import pytest
import sqlite3
import json
import io
import csv
from fastapi.testclient import TestClient
from approval_queue import ApprovalQueueManager
from approval_ui_app import app, handoff_service

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_handoff.db"
    return str(db_file)

@pytest.fixture
def aq(test_db):
    return ApprovalQueueManager(db_path=test_db)

@pytest.fixture
def client(test_db):
    from approval_ui_app import get_aq
    app.dependency_overrides[get_aq] = lambda: ApprovalQueueManager(db_path=test_db)
    return TestClient(app)

def test_batch_export_selects_latest_only(aq):
    # Case: Item 1 has 2 revisions, Item 2 has 1 revision. Both approved.
    # Item 1
    mock_v1 = {"registration_title_ko": "Item 1 V1", "registration_status": "hold"}
    id1 = aq.create_item("product_registration", "Source 1", mock_v1)
    
    mock_v2 = {"registration_title_ko": "Item 1 V2 (Approved)", "registration_status": "ready"}
    rev2_id = aq.create_revision_pending(id1, {}, mock_v1, "Note")
    aq.complete_revision(rev2_id, mock_v2, "completed")
    aq.update_reviewer_status(id1, "approved", "Good")
    
    # Item 2
    mock_item2_v1 = {"registration_title_ko": "Item 2 V1 (Approved)", "registration_status": "ready"}
    id2 = aq.create_item("product_registration", "Source 2", mock_item2_v1)
    aq.update_reviewer_status(id2, "approved", "Excellent")
    
    # Fetch
    items = aq.get_latest_approved_items()
    assert len(items) == 2
    
    titles = [i['revised_agent_output']['registration_title_ko'] for i in items]
    assert "Item 1 V2 (Approved)" in titles
    assert "Item 2 V1 (Approved)" in titles
    assert "Item 1 V1" not in titles

def test_batch_export_empty_case(aq):
    items = aq.get_latest_approved_items()
    assert len(items) == 0

def test_handoff_trigger_api(client, aq):
    # Setup 1 approved item
    mock = {"registration_title_ko": "Test Item", "registration_status": "ready"}
    id1 = aq.create_item("product_registration", "Source", mock)
    aq.update_reviewer_status(id1, "approved", "Note")
    
    # Trigger Handoff
    res = client.post("/api/handoff/run")
    assert res.status_code == 200
    data = res.json()
    assert data['success'] is True
    assert data['count'] == 1
    assert data['slack']['status'] == 'log_only'
    assert data['email']['status'] == 'log_only'

def test_slack_summary_preview_limit():
    from handoff_service import HandoffService
    svc = HandoffService()
    
    # 5 items
    items = [
        {"source_title": f"Item {i}", "revision_number": 1, "revised_agent_output": {"registration_title_ko": f"Title {i}"}}
        for i in range(1, 6)
    ]
    
    res = svc.send_slack_summary(items)
    text = res['message']['attachments'][0]['text']
    assert "Title 1" in text
    assert "Title 3" in text
    assert "Title 4" not in text
    assert "외 2건" in text

def test_csv_batch_export_endpoint(client, aq):
    mock = {"registration_title_ko": "CSV Test", "registration_status": "ready"}
    id1 = aq.create_item("product_registration", "Source", mock)
    aq.update_reviewer_status(id1, "approved", "Note")
    
    res = client.get("/api/exports/approved/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers['content-type']
    
    content = res.text
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]['registration_title_ko'] == "CSV Test"
