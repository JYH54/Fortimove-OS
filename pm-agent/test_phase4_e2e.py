"""
End-to-End Integration Tests for Phase 4 Review-First Publishing Console

Tests the complete flow from auto-generated content through review, approval, and export.
"""

import pytest
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Import Phase 4 modules
from review_workflow import validate_status_transition, get_allowed_next_statuses
from export_service import ExportService
from image_review_manager import ImageReviewManager

# Test database path
TEST_DB_PATH = "data/test_approval_queue.db"


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test"""
    db_path = Path(TEST_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing test database
    if db_path.exists():
        db_path.unlink()

    # Create new database with Phase 4 schema
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Load and execute Phase 4 schema
    schema_path = Path(__file__).parent / "004_phase4_schema.sql"
    if schema_path.exists():
        schema_sql = schema_path.read_text()
        cursor.executescript(schema_sql)
    else:
        # Minimal schema for testing if file not found
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS content_review (
                review_id TEXT PRIMARY KEY,
                source_title TEXT,
                source_url TEXT,
                score INTEGER DEFAULT 0,
                decision TEXT,
                generated_naver_title TEXT,
                generated_naver_description TEXT,
                generated_naver_tags TEXT,
                generated_coupang_title TEXT,
                generated_coupang_description TEXT,
                generated_price REAL,
                reviewed_naver_title TEXT,
                reviewed_naver_description TEXT,
                reviewed_naver_tags TEXT,
                reviewed_coupang_title TEXT,
                reviewed_coupang_description TEXT,
                reviewed_price REAL,
                review_notes TEXT,
                review_status TEXT DEFAULT 'draft',
                reviewed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS image_review (
                image_id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL,
                url TEXT NOT NULL,
                is_primary INTEGER DEFAULT 0,
                is_excluded INTEGER DEFAULT 0,
                display_order INTEGER DEFAULT 0,
                warning_notes TEXT,
                reviewed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES content_review(review_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS export_log (
                export_id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                exported_by TEXT NOT NULL,
                csv_data TEXT,
                row_count INTEGER DEFAULT 0,
                export_status TEXT DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES content_review(review_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS review_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id TEXT NOT NULL,
                action TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                operator TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES content_review(review_id) ON DELETE CASCADE
            );
        """)

    conn.commit()
    conn.close()

    yield TEST_DB_PATH

    # Cleanup after test
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def workflow_manager(test_db):
    """Initialize ReviewWorkflowManager with test database"""
    return ReviewWorkflowManager(db_path=test_db)


@pytest.fixture
def console_service(test_db):
    """Initialize ReviewConsoleService with test database"""
    return ReviewConsoleService(db_path=test_db)


@pytest.fixture
def export_service(test_db):
    """Initialize ExportService with test database"""
    return ExportService(db_path=test_db)


@pytest.fixture
def image_manager(test_db):
    """Initialize ImageReviewManager with test database"""
    return ImageReviewManager(db_path=test_db)


@pytest.fixture
def sample_review_data():
    """Sample auto-generated content for testing"""
    return {
        "review_id": "test-review-001",
        "source_title": "프리미엄 스테인리스 텀블러 500ml",
        "source_url": "https://item.taobao.com/item.htm?id=123456789",
        "score": 85,
        "decision": "PASS",
        "generated_naver_title": "[한정특가] 프리미엄 스테인리스 텀블러 500ml - 진공단열 보온보냉",
        "generated_naver_description": "고급 스테인리스 소재로 제작된 진공단열 텀블러입니다. 500ml 용량으로 보온 6시간, 보냉 12시간 유지됩니다.",
        "generated_naver_tags": json.dumps(["텀블러", "보온보냉", "스테인리스", "500ml", "진공단열"]),
        "generated_coupang_title": "프리미엄 진공단열 텀블러 500ml",
        "generated_coupang_description": "진공단열 설계로 장시간 온도 유지\n스테인리스 소재로 위생적\n500ml 넉넉한 용량",
        "generated_price": 15900.0,
        "review_status": "draft"
    }


