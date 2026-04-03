#!/usr/bin/env python3
"""
Image Review Integration Tests - Phase 4
이미지 검수 시스템 통합 테스트
"""

import sys
import json
import sqlite3
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from image_review_manager import ImageReviewManager
from export_service import ExportService


# Test DB setup
DB_PATH = Path(__file__).parent / "data" / "approval_queue.db"


def setup_test_data():
    """테스트용 review 데이터 생성"""
    from approval_queue import ApprovalQueueManager

    try:
        test_review_id = "review-img-test-001"

        # Create source data with images
        source_data = {
            "product_name": "테스트 상품",
            "images": [
                "https://example.com/img1.jpg",
                "https://example.com/img2.jpg",
                "https://example.com/img3.jpg",
                "https://example.com/img4.jpg"
            ],
            "price": 29900
        }

        agent_output = {
            "result": {
                "registration_title_ko": "테스트 상품",
                "registration_status": "pending"
            }
        }

        # Delete existing test data
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM approval_queue WHERE review_id = ?', (test_review_id,))
            cursor.execute('DELETE FROM image_review WHERE review_id = ?', (test_review_id,))
            conn.commit()

        # Create review using approval_queue manager
        queue_manager = ApprovalQueueManager()

        review_id = queue_manager.create_item(
            source_type='daily_scout',
            source_title='테스트 상품',
            agent_output=agent_output,
            source_data=source_data
        )

        print(f"✅ Test data created: {review_id}")
        return review_id

    except Exception as e:
        print(f"❌ Failed to setup test data: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_get_images_initialization():
    """TEST 1: 이미지 초기화 및 조회"""
    print("\n" + "=" * 60)
    print("TEST 1: Get Images (Initialize from source_data)")
    print("=" * 60)

    manager = ImageReviewManager()
    review_id = setup_test_data()

    if not review_id:
        return False, None

    images = manager.get_images(review_id)

    if not images:
        print("❌ Failed to get images")
        return False, None

    # Verify initialization
    reviewed_images = images.get('reviewed_images', [])

    if len(reviewed_images) != 4:
        print(f"❌ Expected 4 images, got {len(reviewed_images)}")
        return False, None

    # Check first image is primary by default
    if not reviewed_images[0].get('is_primary', False):
        print("❌ First image should be primary by default")
        return False, None

    # Check no excluded images
    excluded_count = sum(1 for img in reviewed_images if img.get('is_excluded', False))
    if excluded_count != 0:
        print(f"❌ Expected 0 excluded images, got {excluded_count}")
        return False, None

    print(f"✅ Images initialized: {len(reviewed_images)} images")
    print(f"   Primary: {reviewed_images[0]['image_id']}")
    print(f"   All non-excluded: True")

    return True, review_id


def test_primary_image_uniqueness():
    """TEST 2: 대표 이미지 1개 규칙 강제"""
    print("\n" + "=" * 60)
    print("TEST 2: Primary Image Uniqueness Enforcement")
    print("=" * 60)

    manager = ImageReviewManager()
    review_id = "review-img-test-001"

    images_data = manager.get_images(review_id)
    reviewed_images = images_data.get('reviewed_images', [])

    # Try to set multiple images as primary
    reviewed_images[0]['is_primary'] = True
    reviewed_images[1]['is_primary'] = True
    reviewed_images[2]['is_primary'] = True

    result = manager.save_images(review_id, reviewed_images, operator="test")

    if result['success']:
        print("❌ Should reject multiple primary images")
        return False

    if "대표 이미지는 1개만 지정할 수 있습니다" not in result['errors'][0]:
        print(f"❌ Wrong error message: {result['errors']}")
        return False

    print(f"✅ Multiple primary images correctly rejected")
    print(f"   Error: {result['errors'][0]}")

    return True


def test_excluded_primary_rejection():
    """TEST 3: 제외된 이미지는 대표 이미지 불가"""
    print("\n" + "=" * 60)
    print("TEST 3: Excluded Image Cannot Be Primary")
    print("=" * 60)

    manager = ImageReviewManager()
    review_id = "review-img-test-001"

    images_data = manager.get_images(review_id)
    reviewed_images = images_data.get('reviewed_images', [])

    # Set first image as excluded AND primary (invalid)
    reviewed_images[0]['is_excluded'] = True
    reviewed_images[0]['is_primary'] = True
    reviewed_images[1]['is_primary'] = False

    result = manager.save_images(review_id, reviewed_images, operator="test")

    if result['success']:
        print("❌ Should reject excluded primary image")
        return False

    if "제외된 이미지는 대표 이미지로 지정할 수 없습니다" not in result['errors'][0]:
        print(f"❌ Wrong error message: {result['errors']}")
        return False

    print(f"✅ Excluded primary image correctly rejected")
    print(f"   Error: {result['errors'][0]}")

    return True


def test_set_primary_image():
    """TEST 4: 대표 이미지 변경"""
    print("\n" + "=" * 60)
    print("TEST 4: Set Primary Image (Change)")
    print("=" * 60)

    manager = ImageReviewManager()
    review_id = "review-img-test-001"

    # First, save valid state (first image primary)
    images_data = manager.get_images(review_id)
    reviewed_images = images_data.get('reviewed_images', [])

    reviewed_images[0]['is_primary'] = True
    reviewed_images[0]['is_excluded'] = False
    for i in range(1, len(reviewed_images)):
        reviewed_images[i]['is_primary'] = False

    result = manager.save_images(review_id, reviewed_images, operator="test")

    if not result['success']:
        print(f"❌ Failed to save initial state: {result['errors']}")
        return False

    # Now change primary to second image
    second_image_id = reviewed_images[1]['image_id']

    result = manager.set_primary_image(review_id, second_image_id, operator="test")

    if not result['success']:
        print(f"❌ Failed to set primary: {result['errors']}")
        return False

    # Verify change
    images_data = manager.get_images(review_id)
    reviewed_images = images_data.get('reviewed_images', [])

    primary_count = sum(1 for img in reviewed_images if img.get('is_primary', False))
    if primary_count != 1:
        print(f"❌ Expected 1 primary, got {primary_count}")
        return False

    primary_img = next((img for img in reviewed_images if img.get('is_primary', False)), None)
    if primary_img['image_id'] != second_image_id:
        print(f"❌ Wrong primary image: {primary_img['image_id']} != {second_image_id}")
        return False

    print(f"✅ Primary image changed successfully")
    print(f"   New primary: {second_image_id}")

    return True


def test_exclude_primary_auto_fallback():
    """TEST 5: 대표 이미지 제외 시 자동 fallback"""
    print("\n" + "=" * 60)
    print("TEST 5: Exclude Primary Image (Auto Fallback)")
    print("=" * 60)

    manager = ImageReviewManager()
    review_id = "review-img-test-001"

    # Get current primary
    images_data = manager.get_images(review_id)
    reviewed_images = images_data.get('reviewed_images', [])

    primary_img = next((img for img in reviewed_images if img.get('is_primary', False)), None)

    if not primary_img:
        print("❌ No primary image found")
        return False

    primary_image_id = primary_img['image_id']

    # Exclude current primary
    result = manager.exclude_image(review_id, primary_image_id, excluded=True, operator="test")

    if not result['success']:
        print(f"❌ Failed to exclude primary: {result['errors']}")
        return False

    # Verify: primary cleared, new primary selected
    images_data = manager.get_images(review_id)
    reviewed_images = images_data.get('reviewed_images', [])

    excluded_img = next((img for img in reviewed_images if img['image_id'] == primary_image_id), None)

    if not excluded_img or not excluded_img.get('is_excluded', False):
        print("❌ Image should be excluded")
        return False

    if excluded_img.get('is_primary', False):
        print("❌ Excluded image should not be primary")
        return False

    # Check new primary exists
    primary_count = sum(1 for img in reviewed_images if img.get('is_primary', False))
    if primary_count != 1:
        print(f"❌ Expected 1 primary (auto fallback), got {primary_count}")
        return False

    new_primary = next((img for img in reviewed_images if img.get('is_primary', False)), None)

    print(f"✅ Primary exclusion handled correctly")
    print(f"   Excluded: {primary_image_id}")
    print(f"   New primary (auto): {new_primary['image_id']}")

    return True


def test_get_exportable_images():
    """TEST 6: Export 가능 이미지 조회"""
    print("\n" + "=" * 60)
    print("TEST 6: Get Exportable Images")
    print("=" * 60)

    manager = ImageReviewManager()
    review_id = "review-img-test-001"

    result = manager.get_exportable_images(review_id)

    if not result['success']:
        print(f"❌ Failed to get exportable images: {result['errors']}")
        return False

    # Should have primary and non-excluded images
    if not result.get('primary_image'):
        print("❌ No primary image")
        return False

    exportable_count = result.get('exportable_count', 0)

    # We excluded 1 image earlier, so should have 3 exportable
    if exportable_count != 3:
        print(f"❌ Expected 3 exportable images, got {exportable_count}")
        return False

    print(f"✅ Exportable images retrieved")
    print(f"   Primary: {result['primary_image']['image_id']}")
    print(f"   Total exportable: {exportable_count}")

    return True


def test_export_integration():
    """TEST 7: Export와 이미지 검수 통합"""
    print("\n" + "=" * 60)
    print("TEST 7: Export Integration with Image Review")
    print("=" * 60)

    # Setup: Create approved review with reviewed content
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            review_id = "review-img-test-001"

            # Update review to approved_for_export
            cursor.execute('''
                UPDATE approval_queue
                SET review_status = 'approved_for_export',
                    generated_naver_title = '테스트 상품',
                    generated_price = 29900
                WHERE review_id = ?
            ''', (review_id,))

            conn.commit()

    except Exception as e:
        print(f"❌ Failed to setup export test: {e}")
        return False

    # Export to Naver
    export_service = ExportService()

    result = export_service.export_to_naver_csv([review_id], exported_by="test")

    if not result['success']:
        print(f"❌ Export failed: {result.get('error')}")
        return False

    csv_data = result['csv_data']

    # Verify CSV contains images
    lines = csv_data.strip().split('\n')

    if len(lines) < 2:
        print(f"❌ CSV should have header + data rows")
        return False

    # Check data row contains images
    data_row = lines[1]

    if 'https://example.com/img' not in data_row:
        print(f"❌ CSV should contain image URLs")
        return False

    print(f"✅ Export integrated with image review")
    print(f"   CSV rows: {len(lines)}")
    print(f"   Export ID: {result['export_id']}")

    return True


def run_all_tests():
    """전체 테스트 실행"""
    print("\n" + "=" * 60)
    print("IMAGE REVIEW INTEGRATION TEST SUITE")
    print("=" * 60)

    tests = [
        ("Get Images (Initialization)", test_get_images_initialization),
        ("Primary Image Uniqueness", test_primary_image_uniqueness),
        ("Excluded Primary Rejection", test_excluded_primary_rejection),
        ("Set Primary Image", test_set_primary_image),
        ("Exclude Primary Auto Fallback", test_exclude_primary_auto_fallback),
        ("Get Exportable Images", test_get_exportable_images),
        ("Export Integration", test_export_integration),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ TEST CRASHED: {test_name}")
            print(f"   Error: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} : {test_name}")

    print(f"\n  Total: {len(results)} tests, {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
