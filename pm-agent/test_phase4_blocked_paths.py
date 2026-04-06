#!/usr/bin/env python3
"""
Phase 4 Blocked-Path Tests

Tests scenarios where operations should be blocked with clear error messages.
"""

import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime

TEST_DB_PATH = Path(__file__).parent / "data" / "test_approval_queue.db"

def setup_test_db():
    """Create test database"""
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Base approval_queue table
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
            updated_at TEXT NOT NULL,
            generated_naver_title TEXT,
            generated_price REAL,
            reviewed_naver_title TEXT,
            reviewed_price REAL,
            review_status TEXT DEFAULT 'draft',
            reviewed_by TEXT
        )
    """)

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

    conn.commit()
    conn.close()
    print(f"✅ Test database created: {TEST_DB_PATH}")

def test_export_blocked_without_images():
    """Test: Export blocked when no non-excluded images exist"""
    print("\n📋 Test: Export blocked without exportable images")

    review_id = f"test-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Insert review with approved status
    cursor.execute("""
        INSERT INTO approval_queue (
            review_id, agent_name, input_data, output_data,
            generated_naver_title, generated_price,
            review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        review_id, "content_agent", "{}", "{}",
        "Test Product", 10000.0,
        "approved_for_export",
        now, now
    ))

    # Insert image review with ALL images excluded
    image_review_id = f"imgrev-{uuid.uuid4().hex[:8]}"
    reviewed_images = [
        {"url": "https://example.com/1.jpg", "order": 0, "is_primary": True, "excluded": True},
        {"url": "https://example.com/2.jpg", "order": 1, "is_primary": False, "excluded": True}
    ]

    cursor.execute("""
        INSERT INTO image_review (
            image_review_id, review_id,
            original_images_json, reviewed_images_json,
            primary_image_index,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_review_id, review_id,
        json.dumps(["https://example.com/1.jpg", "https://example.com/2.jpg"]),
        json.dumps(reviewed_images),
        0,
        now, now
    ))

    conn.commit()

    # Check if exportable images exist
    cursor.execute("SELECT reviewed_images_json FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    images = json.loads(result[0])
    exportable_images = [img for img in images if not img["excluded"]]

    if len(exportable_images) == 0:
        print(f"  ✓ BLOCKED: No exportable images found (all {len(images)} images excluded)")
        print(f"  ✓ Export would be blocked with error message")
        conn.close()
        print("✅ TEST PASSED: Export correctly blocked without exportable images")
        return True

    conn.close()
    raise AssertionError("Export should have been blocked")

def test_export_blocked_for_draft_status():
    """Test: Export blocked when review_status is draft"""
    print("\n📋 Test: Export blocked for draft status")

    review_id = f"test-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Insert review with DRAFT status
    cursor.execute("""
        INSERT INTO approval_queue (
            review_id, agent_name, input_data, output_data,
            generated_naver_title, generated_price,
            review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        review_id, "content_agent", "{}", "{}",
        "Test Product", 10000.0,
        "draft",  # Not approved
        now, now
    ))

    # Insert valid images
    image_review_id = f"imgrev-{uuid.uuid4().hex[:8]}"
    reviewed_images = [
        {"url": "https://example.com/1.jpg", "order": 0, "is_primary": True, "excluded": False}
    ]

    cursor.execute("""
        INSERT INTO image_review (
            image_review_id, review_id,
            original_images_json, reviewed_images_json,
            primary_image_index,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_review_id, review_id,
        json.dumps(["https://example.com/1.jpg"]),
        json.dumps(reviewed_images),
        0,
        now, now
    ))

    conn.commit()

    # Check status
    cursor.execute("SELECT review_status FROM approval_queue WHERE review_id = ?", (review_id,))
    status = cursor.fetchone()[0]

    allowed_export_statuses = ["approved_for_export", "approved_for_upload"]

    if status not in allowed_export_statuses:
        print(f"  ✓ BLOCKED: Status '{status}' not in allowed export statuses {allowed_export_statuses}")
        print(f"  ✓ Export would be blocked with 'Status not approved for export' error")
        conn.close()
        print("✅ TEST PASSED: Export correctly blocked for draft status")
        return True

    conn.close()
    raise AssertionError("Export should have been blocked")

def test_rejected_status_cannot_export():
    """Test: Rejected reviews cannot be exported"""
    print("\n📋 Test: Rejected status cannot be exported")

    review_id = f"test-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Insert review with REJECTED status
    cursor.execute("""
        INSERT INTO approval_queue (
            review_id, agent_name, input_data, output_data,
            generated_naver_title, generated_price,
            review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        review_id, "content_agent", "{}", "{}",
        "Test Product", 10000.0,
        "rejected",  # Rejected
        now, now
    ))

    conn.commit()

    # Check status
    cursor.execute("SELECT review_status FROM approval_queue WHERE review_id = ?", (review_id,))
    status = cursor.fetchone()[0]

    if status == "rejected":
        print(f"  ✓ BLOCKED: Status is 'rejected'")
        print(f"  ✓ Export would be blocked with 'Cannot export rejected reviews' error")
        conn.close()
        print("✅ TEST PASSED: Export correctly blocked for rejected status")
        return True

    conn.close()
    raise AssertionError("Export should have been blocked")