@pytest.fixture
def sample_images():
    """Sample image data for testing"""
    return [
        {
            "image_id": "img-001",
            "url": "https://example.com/images/tumbler-main.jpg",
            "is_primary": 1,
            "is_excluded": 0,
            "display_order": 0
        },
        {
            "image_id": "img-002",
            "url": "https://example.com/images/tumbler-detail1.jpg",
            "is_primary": 0,
            "is_excluded": 0,
            "display_order": 1
        },
        {
            "image_id": "img-003",
            "url": "https://example.com/images/tumbler-detail2.jpg",
            "is_primary": 0,
            "is_excluded": 0,
            "display_order": 2
        }
    ]


def insert_review(db_path: str, review_data: Dict[str, Any]):
    """Helper: Insert review into database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns = ", ".join(review_data.keys())
    placeholders = ", ".join(["?" for _ in review_data])

    cursor.execute(
        f"INSERT INTO content_review ({columns}) VALUES ({placeholders})",
        list(review_data.values())
    )

    conn.commit()
    conn.close()


def insert_images(db_path: str, review_id: str, images: List[Dict[str, Any]]):
    """Helper: Insert images into database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for img in images:
        img_data = img.copy()
        img_data["review_id"] = review_id

        columns = ", ".join(img_data.keys())
        placeholders = ", ".join(["?" for _ in img_data])

        cursor.execute(
            f"INSERT INTO image_review ({columns}) VALUES ({placeholders})",
            list(img_data.values())
        )

    conn.commit()
    conn.close()


