import pytest
import sqlite3
import os
from approval_queue import ApprovalQueueManager

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_queue.db"
    return str(db_file)

def test_approval_queue_creation_and_list(test_db):
    aq = ApprovalQueueManager(db_path=test_db)
    
    mock_agent_output = {
        "registration_title_ko": "테스트 상품명",
        "registration_status": "hold",
        "needs_human_review": True,
        "hold_reason": "위험 문구 포함",
        "risk_notes": ["위험 문구 포함"],
        "suggested_next_action": "담당자 수동 리뷰 및 데이터 보완",
        "normalized_options_ko": ["빨강", "파랑"]
    }
    
    # Insert
    review_id = aq.create_item("product_registration", "Test Item Initial", mock_agent_output, source_data={"title": "Test Item Initial"})
    assert review_id is not None
    
    # List pending
    items = aq.list_items("pending")
    assert len(items) == 1
    assert items[0]["review_id"] == review_id
    assert items[0]["raw_agent_output"]["normalized_options_ko"] == ["빨강", "파랑"]
    
    # Ensure immutability principle
    assert "reviewer_note" in items[0]
    assert items[0]["reviewer_status"] == "pending"

def test_approval_queue_update_status(test_db):
    aq = ApprovalQueueManager(db_path=test_db)
    
    mock_agent_output = {
        "registration_title_ko": "상품",
        "registration_status": "hold",
        "needs_human_review": True
    }
    
    review_id = aq.create_item("product_registration", "Item", mock_agent_output, source_data={"title": "Item"})
    
    # Update status to approved
    aq.update_reviewer_status(review_id, "approved", "Looking good now")
    
    # Assert it is no longer pending
    pending_items = aq.list_items("pending")
    assert len(pending_items) == 0
    
    # Fetch it directly
    approved_items = aq.list_items("approved")
    assert len(approved_items) == 1
    assert approved_items[0]["reviewer_note"] == "Looking good now"
    # Raw JSON must remain entirely identical
    assert approved_items[0]["raw_agent_output"]["registration_status"] == "hold"

def test_approval_queue_invalid_status(test_db):
    aq = ApprovalQueueManager(db_path=test_db)
    
    with pytest.raises(ValueError, match="Invalid reviewer_status"):
        aq.list_items("unknown_status")
        
    with pytest.raises(ValueError, match="Invalid reviewer_status"):
        aq.update_reviewer_status("some-id", "unknown", "invalid test")
