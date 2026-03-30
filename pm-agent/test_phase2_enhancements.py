import pytest
import sqlite3
import json
import io
import csv
from fastapi.testclient import TestClient
from approval_queue import ApprovalQueueManager
from approval_ui_app import app

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_phase2.db"
    return str(db_file)

@pytest.fixture
def aq(test_db):
    return ApprovalQueueManager(db_path=test_db)

@pytest.fixture
def client(test_db):
    from approval_ui_app import get_aq
    app.dependency_overrides[get_aq] = lambda: ApprovalQueueManager(db_path=test_db)
    return TestClient(app)

def test_revision_1_materialization(aq):
    mock_output = {"registration_title_ko": "Initial Title", "registration_status": "hold"}
    review_id = aq.create_item("product_registration", "Source Title", mock_output, source_data={"original": "data"})
    
    # Check queue item
    item = aq.get_item(review_id)
    assert item['latest_registration_title_ko'] == "Initial Title"
    assert item['latest_revision_number'] == 1
    assert item['latest_revision_id'] is not None
    
    # Check revisions table
    revs = aq.list_revisions(review_id)
    assert len(revs) == 1
    assert revs[0]['revision_number'] == 1
    assert revs[0]['generation_status'] == 'completed'
    assert revs[0]['revised_agent_output']['registration_title_ko'] == "Initial Title"

def test_reviewer_note_validation(aq):
    # Valid
    assert aq.validate_reviewer_note("상품 제목에서 브랜드명 삭제해주세요") is None
    assert aq.validate_reviewer_note("설명 문구를 조금 더 부드럽게 고쳐줘") is None
    
    # Invalid: Too short
    assert "너무 짧습니다" in aq.validate_reviewer_note("수정")
    
    # Invalid: Vague/Blacklist
    assert "모호한 표현" in aq.validate_reviewer_note("다시 수정해")
    assert "모호한 표현" in aq.validate_reviewer_note("잘 좀 해봐")
    
    # Invalid: No target keywords
    assert "명확하지 않습니다" in aq.validate_reviewer_note("이거 좀 이상한데")

def test_export_security_and_content(client, aq):
    mock_output = {"registration_title_ko": "Initial", "registration_status": "hold"}
    review_id = aq.create_item("product_registration", "Source", mock_output, source_data={"src": "data"})
    
    # 1. Export fails if not approved
    res_json = client.get(f"/api/queue/{review_id}/export/json")
    assert res_json.status_code == 400
    assert "Only approved items" in res_json.json()['detail']
    
    # 2. Approve it
    aq.update_reviewer_status(review_id, "approved", "Approved note")
    
    # 3. Export JSON success
    res_json = client.get(f"/api/queue/{review_id}/export/json")
    assert res_json.status_code == 200
    export_data = res_json.json()
    assert export_data['review_id'] == review_id
    assert export_data['revision_number'] == 1
    assert export_data['data']['registration_title_ko'] == "Initial"
    
    # 4. Export CSV success
    res_csv = client.get(f"/api/queue/{review_id}/export/csv")
    assert res_csv.status_code == 200
    assert res_csv.headers['content-type'] == "text/csv; charset=utf-8"
    
    content = res_csv.text
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]['review_id'] == review_id
    assert rows[0]['registration_title_ko'] == "Initial"

def test_export_uses_latest_revision(client, aq):
    mock_output = {"registration_title_ko": "V1", "registration_status": "hold"}
    review_id = aq.create_item("product_registration", "Source", mock_output, source_data={"src": "data"})
    
    # Create Revision 2 (manually for test)
    revised_output = {"registration_title_ko": "V2 Approved", "registration_status": "ready"}
    rev_id_2 = aq.create_revision_pending(review_id, {}, mock_output, "Note for V2")
    aq.complete_revision(rev_id_2, revised_output, "completed")
    
    # Set to approved
    aq.update_reviewer_status(review_id, "approved", "Good")
    
    # Export should be V2
    res_json = client.get(f"/api/queue/{review_id}/export/json")
    assert res_json.json()['data']['registration_title_ko'] == "V2 Approved"
    assert res_json.json()['revision_number'] == 2
