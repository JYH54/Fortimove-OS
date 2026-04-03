import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from approval_ui_app import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_aq():
    with patch('approval_ui_app.get_aq') as mock:
        yield mock.return_value

def test_api_list_queue(client, mock_aq):
    mock_aq.list_items.return_value = [{"review_id": "1", "registration_status": "hold"}]
    
    res = client.get("/api/queue?status=pending")
    
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["review_id"] == "1"

def test_api_get_item(client, mock_aq):
    mock_aq.get_item.return_value = {
        "review_id": "123",
        "raw_agent_output": {"key": "val"},
        "needs_human_review": True
    }
    
    res = client.get("/api/queue/123")
    
    assert res.status_code == 200
    assert res.json()["review_id"] == "123"

def test_api_get_item_not_found(client, mock_aq):
    mock_aq.get_item.return_value = None
    
    res = client.get("/api/queue/not_found")
    
    assert res.status_code == 404

def test_api_update_status(client, mock_aq):
    res = client.patch("/api/queue/123", json={
        "reviewer_status": "approved",
        "reviewer_note": "ok"
    })
    
    assert res.status_code == 200
    mock_aq.update_reviewer_status.assert_called_once_with("123", "approved", "ok")

def test_api_update_invalid_status(client, mock_aq):
    mock_aq.update_reviewer_status.side_effect = ValueError("Invalid status")
    
    res = client.patch("/api/queue/123", json={
        "reviewer_status": "wrong_status",
        "reviewer_note": "bad"
    })
    
    assert res.status_code == 400

def test_ui_index(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "<title>Approval Queue MVP</title>" in res.text
