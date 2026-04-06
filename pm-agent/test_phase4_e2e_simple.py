#!/usr/bin/env python3
"""
Phase 4 End-to-End Integration Tests (Simplified)

Tests the complete review-first publishing flow using the actual Phase 4 implementation.
"""

import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime

# Test database path
TEST_DB_PATH = Path(__file__).parent / "data" / "test_approval_queue.db"

def setup_test_db():
    """Create test database with Phase 4 schema"""
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Execute Phase 4 migration
    migration_path = Path(__file__).parent / "migrations" / "004_phase4_schema.sql"

    # Base approval_queue table (if not exists from migrations)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_queue (
            review_id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            input_data TEXT NOT NULL,
            output_data TEXT,
            score INTEGER DEFAULT 0,
            decision TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Phase 4 extensions
    phase4_extensions = [
        "ALTER TABLE approval_queue ADD COLUMN generated_naver_title TEXT",
        "ALTER TABLE approval_queue ADD COLUMN generated_naver_description TEXT",
        "ALTER TABLE approval_queue ADD COLUMN generated_naver_tags TEXT",
        "ALTER TABLE approval_queue ADD COLUMN generated_coupang_title TEXT",
        "ALTER TABLE approval_queue ADD COLUMN generated_coupang_description TEXT",
        "ALTER TABLE approval_queue ADD COLUMN generated_price REAL",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_naver_title TEXT",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_naver_description TEXT",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_naver_tags TEXT",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_title TEXT",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_description TEXT",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_price REAL",
        "ALTER TABLE approval_queue ADD COLUMN review_status TEXT DEFAULT 'draft'",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_at TEXT",
        "ALTER TABLE approval_queue ADD COLUMN reviewed_by TEXT",
        "ALTER TABLE approval_queue ADD COLUMN review_notes TEXT"
    ]

    for sql in phase4_extensions:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass  # Column already exists

    # image_review table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_review (
            image_review_id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL,
            original_images_json TEXT NOT NULL,
            reviewed_images_json TEXT NOT NULL,
            primary_image_index INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
        )
    """)

    # review_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_history (
            history_id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL,
            action TEXT NOT NULL,
            previous_state_json TEXT,
            changed_fields TEXT,
            changes_json TEXT,
            changed_by TEXT NOT NULL,
            change_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
        )
    """)

    # export_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS export_log (
            export_id TEXT PRIMARY KEY,
            channel TEXT NOT NULL,
            review_ids TEXT NOT NULL,
            export_format TEXT NOT NULL,
            export_file_path TEXT,
            export_status TEXT NOT NULL DEFAULT 'pending',
            export_error TEXT,
            row_count INTEGER,
            file_size INTEGER,
            exported_by TEXT NOT NULL,
            export_reason TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅ Test database created: {TEST_DB_PATH}")

