#!/usr/bin/env python3
"""
Simple Image Review Test - Phase 4
핵심 기능만 빠르게 검증
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from image_review_manager import ImageReviewManager
from approval_queue import ApprovalQueueManager

def main():
    print("\n🧪 Image Review Manager - Simple Test\n")

    # Setup
    source_data = {
        "product_name": "테스트 상품",
        "images": [
            "https://example.com/img1.jpg",
            "https://example.com/img2.jpg",
            "https://example.com/img3.jpg"
        ],
        "price": 29900
    }

    agent_output = {
        "result": {
            "registration_title_ko": "테스트 상품",
            "registration_status": "pending"
        }
    }

    # Create test review
    queue_manager = ApprovalQueueManager()
    manager = ImageReviewManager()

    review_id = queue_manager.create_item(
        source_type='daily_scout',
        source_title='테스트 상품',
        agent_output=agent_output,
        source_data=source_data
    )

    print(f"✅ Created review: {review_id[:8]}...\n")

    # Test 1: Get images (auto-initialize)
    print("TEST 1: Auto-initialize images")
    images = manager.get_images(review_id)
    reviewed_images = images['reviewed_images']
    print(f"  ✅ {len(reviewed_images)} images loaded")
    print(f"  ✅ Primary: {reviewed_images[0]['image_id']}")

    # Test 2: Reject multiple primary
    print("\nTEST 2: Reject multiple primary images")
    reviewed_images[1]['is_primary'] = True
    result = manager.save_images(review_id, reviewed_images, "test")
    assert not result['success'], "Should reject multiple primary"
    print(f"  ✅ Correctly rejected: {result['errors'][0][:50]}...")

    # Test 3: Change primary
    print("\nTEST 3: Change primary image")
    reviewed_images[0]['is_primary'] = False
    reviewed_images[1]['is_primary'] = True
    result = manager.save_images(review_id, reviewed_images, "test")
    assert result['success'], f"Should succeed: {result.get('errors')}"
    print(f"  ✅ Primary changed to image #2")

    # Test 4: Exclude primary (auto fallback)
    print("\nTEST 4: Exclude primary image")
    result = manager.exclude_image(review_id, reviewed_images[1]['image_id'], excluded=True, operator="test")
    assert result['success'], f"Should succeed: {result.get('errors')}"

    images = manager.get_images(review_id)
    reviewed_images = images['reviewed_images']
    excluded_img = reviewed_images[1]
    assert excluded_img['is_excluded'], "Image should be excluded"
    assert not excluded_img['is_primary'], "Excluded image should not be primary"

    primary_count = sum(1 for img in reviewed_images if img.get('is_primary', False))
    assert primary_count == 1, f"Should have 1 primary, got {primary_count}"
    print(f"  ✅ Primary auto-fallback worked")

    # Test 5: Get exportable
    print("\nTEST 5: Get exportable images")
    result = manager.get_exportable_images(review_id)
    assert result['success'], f"Should succeed: {result.get('errors')}"
    print(f"  ✅ {result['exportable_count']} exportable images")
    print(f"  ✅ Primary: {result['primary_image']['url'][:40]}...")

    print("\n🎉 ALL TESTS PASSED!\n")
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
