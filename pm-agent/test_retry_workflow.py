import pytest
import sqlite3
import json
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from approval_queue import ApprovalQueueManager
from approval_ui_app import app
from agent_framework import TaskResult

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_retry.db"
    return str(db_file)

@pytest.fixture
def aq(test_db):
    return ApprovalQueueManager(db_path=test_db)

@pytest.fixture
def client(test_db):
    # Override get_aq dependency
    from approval_ui_app import get_aq
    app.dependency_overrides[get_aq] = lambda: ApprovalQueueManager(db_path=test_db)
    return TestClient(app)

def test_revision_table_init(aq):
    with sqlite3.connect(aq.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='revisions'")
        assert cursor.fetchone() is not None

def test_create_revision_pending_and_complete(aq):
    mock_output = {"registration_title_ko": "Orig", "registration_status": "hold"}
    review_id = aq.create_item("product_registration", "Test", mock_output, source_data={"title": "Test"})
    
    source_snap = {"title": "Test"}
    note = "Fix this"
    
    rev_id = aq.create_revision_pending(review_id, source_snap, mock_output, note)
    assert rev_id is not None
    
    latest = aq.get_latest_revision(review_id)
    assert latest['revision_number'] == 2
    assert latest['generation_status'] == 'pending'
    
    # Complete
    revised_output = {"registration_title_ko": "Revised", "registration_status": "ready", "needs_human_review": False}
    aq.complete_revision(rev_id, revised_output, "completed")
    
    # Verify main item updated
    item = aq.get_item(review_id)
    assert item['latest_registration_title_ko'] == "Revised"
    assert item['latest_registration_status'] == "ready"
    assert item['reviewer_status'] == "pending" # Reset to pending
    
    # Verify revision status
    revs = aq.list_revisions(review_id)
    assert len(revs) == 2
    assert revs[1]['generation_status'] == 'completed'
    assert revs[1]['revised_agent_output']['registration_title_ko'] == "Revised"

def test_retry_concurrency_protection(aq):
    mock_output = {"registration_title_ko": "Orig", "registration_status": "hold"}
    review_id = aq.create_item("product_registration", "Test", mock_output, source_data={})
    
    aq.create_revision_pending(review_id, {}, {}, "note")
    
    with pytest.raises(ConnectionError, match="이미 처리 중인 Revision"):
        aq.create_revision_pending(review_id, {}, {}, "note 2")

def test_api_retry_validation(client, aq):
    mock_output = {"registration_title_ko": "Orig", "registration_status": "hold"}
    review_id = aq.create_item("product_registration", "Test", mock_output, source_data={})
    
    # Fail: status is pending, not needs_edit
    res = client.post(f"/api/queue/{review_id}/retry")
    assert res.status_code == 400
    assert "Only 'needs_edit' items" in res.json()['detail']
    
    # Set to needs_edit but no note
    aq.update_reviewer_status(review_id, "needs_edit", "")
    res = client.post(f"/api/queue/{review_id}/retry")
    assert res.status_code == 400
    assert "메모가 비어 있습니다" in res.json()['detail']

    # Set to needs_edit but vague note
    aq.update_reviewer_status(review_id, "needs_edit", "다시")
    res = client.post(f"/api/queue/{review_id}/retry")
    assert res.status_code == 400
    assert "너무 짧습니다" in res.json()['detail']

@patch("product_registration_agent.ProductRegistrationAgent.execute")
def test_api_retry_success_flow(mock_execute, client, aq):
    mock_output = {"registration_title_ko": "Orig", "registration_status": "hold", "source_options": []}
    review_id = aq.create_item("product_registration", "Test", mock_output, source_data={"source_title": "Test", "source_options": []})
    aq.update_reviewer_status(review_id, "needs_edit", "상품명에서 브랜드명을 삭제해 주세요")
    
    # Mock agent success
    revised = {"registration_title_ko": "Fixed Title", "registration_status": "ready", "needs_human_review": False}
    mock_execute.return_value = TaskResult(
        agent_name="product_registration",
        status="completed", # fixed to match AgentStatus.COMPLETED
        output=revised
    )
    
    res = client.post(f"/api/queue/{review_id}/retry")
    assert res.status_code == 200
    assert res.json()['success'] is True
    
    # Check DB
    item = aq.get_item(review_id)
    assert item['latest_registration_title_ko'] == "Fixed Title"
    assert item['reviewer_status'] == "pending"
    
    revs = aq.list_revisions(review_id)
    assert len(revs) == 2 # 1 (Initial) + 1 (Retry)
    assert revs[1]['revision_number'] == 2
    assert revs[1]['reviewer_note'] == "상품명에서 브랜드명을 삭제해 주세요"

def test_agent_retry_prompt_logic():
    from product_registration_agent import ProductRegistrationAgent, ProductRegistrationInputSchema
    agent = ProductRegistrationAgent()
    
    # We spy on _generate_drafts to see if it would fail or we can mock/check the prompt construction if we expose it
    # But since it's private, we'll verify the schema supports the fields
    inp = ProductRegistrationInputSchema(
        source_title="Title",
        reviewer_note="Note",
        previous_output={"title": "Old"}
    )
    assert inp.reviewer_note == "Note"
    assert inp.previous_output == {"title": "Old"}
