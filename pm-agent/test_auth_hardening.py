import pytest
import os
from fastapi.testclient import TestClient
from approval_ui_app import app

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_auth_sys.db"
    return str(db_file)

@pytest.fixture
def client(test_db):
    from approval_ui_app import get_aq, ApprovalQueueManager
    app.dependency_overrides[get_aq] = lambda: ApprovalQueueManager(db_path=test_db)
    # Ensure ADMIN_TOKEN is set for the test session
    os.environ["ADMIN_TOKEN"] = "test-secret-token"
    # Ensure ALLOW_LOCAL_NOAUTH is false to test strict mode
    os.environ["ALLOW_LOCAL_NOAUTH"] = "false"
    return TestClient(app)

def test_health_is_public(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_api_queue_requires_auth(client):
    # No header
    res = client.get("/api/queue")
    assert res.status_code == 401
    
    # Wrong header
    res = client.get("/api/queue", headers={"X-API-TOKEN": "wrong-token"})
    assert res.status_code == 401
    
    # Correct header
    res = client.get("/api/queue", headers={"X-API-TOKEN": "test-secret-token"})
    assert res.status_code == 200

def test_write_endpoints_require_auth(client):
    res = client.patch("/api/queue/any-id", headers={"X-API-TOKEN": "wrong-token"}, json={"reviewer_status": "approved"})
    assert res.status_code == 401

def test_export_endpoints_require_auth(client):
    res = client.get("/api/exports/approved/json", headers={"X-API-TOKEN": "wrong-token"})
    assert res.status_code == 401

def test_allow_local_noauth_mode():
    os.environ["ADMIN_TOKEN"] = "" # Unset
    os.environ["ALLOW_LOCAL_NOAUTH"] = "true"
    
    # Use a fresh client to pick up env changes if needed, 
    # but since app reads env inside the dependency, we just call it.
    with TestClient(app) as c:
        res = c.get("/api/queue")
        assert res.status_code == 200

def test_strict_mode_when_no_token_and_no_flag():
    os.environ["ADMIN_TOKEN"] = ""
    os.environ["ALLOW_LOCAL_NOAUTH"] = "false"
    
    with TestClient(app) as c:
        res = c.get("/api/queue")
        assert res.status_code == 401
        assert "ADMIN_TOKEN not configured" in res.json()["detail"]
