"""
Tests for HTTPS deployment, real_send verification, and duplicate handoff prevention.
"""
import pytest
import os
import tempfile
import time
from fastapi.testclient import TestClient
from approval_queue import ApprovalQueueManager


@pytest.fixture(scope="function")
def setup_env():
    """Setup test environment with ADMIN_TOKEN."""
    os.environ["ADMIN_TOKEN"] = "test_production_token_xyz"
    os.environ.pop("ALLOW_LOCAL_NOAUTH", None)
    os.environ.pop("SLACK_WEBHOOK_URL", None)
    os.environ.pop("SMTP_HOST", None)
    yield
    os.environ.pop("ADMIN_TOKEN", None)


@pytest.fixture(scope="function")
def test_db():
    """Create temporary test database."""
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = db_file.name
    db_file.close()
    aq = ApprovalQueueManager(db_path=db_path)
    yield aq, db_path
    import os
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestDuplicateHandoffPrevention:
    """Test duplicate handoff execution prevention."""

    def test_duplicate_handoff_blocked(self, test_db):
        """TEST 1: Second handoff while first is running should be blocked with HTTPException."""
        aq, db_path = test_db

        # Start first handoff run
        run_id_1 = aq.start_handoff_run('log_only')
        assert run_id_1 is not None

        # Try to start second handoff (should raise 409)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            run_id_2 = aq.start_handoff_run('log_only')

        assert exc_info.value.status_code == 409
        assert "already in progress" in exc_info.value.detail.lower()

        # Cleanup: finish first run
        aq.finish_handoff_run(
            run_id=run_id_1,
            status='completed',
            item_count=0,
            slack_status='no_op',
            email_status='no_op',
            overall_result='no_op'
        )

        # Now third handoff should succeed
        run_id_3 = aq.start_handoff_run('log_only')
        assert run_id_3 is not None
        aq.finish_handoff_run(
            run_id=run_id_3,
            status='completed',
            item_count=0,
            slack_status='no_op',
            email_status='no_op',
            overall_result='no_op'
        )

    def test_stale_lock_recovery(self, test_db):
        """TEST 2: Stale lock (>10 min) should be auto-recovered."""
        aq, db_path = test_db

        # Create a stale run (manually set old timestamp)
        import sqlite3
        from datetime import datetime, timedelta
        old_timestamp = (datetime.utcnow() - timedelta(minutes=11)).isoformat()

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO handoff_runs (run_id, status, started_at, mode)
                VALUES (?, ?, ?, ?)
            ''', ('stale-run-id', 'running', old_timestamp, 'log_only'))
            conn.commit()

        # Should be able to start new run (stale lock auto-failed)
        run_id_new = aq.start_handoff_run('log_only')
        assert run_id_new is not None

        # Check stale run was marked as failed
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM handoff_runs WHERE run_id = ?', ('stale-run-id',))
            stale_run = cursor.fetchone()
            assert stale_run['status'] == 'failed'
            assert 'stale' in stale_run['error_message'].lower()

    def test_handoff_run_lifecycle(self, test_db):
        """TEST 3: Normal handoff run lifecycle (start -> finish)."""
        aq, db_path = test_db

        # Start run
        run_id = aq.start_handoff_run('log_only')
        assert run_id is not None

        # Check current run exists
        current = aq.get_current_handoff_run()
        assert current is not None
        assert current['run_id'] == run_id
        assert current['status'] == 'running'

        # Finish run
        aq.finish_handoff_run(
            run_id=run_id,
            status='completed',
            item_count=5,
            slack_status='sent',
            email_status='sent',
            overall_result='success'
        )

        # Check no current run
        current_after = aq.get_current_handoff_run()
        assert current_after is None

        # Check run history
        history = aq.get_handoff_run_history(limit=1)
        assert len(history) == 1
        assert history[0]['run_id'] == run_id
        assert history[0]['status'] == 'completed'
        assert history[0]['item_count'] == 5


class TestRealSendVerification:
    """Test real_send verification endpoints."""

    def test_verify_endpoint_no_credentials(self, setup_env):
        """TEST 4: Verify endpoint shows 'not_verified' when credentials absent."""
        from approval_ui_app import app
        client = TestClient(app)

        response = client.get(
            "/api/handoff/verify",
            headers={"X-API-TOKEN": "test_production_token_xyz"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data['mode'] == 'log_only'
        assert data['slack']['status'] == 'not_verified'
        assert data['slack']['configured'] is False
        assert data['email']['status'] == 'not_verified'
        assert data['email']['configured'] is False

    def test_verify_endpoint_slack_configured(self, setup_env):
        """TEST 5: Verify endpoint attempts real Slack verification if configured."""
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/INVALID/TEST/URL"

        from approval_ui_app import app
        client = TestClient(app)

        response = client.get(
            "/api/handoff/verify",
            headers={"X-API-TOKEN": "test_production_token_xyz"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data['mode'] == 'real_send'  # Slack URL is configured
        assert data['slack']['configured'] is True
        # Will likely fail because URL is invalid, but that's expected
        assert data['slack']['status'] in ['failed', 'verified']

        os.environ.pop("SLACK_WEBHOOK_URL")

    def test_verify_endpoint_requires_auth(self):
        """TEST 6: Verify endpoint requires authentication."""
        os.environ["ADMIN_TOKEN"] = "test_production_token_xyz"

        from approval_ui_app import app
        client = TestClient(app)

        response = client.get("/api/handoff/verify")
        assert response.status_code == 401

        os.environ.pop("ADMIN_TOKEN")


class TestHandoffRunsEndpoint:
    """Test handoff runs history endpoint."""

    def test_runs_endpoint_shows_current_run(self, setup_env, test_db):
        """TEST 7: get_current_handoff_run() returns current run if in progress."""
        aq, db_path = test_db

        # Start a run
        run_id = aq.start_handoff_run('log_only')

        # Check current run
        current = aq.get_current_handoff_run()
        assert current is not None
        assert current['run_id'] == run_id
        assert current['status'] == 'running'

        # Cleanup
        aq.finish_handoff_run(
            run_id=run_id,
            status='completed',
            item_count=0,
            slack_status='no_op',
            email_status='no_op',
            overall_result='no_op'
        )

        # After finish, no current run
        current_after = aq.get_current_handoff_run()
        assert current_after is None

    def test_runs_endpoint_shows_recent_history(self, setup_env, test_db):
        """TEST 8: get_handoff_run_history() shows recent completed runs."""
        aq, db_path = test_db

        # Create 3 completed runs
        for i in range(3):
            run_id = aq.start_handoff_run('log_only')
            aq.finish_handoff_run(
                run_id=run_id,
                status='completed',
                item_count=i,
                slack_status='sent',
                email_status='sent',
                overall_result='success'
            )

        # Check recent runs
        history = aq.get_handoff_run_history(limit=10)
        assert len(history) == 3
        assert history[0]['item_count'] == 2  # Most recent
        assert history[1]['item_count'] == 1
        assert history[2]['item_count'] == 0


class TestHandoffWithNoApprovedItems:
    """Test handoff behavior with no approved items."""

    def test_handoff_no_approved_items_is_noop(self, setup_env, test_db):
        """TEST 9: Handoff run records no_op when 0 approved items."""
        aq, db_path = test_db

        # Simulate no-op handoff run
        run_id = aq.start_handoff_run('log_only')
        aq.finish_handoff_run(
            run_id=run_id,
            status='no_op',
            item_count=0,
            slack_status='no_op',
            email_status='no_op',
            overall_result='no_op'
        )

        # Check run was recorded
        history = aq.get_handoff_run_history(limit=1)
        assert len(history) == 1
        assert history[0]['status'] == 'no_op'
        assert history[0]['item_count'] == 0
        assert history[0]['overall_result'] == 'no_op'


class TestDeploymentDocumentation:
    """Test deployment documentation exists and is comprehensive."""

    def test_deployment_doc_exists(self):
        """TEST 10: DEPLOYMENT.md exists."""
        import os
        doc_path = os.path.join(os.path.dirname(__file__), 'DEPLOYMENT.md')
        assert os.path.exists(doc_path), "DEPLOYMENT.md must exist"

    def test_deployment_doc_mentions_https(self):
        """TEST 11: DEPLOYMENT.md explicitly mentions HTTPS requirement."""
        import os
        doc_path = os.path.join(os.path.dirname(__file__), 'DEPLOYMENT.md')
        with open(doc_path, 'r') as f:
            content = f.read()

        assert 'HTTPS' in content.upper(), "DEPLOYMENT.md must mention HTTPS"
        assert 'HTTP' in content.upper(), "DEPLOYMENT.md must explain HTTP danger"
        assert 'plaintext' in content.lower() or 'plain text' in content.lower(), \
            "DEPLOYMENT.md must explain token plaintext risk"

    def test_deployment_doc_has_nginx_config(self):
        """TEST 12: DEPLOYMENT.md includes reverse proxy example."""
        import os
        doc_path = os.path.join(os.path.dirname(__file__), 'DEPLOYMENT.md')
        with open(doc_path, 'r') as f:
            content = f.read()

        # Should have nginx or traefik or caddy config
        has_proxy = ('nginx' in content.lower() or
                     'traefik' in content.lower() or
                     'caddy' in content.lower())
        assert has_proxy, "DEPLOYMENT.md must include reverse proxy config"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