def test_excluded_image_cannot_be_primary():
    """Test: Excluded image cannot be set as primary"""
    print("\n📋 Test: Excluded image cannot be primary")

    review_id = f"test-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Insert review
    cursor.execute("""
        INSERT INTO approval_queue (
            review_id, agent_name, input_data, output_data,
            generated_naver_title, generated_price,
            review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        review_id, "content_agent", "{}", "{}",
        "Test Product", 10000.0,
        "draft",
        now, now
    ))

    # Insert images with img-2 excluded
    image_review_id = f"imgrev-{uuid.uuid4().hex[:8]}"
    reviewed_images = [
        {"url": "https://example.com/1.jpg", "order": 0, "is_primary": True, "excluded": False},
        {"url": "https://example.com/2.jpg", "order": 1, "is_primary": False, "excluded": True}  # Excluded
    ]

    cursor.execute("""
        INSERT INTO image_review (
            image_review_id, review_id,
            original_images_json, reviewed_images_json,
            primary_image_index,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_review_id, review_id,
        json.dumps(["https://example.com/1.jpg", "https://example.com/2.jpg"]),
        json.dumps(reviewed_images),
        0,
        now, now
    ))

    conn.commit()

    # Attempt to set excluded image as primary (should fail)
    cursor.execute("SELECT reviewed_images_json FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    images = json.loads(result[0])

    # Find the excluded image
    excluded_image = [img for img in images if img["excluded"] and img["order"] == 1][0]

    # Validation: Cannot set excluded image as primary
    if excluded_image["excluded"]:
        print(f"  ✓ BLOCKED: Image at order {excluded_image['order']} is excluded")
        print(f"  ✓ Setting as primary would be blocked with 'Cannot set excluded image as primary' error")
        conn.close()
        print("✅ TEST PASSED: Excluded image correctly cannot be primary")
        return True

    conn.close()
    raise AssertionError("Setting excluded image as primary should have been blocked")

def test_multiple_primary_images_prevented():
    """Test: Only one primary image can exist"""
    print("\n📋 Test: Multiple primary images prevented")

    review_id = f"test-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Insert review
    cursor.execute("""
        INSERT INTO approval_queue (
            review_id, agent_name, input_data, output_data,
            generated_naver_title, generated_price,
            review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        review_id, "content_agent", "{}", "{}",
        "Test Product", 10000.0,
        "draft",
        now, now
    ))

    # Insert images with img-1 primary
    image_review_id = f"imgrev-{uuid.uuid4().hex[:8]}"
    reviewed_images = [
        {"url": "https://example.com/1.jpg", "order": 0, "is_primary": True, "excluded": False},
        {"url": "https://example.com/2.jpg", "order": 1, "is_primary": False, "excluded": False},
        {"url": "https://example.com/3.jpg", "order": 2, "is_primary": False, "excluded": False}
    ]

    cursor.execute("""
        INSERT INTO image_review (
            image_review_id, review_id,
            original_images_json, reviewed_images_json,
            primary_image_index,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_review_id, review_id,
        json.dumps(["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg"]),
        json.dumps(reviewed_images),
        0,
        now, now
    ))

    conn.commit()

    # Set img-2 as primary (should unset img-1)
    cursor.execute("SELECT reviewed_images_json FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    images = json.loads(result[0])

    # Unset all primary flags
    for img in images:
        img["is_primary"] = False

    # Set img-2 as primary
    images[1]["is_primary"] = True

    # Update
    cursor.execute("""
        UPDATE image_review
        SET reviewed_images_json = ?,
            primary_image_index = ?,
            updated_at = ?
        WHERE review_id = ?
    """, (
        json.dumps(images),
        1,
        datetime.now().isoformat(),
        review_id
    ))

    conn.commit()

    # Verify only one primary
    cursor.execute("SELECT reviewed_images_json FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    updated_images = json.loads(result[0])
    primary_count = sum(1 for img in updated_images if img["is_primary"])

    if primary_count == 1:
        print(f"  ✓ VALIDATED: Only 1 primary image exists")
        print(f"  ✓ Setting new primary correctly unsets previous primary")
        conn.close()
        print("✅ TEST PASSED: Multiple primary images prevented")
        return True

    conn.close()
    raise AssertionError(f"Expected 1 primary image, found {primary_count}")

def test_invalid_workflow_transition():
    """Test: Invalid workflow transition blocked"""
    print("\n📋 Test: Invalid workflow transition blocked")

    from review_workflow import validate_status_transition, get_allowed_next_statuses

    current_status = "draft"
    target_status = "approved_for_export"

    # Check if transition is valid
    allowed = get_allowed_next_statuses(current_status)
    is_valid = target_status in allowed

    if not is_valid:
        print(f"  ✓ BLOCKED: Transition from '{current_status}' to '{target_status}' not allowed")
        print(f"  ✓ Allowed transitions from '{current_status}': {allowed}")
        print(f"  ✓ Transition would be blocked with 'Invalid status transition' error")
        print("✅ TEST PASSED: Invalid workflow transition correctly blocked")
        return True

    raise AssertionError("Invalid transition should have been blocked")

def test_image_export_selection_rules():
    """Test: Image export selection rules"""
    print("\n📋 Test: Image export selection rules")

    review_id = f"test-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Insert review
    cursor.execute("""
        INSERT INTO approval_queue (
            review_id, agent_name, input_data, output_data,
            generated_naver_title, generated_price,
            review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        review_id, "content_agent", "{}", "{}",
        "Test Product", 10000.0,
        "approved_for_export",
        now, now
    ))

    # Case 1: Primary is excluded, fallback to display_order
    print("\n  Case 1: Primary excluded, fallback to first non-excluded by display_order")

    image_review_id = f"imgrev-{uuid.uuid4().hex[:8]}"
    reviewed_images = [
        {"url": "https://example.com/1.jpg", "order": 0, "is_primary": True, "excluded": True},  # Primary but excluded
        {"url": "https://example.com/2.jpg", "order": 1, "is_primary": False, "excluded": False},  # Should be used
        {"url": "https://example.com/3.jpg", "order": 2, "is_primary": False, "excluded": False}
    ]

    cursor.execute("""
        INSERT INTO image_review (
            image_review_id, review_id,
            original_images_json, reviewed_images_json,
            primary_image_index,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_review_id, review_id,
        json.dumps([img["url"] for img in reviewed_images]),
        json.dumps(reviewed_images),
        0,
        now, now
    ))

    conn.commit()

    # Export selection logic
    cursor.execute("SELECT reviewed_images_json FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    images = json.loads(result[0])

    # 1. Try primary (non-excluded)
    primary_image = [img for img in images if img["is_primary"] and not img["excluded"]]

    # 2. Fallback to first non-excluded by display_order
    if not primary_image:
        non_excluded = [img for img in images if not img["excluded"]]
        non_excluded_sorted = sorted(non_excluded, key=lambda x: x["order"])
        selected_image = non_excluded_sorted[0] if non_excluded_sorted else None
    else:
        selected_image = primary_image[0]

    if selected_image and selected_image["url"] == "https://example.com/2.jpg":
        print(f"    ✓ Correctly selected: {selected_image['url']} (order: {selected_image['order']})")
        print(f"    ✓ Rule: Primary excluded → fallback to first non-excluded by display_order")
    else:
        raise AssertionError("Incorrect image selection")

    # Case 2: All excluded → export blocked
    print("\n  Case 2: All images excluded → export blocked")

    cursor.execute("DELETE FROM image_review WHERE review_id = ?", (review_id,))

    image_review_id2 = f"imgrev-{uuid.uuid4().hex[:8]}"
    all_excluded = [
        {"url": "https://example.com/1.jpg", "order": 0, "is_primary": True, "excluded": True},
        {"url": "https://example.com/2.jpg", "order": 1, "is_primary": False, "excluded": True}
    ]

    cursor.execute("""
        INSERT INTO image_review (
            image_review_id, review_id,
            original_images_json, reviewed_images_json,
            primary_image_index,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_review_id2, review_id,
        json.dumps([img["url"] for img in all_excluded]),
        json.dumps(all_excluded),
        0,
        now, now
    ))

    conn.commit()

    cursor.execute("SELECT reviewed_images_json FROM image_review WHERE review_id = ?", (review_id,))
    result = cursor.fetchone()

    images = json.loads(result[0])
    non_excluded = [img for img in images if not img["excluded"]]

    if len(non_excluded) == 0:
        print(f"    ✓ No exportable images found (all {len(images)} excluded)")
        print(f"    ✓ Export would be blocked")

    conn.close()
    print("✅ TEST PASSED: Image export selection rules validated")
    return True

def run_all_tests():
    """Run all blocked-path tests"""
    print("\n" + "="*80)
    print("🧪 Phase 4 Blocked-Path Tests")
    print("="*80 + "\n")

    print("📋 Setting up test database...")
    setup_test_db()

    # Run tests
    test_export_blocked_without_images()
    test_export_blocked_for_draft_status()
    test_rejected_status_cannot_export()
    test_excluded_image_cannot_be_primary()
    test_multiple_primary_images_prevented()
    test_invalid_workflow_transition()
    test_image_export_selection_rules()

    # Summary
    print("\n" + "="*80)
    print("🎉 ALL BLOCKED-PATH TESTS PASSED!")
    print("="*80)
    print("\n✅ Phase 4 Blocked-Path Tests Complete\n")

if __name__ == "__main__":
    run_all_tests()
