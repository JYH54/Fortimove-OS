import pytest
import os
import sqlite3
import json
from fastapi.testclient import TestClient
from approval_queue import ApprovalQueueManager
from approval_ui_app import app, get_aq

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_handoff_meta.db"
    return str(db_file)

@pytest.fixture
def aq(test_db):
    return ApprovalQueueManager(db_path=test_db)

@pytest.fixture
def client(test_db):
    app.dependency_overrides[get_aq] = lambda: ApprovalQueueManager(db_path=test_db)
    # Enable bypass for easier testing of logic
    os.environ["ALLOW_LOCAL_NOAUTH"] = "true"
    return TestClient(app)

def test_handoff_no_approved_items_still_logs(client, aq):
    # Case: 0 approved items
    res = client.post("/api/handoff/run")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 0
    assert data["slack"]["status"] == "log_only" # Assuming no env set

    # Verify DB record
    history = aq.get_handoff_history(limit=1)
    assert len(history) == 1
    log = history[0]
    assert log["item_count"] == 0
    assert log["slack_status"] == "no_op"
    assert log["email_status"] == "no_op"
    assert log["mode"] == "log_only"

def test_handoff_with_items_logs_correctly(client, aq):
    # Setup 1 approved item
    mock_data = {"registration_title_ko": "Test", "registration_status": "ready"}
    id1 = aq.create_item("product_registration", "Source", mock_data)
    aq.update_reviewer_status(id1, "approved", "Good")
    
    # Run handoff
    res = client.post("/api/handoff/run")
    assert res.status_code == 200
    
    history = aq.get_handoff_history(limit=1)
    log = history[0]
    assert log["item_count"] == 1
    assert log["slack_status"] == "log_only"
    assert log["export_generated"] == 1

def test_slack_failure_isolation(client, aq):
    # Force a failure scenario? 
    # Since we can't easily mock httpx.Client inside the endpoint without more dependency injection,
    # we can at least verify that it records status correctly if provided a bad URL.
    
    from approval_ui_app import handoff_service
    handoff_service.log_only = False
    handoff_service.slack_webhook_url = "https://invalid-webhook-url.example.com"
    handoff_service.smtp_host = "" # Trigger fail for email

    # Approved item
    mock_data = {"registration_title_ko": "Test", "registration_status": "ready"}
    id1 = aq.create_item("product_registration", "Source", mock_data)
    aq.update_reviewer_status(id1, "approved", "Good")

    res = client.post("/api/handoff/run")
    assert res.status_code == 200
    data = res.json()
    assert data["slack"]["status"] == "failed"
    assert data["email"]["status"] == "failed"
    
    # Check DB
    history = aq.get_handoff_history(limit=1)
    log = history[0]
    assert log["slack_status"] == "failed"
    # Flexible error check
    assert log["slack_error"] is not None
    assert log["email_status"] == "failed"
    assert "SMTP_HOST" in log["email_error"]

def test_handoff_status_history_endpoint(client, aq):
    # Create 2 logs
    aq.create_handoff_log(1, True, "sent", None, "sent", None, "real_send")
    aq.create_handoff_log(2, True, "log_only", None, "log_only", None, "log_only")
    
    res = client.get("/api/handoff/status")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["item_count"] == 2 # Most recent first
    assert data[1]["item_count"] == 1

def test_no_mutation_during_handoff(client, aq):
    # Setup approved item
    mock_data = {"registration_title_ko": "Keep Me", "registration_status": "ready"}
    id1 = aq.create_item("product_registration", "Source", mock_data)
    aq.update_reviewer_status(id1, "approved", "Good")
    
    # Get state before
    item_before = aq.get_item(id1)
    
    # Run handoff
    client.post("/api/handoff/run")
    
    # Verify state after
    item_after = aq.get_item(id1)
    assert item_before["reviewer_status"] == item_after["reviewer_status"]
    assert item_before["raw_agent_output"] == item_after["raw_agent_output"]