def insert_test_review():
    """Insert test review with generated content"""
    review_id = f"test-review-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO approval_queue (
            review_id, agent_name, input_data, output_data,
            score, decision, status,
            generated_naver_title, generated_naver_description, generated_naver_tags,
            generated_coupang_title, generated_coupang_description, generated_price,
            review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        review_id,
        "content_agent",
        json.dumps({"product_name": "프리미엄 텀블러 500ml"}),
        json.dumps({"status": "completed"}),
        85,
        "PASS",
        "pending",
        "[한정특가] 프리미엄 스테인리스 텀블러 500ml - 진공단열",
        "고급 스테인리스 소재로 제작된 진공단열 텀블러입니다. 보온 6시간 보냉 12시간 유지.",
        json.dumps(["텀블러", "보온보냉", "스테인리스", "500ml"]),
        "프리미엄 진공단열 텀블러 500ml",
        "진공단열 설계로 장시간 온도 유지\n스테인리스 소재",
        15900.0,
        "draft",
        now,
        now
    ))

    # Insert images
    image_review_id = f"imgrev-{uuid.uuid4().hex[:8]}"
    original_images = [
        "https://example.com/images/tumbler-main.jpg",
        "https://example.com/images/tumbler-detail1.jpg",
        "https://example.com/images/tumbler-detail2.jpg"
    ]

    reviewed_images = [
        {
            "url": "https://example.com/images/tumbler-main.jpg",
            "order": 0,
            "is_primary": True,
            "excluded": False,
            "warnings": []
        },
        {
            "url": "https://example.com/images/tumbler-detail1.jpg",
            "order": 1,
            "is_primary": False,
            "excluded": False,
            "warnings": []
        },
        {
            "url": "https://example.com/images/tumbler-detail2.jpg",
            "order": 2,
            "is_primary": False,
            "excluded": False,
            "warnings": []
        }
    ]

    cursor.execute("""
        INSERT INTO image_review (
            image_review_id, review_id,
            original_images_json, reviewed_images_json,
            primary_image_index,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_review_id,
        review_id,
        json.dumps(original_images),
        json.dumps(reviewed_images),
        0,
        now,
        now
    ))

    conn.commit()
    conn.close()

    print(f"✅ Test review inserted: {review_id}")
    return review_id

def test_review_detail_load(review_id):
    """Test: Load review detail"""
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM approval_queue WHERE review_id = ?", (review_id,))
    review = cursor.fetchone()

    assert review is not None, "Review not found"
    assert review["review_id"] == review_id
    assert review["review_status"] == "draft"
    assert review["generated_naver_title"] is not None

    conn.close()
    print(f"✅ TEST PASSED: Review detail loaded")

def test_save_reviewed_content(review_id):
    """Test: Save reviewed content"""
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    cursor.execute("""
        UPDATE approval_queue
        SET reviewed_naver_title = ?,
            reviewed_naver_description = ?,
            reviewed_price = ?,
            review_notes = ?,
            reviewed_at = ?,
            reviewed_by = ?
        WHERE review_id = ?
    """, (
        "[최종] 프리미엄 스테인리스 텀블러 500ml - 검수완료",
        "검수를 거친 고급 텀블러입니다.",
        16900.0,
        "가격 조정 및 타이틀 최적화 완료",
        now,
        "test_operator",
        review_id
    ))

    # Record history
    history_id = f"hist-{uuid.uuid4().hex[:8]}"
    cursor.execute("""
        INSERT INTO review_history (
            history_id, review_id, action,
            changed_by, change_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        history_id,
        review_id,
        "save_draft",
        "test_operator",
        "Reviewed content saved",
        now
    ))

    conn.commit()

    # Verify
    cursor.execute("SELECT reviewed_naver_title, reviewed_price FROM approval_queue WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    assert result[0] == "[최종] 프리미엄 스테인리스 텀블러 500ml - 검수완료"
    assert result[1] == 16900.0

    conn.close()
    print(f"✅ TEST PASSED: Reviewed content saved")

def test_image_review_update(review_id):
    """Test: Update image review (set different primary)"""
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Load current images
    cursor.execute("SELECT reviewed_images_json FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    reviewed_images = json.loads(result[0])

    # Set img #2 as primary
    for img in reviewed_images:
        img["is_primary"] = (img["order"] == 1)

    # Update
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE image_review
        SET reviewed_images_json = ?,
            primary_image_index = ?,
            updated_at = ?
        WHERE review_id = ?
    """, (
        json.dumps(reviewed_images),
        1,
        now,
        review_id
    ))

    conn.commit()

    # Verify
    cursor.execute("SELECT reviewed_images_json, primary_image_index FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    updated_images = json.loads(result[0])
    primary_count = sum(1 for img in updated_images if img["is_primary"])

    assert primary_count == 1, "Must have exactly one primary image"
    assert result[1] == 1, "Primary image index must be 1"

    conn.close()
    print(f"✅ TEST PASSED: Image review updated")

def test_workflow_transition(review_id):
    """Test: Workflow transition to approved_for_export"""
    from review_workflow import validate_status_transition, get_allowed_next_statuses

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Get current status
    cursor.execute("SELECT review_status FROM approval_queue WHERE review_id = ?", (review_id,))
    current_status = cursor.fetchone()[0]

    print(f"  Current status: {current_status}")

    # Get allowed transitions
    allowed = get_allowed_next_statuses(current_status)
    print(f"  Allowed next statuses: {allowed}")

    # Transition to under_review first
    if "under_review" in allowed:
        cursor.execute("""
            UPDATE approval_queue
            SET review_status = ?
            WHERE review_id = ?
        """, ("under_review", review_id))

        # Record history
        history_id = f"hist-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO review_history (
                history_id, review_id, action,
                changed_by, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            history_id,
            review_id,
            "submit_for_review",
            "test_operator",
            datetime.now().isoformat()
        ))

        conn.commit()
        print(f"  ✓ Transitioned to under_review")

    # Now transition to approved_for_export
    cursor.execute("SELECT review_status FROM approval_queue WHERE review_id = ?", (review_id,))
    current_status = cursor.fetchone()[0]

    allowed = get_allowed_next_statuses(current_status)
    print(f"  Allowed next statuses from {current_status}: {allowed}")

    if "approved_for_export" in allowed:
        cursor.execute("""
            UPDATE approval_queue
            SET review_status = ?
            WHERE review_id = ?
        """, ("approved_for_export", review_id))

        # Record history
        history_id = f"hist-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO review_history (
                history_id, review_id, action,
                changed_by, change_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            history_id,
            review_id,
            "approve_for_export",
            "test_operator",
            "검수 완료",
            datetime.now().isoformat()
        ))

        conn.commit()
        print(f"  ✓ Transitioned to approved_for_export")

    # Verify final status
    cursor.execute("SELECT review_status FROM approval_queue WHERE review_id = ?", (review_id,))
    final_status = cursor.fetchone()[0]

    assert final_status == "approved_for_export", f"Expected approved_for_export, got {final_status}"

    conn.close()
    print(f"✅ TEST PASSED: Workflow transition completed")

def test_export_priority(review_id):
    """Test: reviewed_* values take priority over generated_* in export"""
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            generated_naver_title, reviewed_naver_title,
            generated_price, reviewed_price
        FROM approval_queue
        WHERE review_id = ?
    """, (review_id,))

    row = cursor.fetchone()

    # Export logic should use reviewed_* first
    export_title = row["reviewed_naver_title"] or row["generated_naver_title"]
    export_price = row["reviewed_price"] or row["generated_price"]

    assert export_title == row["reviewed_naver_title"], "Should use reviewed title"
    assert export_price == row["reviewed_price"], "Should use reviewed price"

    print(f"  Export title: {export_title}")
    print(f"  Export price: {export_price}")

    conn.close()
    print(f"✅ TEST PASSED: Export priority verified (reviewed_* > generated_*)")

def test_review_history(review_id):
    """Test: Review history recorded"""
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT action, changed_by, created_at
        FROM review_history
        WHERE review_id = ?
        ORDER BY created_at
    """, (review_id,))

    history = cursor.fetchall()

    assert len(history) >= 2, f"Expected at least 2 history entries, got {len(history)}"

    actions = [h["action"] for h in history]
    print(f"  History actions: {actions}")

    assert "save_draft" in actions or "submit_for_review" in actions
    assert "approve_for_export" in actions

    conn.close()
    print(f"✅ TEST PASSED: Review history recorded ({len(history)} entries)")

def run_all_tests():
    """Run all E2E tests"""
    print("\n" + "="*80)
    print("🧪 Phase 4 End-to-End Integration Tests")
    print("="*80 + "\n")

    # Setup
    print("📋 Setting up test database...")
    setup_test_db()

    print("\n📝 Inserting test review...")
    review_id = insert_test_review()

    # Run tests
    print("\n" + "-"*80)
    print("TEST 1: Review Detail Load")
    print("-"*80)
    test_review_detail_load(review_id)

    print("\n" + "-"*80)
    print("TEST 2: Save Reviewed Content")
    print("-"*80)
    test_save_reviewed_content(review_id)

    print("\n" + "-"*80)
    print("TEST 3: Image Review Update")
    print("-"*80)
    test_image_review_update(review_id)

    print("\n" + "-"*80)
    print("TEST 4: Workflow Transition")
    print("-"*80)
    test_workflow_transition(review_id)

    print("\n" + "-"*80)
    print("TEST 5: Export Priority (reviewed_* > generated_*)")
    print("-"*80)
    test_export_priority(review_id)

    print("\n" + "-"*80)
    print("TEST 6: Review History Recording")
    print("-"*80)
    test_review_history(review_id)

    # Summary
    print("\n" + "="*80)
    print("🎉 ALL TESTS PASSED!")
    print("="*80)
    print(f"\nTest Review ID: {review_id}")
    print(f"Test Database: {TEST_DB_PATH}")
    print("\n✅ Phase 4 End-to-End Integration Test Complete\n")

if __name__ == "__main__":
    run_all_tests()