def get_review(db_path: str, review_id: str) -> Dict[str, Any]:
    """Helper: Get review from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM content_review WHERE review_id = ?", (review_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_images(db_path: str, review_id: str) -> List[Dict[str, Any]]:
    """Helper: Get images from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM image_review WHERE review_id = ? ORDER BY display_order",
        (review_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_export_logs(db_path: str, review_id: str) -> List[Dict[str, Any]]:
    """Helper: Get export logs from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM export_log WHERE review_id = ? ORDER BY created_at DESC",
        (review_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_review_history(db_path: str, review_id: str) -> List[Dict[str, Any]]:
    """Helper: Get review history from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM review_history WHERE review_id = ? ORDER BY created_at",
        (review_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ============================================================================
# HAPPY PATH TESTS
# ============================================================================

def test_happy_path_full_flow(test_db, workflow_manager, console_service, export_service, image_manager, sample_review_data, sample_images):
    """
    Test happy-path flow:
    auto-generated content -> review detail load -> reviewed_* save -> image review update
    -> workflow transition to under_review -> approve_for_export -> csv export
    -> export_log verification -> audit/review history verification
    """
    review_id = sample_review_data["review_id"]

    # Step 1: Insert auto-generated content
    insert_review(test_db, sample_review_data)
    insert_images(test_db, review_id, sample_images)

    # Step 2: Review detail load
    review = console_service.get_review_detail(review_id)
    assert review is not None
    assert review["review_id"] == review_id
    assert review["review_status"] == "draft"
    assert review["generated_naver_title"] == sample_review_data["generated_naver_title"]

    images = image_manager.get_images(review_id)
    assert len(images["reviewed_images"]) == 3
    assert any(img["is_primary"] == 1 for img in images["reviewed_images"])

    # Step 3: Save reviewed_* content
    reviewed_data = {
        "reviewed_naver_title": "[최종] 프리미엄 스테인리스 텀블러 500ml - 검수완료",
        "reviewed_naver_description": "검수를 거친 고급 스테인리스 텀블러입니다. 진공단열로 보온 6시간 보냉 12시간.",
        "reviewed_naver_tags": ["텀블러", "보온", "스테인리스"],
        "reviewed_coupang_title": "프리미엄 텀블러 500ml",
        "reviewed_coupang_description": "진공단열 보온보냉\n스테인리스 위생소재",
        "reviewed_price": 16900.0,
        "review_notes": "가격 조정 및 타이틀 최적화 완료"
    }

    result = console_service.save_reviewed_content(review_id, reviewed_data)
    assert result["status"] == "success"

    # Verify reviewed content saved
    updated_review = get_review(test_db, review_id)
    assert updated_review["reviewed_naver_title"] == reviewed_data["reviewed_naver_title"]
    assert updated_review["reviewed_price"] == reviewed_data["reviewed_price"]

    # Step 4: Update image review (set different primary)
    image_update_result = image_manager.set_primary_image(
        review_id=review_id,
        image_id="img-002",
        operator="test_operator"
    )
    assert image_update_result["status"] == "success"

    # Verify primary image changed
    updated_images = get_images(test_db, review_id)
    primary_img = [img for img in updated_images if img["is_primary"] == 1]
    assert len(primary_img) == 1
    assert primary_img[0]["image_id"] == "img-002"

    # Step 5: Workflow transition to under_review
    transition_result = workflow_manager.transition(
        review_id=review_id,
        action="submit_for_review",
        operator="test_operator"
    )
    assert transition_result["status"] == "success"
    assert transition_result["new_status"] == "under_review"

    # Step 6: Approve for export
    approve_result = workflow_manager.transition(
        review_id=review_id,
        action="approve_for_export",
        operator="test_operator",
        notes="검수 완료"
    )
    assert approve_result["status"] == "success"
    assert approve_result["new_status"] == "approved_for_export"

    # Step 7: CSV export
    export_result = export_service.export_to_csv(
        review_ids=[review_id],
        channel="naver",
        exported_by="test_operator"
    )
    assert export_result["status"] == "success"
    assert export_result["row_count"] > 0
    assert "csv_data" in export_result

    # Step 8: Export log verification
    export_logs = get_export_logs(test_db, review_id)
    assert len(export_logs) >= 1
    assert export_logs[0]["channel"] == "naver"
    assert export_logs[0]["exported_by"] == "test_operator"
    assert export_logs[0]["export_status"] == "success"

    # Step 9: Audit/review history verification
    history = get_review_history(test_db, review_id)
    assert len(history) >= 2  # At least: submit_for_review, approve_for_export

    # Verify workflow transitions recorded
    actions = [h["action"] for h in history]
    assert "submit_for_review" in actions
    assert "approve_for_export" in actions

    # Verify status changes recorded
    final_history = history[-1]
    assert final_history["new_status"] == "approved_for_export"


def test_reviewed_content_priority_in_export(test_db, export_service, sample_review_data, sample_images):
    """
    Test that reviewed_* values are used first in export,
    generated_* values only used as fallback
    """
    review_id = sample_review_data["review_id"]

    # Insert review with both generated and reviewed content
    review_data = sample_review_data.copy()
    review_data["reviewed_naver_title"] = "REVIEWED TITLE"
    review_data["reviewed_price"] = 99999.0
    review_data["review_status"] = "approved_for_export"

    insert_review(test_db, review_data)
    insert_images(test_db, review_id, sample_images)

    # Export to CSV
    export_result = export_service.export_to_csv(
        review_ids=[review_id],
        channel="naver",
        exported_by="test_operator"
    )

    assert export_result["status"] == "success"
    csv_data = export_result["csv_data"]

    # Verify reviewed_* values appear in CSV, not generated_*
    assert "REVIEWED TITLE" in csv_data
    assert "99999" in csv_data
    assert sample_review_data["generated_naver_title"] not in csv_data


def test_generated_content_fallback_in_export(test_db, export_service, sample_review_data, sample_images):
    """
    Test that generated_* values are used when reviewed_* values are missing
    """
    review_id = sample_review_data["review_id"]

    # Insert review with only generated content (no reviewed content)
    review_data = sample_review_data.copy()
    review_data["review_status"] = "approved_for_export"
    # Explicitly no reviewed_* fields

    insert_review(test_db, review_data)
    insert_images(test_db, review_id, sample_images)

    # Export to CSV
    export_result = export_service.export_to_csv(
        review_ids=[review_id],
        channel="naver",
        exported_by="test_operator"
    )

    assert export_result["status"] == "success"
    csv_data = export_result["csv_data"]

    # Verify generated_* values appear in CSV as fallback
    assert sample_review_data["generated_naver_title"] in csv_data
    assert str(int(sample_review_data["generated_price"])) in csv_data


# ============================================================================
# BLOCKED PATH TESTS
# ============================================================================

def test_export_blocked_without_exportable_image(test_db, export_service, sample_review_data):
    """Test that export is blocked when no exportable (non-excluded) image exists"""
    review_id = sample_review_data["review_id"]

    # Insert review with approved status
    review_data = sample_review_data.copy()
    review_data["review_status"] = "approved_for_export"
    insert_review(test_db, review_data)

    # Insert only excluded images
    excluded_images = [
        {
            "image_id": "img-001",
            "url": "https://example.com/img1.jpg",
            "is_primary": 0,
            "is_excluded": 1,  # Excluded
            "display_order": 0
        }
    ]
    insert_images(test_db, review_id, excluded_images)

    # Attempt export
    export_result = export_service.export_to_csv(
        review_ids=[review_id],
        channel="naver",
        exported_by="test_operator"
    )

    # Should fail or warn
    assert export_result["status"] in ["error", "warning"]
    assert "no exportable image" in export_result.get("message", "").lower() or \
           "image" in export_result.get("error", "").lower()


def test_export_blocked_for_invalid_status(test_db, export_service, sample_review_data, sample_images):
    """Test that export is blocked when review_status is not approved"""
    review_id = sample_review_data["review_id"]

    # Insert review with draft status (not approved)
    review_data = sample_review_data.copy()
    review_data["review_status"] = "draft"
    insert_review(test_db, review_data)
    insert_images(test_db, review_id, sample_images)

    # Attempt export
    export_result = export_service.export_to_csv(
        review_ids=[review_id],
        channel="naver",
        exported_by="test_operator"
    )

    # Should fail
    assert export_result["status"] == "error"
    assert "not approved" in export_result.get("message", "").lower() or \
           "status" in export_result.get("error", "").lower()


def test_rejected_status_cannot_be_exported(test_db, workflow_manager, export_service, sample_review_data, sample_images):
    """Test that rejected reviews cannot be exported"""
    review_id = sample_review_data["review_id"]

    # Insert review
    insert_review(test_db, sample_review_data)
    insert_images(test_db, review_id, sample_images)

    # Reject the review
    reject_result = workflow_manager.transition(
        review_id=review_id,
        action="reject",
        operator="test_operator",
        notes="품질 미달"
    )
    assert reject_result["status"] == "success"
    assert reject_result["new_status"] == "rejected"

    # Attempt export
    export_result = export_service.export_to_csv(
        review_ids=[review_id],
        channel="naver",
        exported_by="test_operator"
    )

    # Should fail
    assert export_result["status"] == "error"
    assert "rejected" in export_result.get("message", "").lower() or \
           "not allowed" in export_result.get("error", "").lower()


def test_excluded_image_cannot_be_primary(test_db, image_manager, sample_review_data, sample_images):
    """Test that excluded image cannot be set as primary"""
    review_id = sample_review_data["review_id"]

    insert_review(test_db, sample_review_data)
    insert_images(test_db, review_id, sample_images)

    # First exclude an image
    exclude_result = image_manager.update_image_exclusion(
        review_id=review_id,
        image_id="img-002",
        excluded=True,
        operator="test_operator"
    )
    assert exclude_result["status"] == "success"

    # Attempt to set excluded image as primary
    primary_result = image_manager.set_primary_image(
        review_id=review_id,
        image_id="img-002",
        operator="test_operator"
    )

    # Should fail
    assert primary_result["status"] == "error"
    assert "excluded" in primary_result.get("message", "").lower() or \
           "cannot" in primary_result.get("error", "").lower()


def test_multiple_primary_images_prevented(test_db, image_manager, sample_review_data, sample_images):
    """Test that only one primary image can exist at a time"""
    review_id = sample_review_data["review_id"]

    insert_review(test_db, sample_review_data)
    insert_images(test_db, review_id, sample_images)

    # Set img-002 as primary (img-001 was already primary)
    result = image_manager.set_primary_image(
        review_id=review_id,
        image_id="img-002",
        operator="test_operator"
    )
    assert result["status"] == "success"

    # Verify only one primary exists
    images = get_images(test_db, review_id)
    primary_count = sum(1 for img in images if img["is_primary"] == 1)
    assert primary_count == 1

    # Verify img-002 is now primary
    primary_img = [img for img in images if img["is_primary"] == 1][0]
    assert primary_img["image_id"] == "img-002"


def test_invalid_workflow_transitions_blocked(test_db, workflow_manager, sample_review_data, sample_images):
    """Test that invalid workflow transitions are blocked with clear error messages"""
    review_id = sample_review_data["review_id"]

    insert_review(test_db, sample_review_data)
    insert_images(test_db, review_id, sample_images)

    # Attempt to approve_for_export from draft (should require under_review first)
    result = workflow_manager.transition(
        review_id=review_id,
        action="approve_for_export",
        operator="test_operator"
    )

    # Should fail with clear message
    assert result["status"] == "error"
    assert "invalid transition" in result.get("message", "").lower() or \
           "not allowed" in result.get("message", "").lower() or \
           "state" in result.get("error", "").lower()

    # Verify status unchanged
    review = get_review(test_db, review_id)
    assert review["review_status"] == "draft"


def test_image_export_selection_rules(test_db, export_service, sample_review_data):
    """
    Test image export selection rules:
    1. Non-excluded primary image
    2. Otherwise non-excluded display_order fallback
    3. Otherwise export blocked
    """
    review_id = sample_review_data["review_id"]

    # Insert review
    review_data = sample_review_data.copy()
    review_data["review_status"] = "approved_for_export"
    insert_review(test_db, review_data)

    # Test Case 1: Non-excluded primary image exists
    images_case1 = [
        {"image_id": "img-001", "url": "https://example.com/1.jpg", "is_primary": 1, "is_excluded": 0, "display_order": 0},
        {"image_id": "img-002", "url": "https://example.com/2.jpg", "is_primary": 0, "is_excluded": 0, "display_order": 1}
    ]
    insert_images(test_db, review_id, images_case1)

    export_result = export_service.export_to_csv([review_id], "naver", "test_operator")
    assert export_result["status"] == "success"
    # Primary image should be used

    # Cleanup for next test case
    conn = sqlite3.connect(test_db)
    conn.execute("DELETE FROM image_review WHERE review_id = ?", (review_id,))
    conn.commit()
    conn.close()

    # Test Case 2: Primary is excluded, fallback to display_order
    images_case2 = [
        {"image_id": "img-001", "url": "https://example.com/1.jpg", "is_primary": 1, "is_excluded": 1, "display_order": 0},
        {"image_id": "img-002", "url": "https://example.com/2.jpg", "is_primary": 0, "is_excluded": 0, "display_order": 1}
    ]
    insert_images(test_db, review_id, images_case2)

    export_result = export_service.export_to_csv([review_id], "naver", "test_operator")
    assert export_result["status"] == "success"
    # Should use img-002 (first non-excluded by display_order)

    # Cleanup
    conn = sqlite3.connect(test_db)
    conn.execute("DELETE FROM image_review WHERE review_id = ?", (review_id,))
    conn.commit()
    conn.close()

    # Test Case 3: All images excluded, export blocked
    images_case3 = [
        {"image_id": "img-001", "url": "https://example.com/1.jpg", "is_primary": 1, "is_excluded": 1, "display_order": 0},
        {"image_id": "img-002", "url": "https://example.com/2.jpg", "is_primary": 0, "is_excluded": 1, "display_order": 1}
    ]
    insert_images(test_db, review_id, images_case3)

    export_result = export_service.export_to_csv([review_id], "naver", "test_operator")
    assert export_result["status"] in ["error", "warning"]


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    print("🧪 Running Phase 4 End-to-End Integration Tests\n")
    print("=" * 80)

    # Run pytest with verbose output
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
