#!/usr/bin/env python3
"""
Phase 3 Integration Test Script
Tests: Auto-Scoring Trigger, Upload Validator, Semi-Auto Uploader, Dashboard APIs
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add pm-agent to path
sys.path.insert(0, str(Path(__file__).parent))

from auto_scoring_trigger import AutoScoringTrigger
from upload_validator import UploadValidator
from semi_auto_uploader import SemiAutoUploader
from approval_queue import ApprovalQueueManager
from channel_upload_manager import ChannelUploadManager

def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_auto_scoring_trigger():
    """Test 1: Auto-Scoring Trigger"""
    print_section("TEST 1: Auto-Scoring Trigger")

    trigger = AutoScoringTrigger()

    sample_product = {
        "product_name": "프리미엄 스테인리스 텀블러 500ml",
        "region": "Korea",
        "url": "https://item.taobao.com/item.htm?id=987654321",
        "price": 15900,
        "trend_score": 85,
        "category": "주방용품",
        "source_price_cny": 30.0,
        "weight_kg": 0.5,
        "margin_rate": 0.45,
        "profit": 7000,
        "risk_flags": [],
        "policy_risks": [],
        "certification_required": False,
        "options": ["300ml", "500ml", "700ml"],
        "images": ["https://example.com/image1.jpg"]
    }

    result = trigger.process_new_product(
        product_id=f"test-product-{datetime.now().timestamp()}",
        product_data=sample_product
    )

    print(f"✅ Auto-Scoring Result:")
    print(f"   Review ID: {result['review_id']}")
    print(f"   Score: {result['score']}")
    print(f"   Decision: {result['decision']}")
    print(f"   Content Generated: {result['content_generated']}")
    print(f"   Upload Items Created: {result['upload_items_created']}")

    assert result['review_id'] is not None, "Review ID should be generated"
    assert result['score'] >= 0, "Score should be non-negative"
    assert result['decision'] in ['auto_approve', 'review', 'hold', 'reject'], "Valid decision"

    print("\n✅ Auto-Scoring Trigger Test PASSED")

    return result

def test_upload_validator():
    """Test 2: Upload Validator"""
    print_section("TEST 2: Upload Validator")

    validator = UploadValidator()

    # Test Naver validation (should pass)
    naver_content_good = {
        "title": "프리미엄 스테인리스 텀블러 500ml",  # 21 chars (OK)
        "description": "고급 소재로 제작된 텀블러입니다.",
        "price": 15900,
        "options": ["300ml", "500ml", "700ml"],
        "images": ["https://example.com/image1.jpg"]
    }

    print("📝 Test Case 1: Naver (should pass)")
    result = validator.validate("naver", naver_content_good)
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {result['errors']}")
    print(f"   Warnings: {result['warnings']}")

    assert result['valid'] == True, "Should pass Naver validation"

    # Test with prohibited word (should fail)
    naver_content_bad = {
        "title": "의료기기 인증 FDA 승인 텀블러",  # Prohibited words
        "description": "치료 효과가 있습니다.",
        "price": 15900,
        "options": [],
        "images": ["https://example.com/image1.jpg"]
    }

    print("\n📝 Test Case 2: Naver with prohibited words (should fail)")
    result = validator.validate("naver", naver_content_bad)
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {result['errors']}")

    assert result['valid'] == False, "Should fail due to prohibited words"
    assert len(result['errors']) > 0, "Should have errors"

    # Test Coupang validation (should pass)
    coupang_content_good = {
        "title": "[오늘출발] 프리미엄 텀블러 500ml",  # Has required tag
        "description": "빠른 배송",
        "price": 15900,
        "options": ["Small", "Medium"],
        "images": ["https://example.com/image1.jpg"],
        "return_policy": "7일 이내 무료 반품"
    }

    print("\n📝 Test Case 3: Coupang (should pass)")
    result = validator.validate("coupang", coupang_content_good)
    print(f"   Valid: {result['valid']}")
    print(f"   Errors: {result['errors']}")
    print(f"   Warnings: {result['warnings']}")

    assert result['valid'] == True, "Should pass Coupang validation"

    print("\n✅ Upload Validator Test PASSED")

def test_semi_auto_uploader():
    """Test 3: Semi-Auto Uploader"""
    print_section("TEST 3: Semi-Auto Uploader")

    uploader = SemiAutoUploader()
    upload_manager = ChannelUploadManager()

    # Create test upload items
    test_review_id = f"test-review-{datetime.now().timestamp()}"

    # Add upload items for testing
    naver_upload_id = upload_manager.add_upload_item(
        review_id=test_review_id,
        channel="naver",
        content={
            "title": "프리미엄 텀블러 500ml",
            "price": 15900,
            "description": "고품질 스테인리스 텀블러",
            "options": ["300ml", "500ml", "700ml"],
            "images": ["https://example.com/image1.jpg"],
            "return_policy": "7일 이내 무료 반품"
        }
    )

    coupang_upload_id = upload_manager.add_upload_item(
        review_id=test_review_id,
        channel="coupang",
        content={
            "title": "[오늘출발] 프리미엄 텀블러 500ml",
            "price": 15900,
            "description": "빠른 배송으로 보내드립니다",
            "options": ["Small", "Medium"],
            "images": ["https://example.com/image1.jpg"],
            "return_policy": "7일 이내 무료 반품"
        }
    )

    print(f"📤 Created test upload items:")
    print(f"   Naver: {naver_upload_id}")
    print(f"   Coupang: {coupang_upload_id}")

    # Test CSV export
    csv_data = uploader.export_to_csv([naver_upload_id, coupang_upload_id])
    print(f"\n📄 Generic CSV export:")
    print(f"   Size: {len(csv_data)} bytes")
    print(f"   Preview:\n{csv_data[:150]}...")

    assert len(csv_data) > 0, "CSV should not be empty"
    assert "upload_id" in csv_data, "CSV should have upload_id column"

    # Test Naver format export
    naver_csv = uploader.export_to_naver_format([naver_upload_id])
    print(f"\n📄 Naver format export:")
    print(f"   Size: {len(naver_csv)} bytes")
    print(f"   Preview:\n{naver_csv[:150]}...")

    assert len(naver_csv) > 0, "Naver CSV should not be empty"
    assert "상품명" in naver_csv, "Should have Korean headers"

    # Test Coupang format export
    coupang_csv = uploader.export_to_coupang_format([coupang_upload_id])
    print(f"\n📄 Coupang format export:")
    print(f"   Size: {len(coupang_csv)} bytes")
    print(f"   Preview:\n{coupang_csv[:150]}...")

    assert len(coupang_csv) > 0, "Coupang CSV should not be empty"

    print("\n✅ Semi-Auto Uploader Test PASSED")

def test_end_to_end_pipeline():
    """Test 4: End-to-End Pipeline"""
    print_section("TEST 4: End-to-End Pipeline")

    print("🔄 Starting End-to-End Pipeline Test...\n")

    # Step 1: Auto-Score a product
    print("Step 1: Auto-scoring product...")
    trigger = AutoScoringTrigger()

    sample_product = {
        "product_name": "고급 주방용품 세트",
        "region": "Korea",
        "url": "https://item.taobao.com/item.htm?id=999888777",
        "price": 29900,
        "trend_score": 90,
        "category": "주방용품",
        "source_price_cny": 50.0,
        "weight_kg": 1.0,
        "margin_rate": 0.40,
        "profit": 12000,
        "risk_flags": [],
        "policy_risks": [],
        "certification_required": False,
        "options": ["기본 세트", "프리미엄 세트"],
        "images": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
    }

    result = trigger.process_new_product(
        product_id=f"e2e-test-{datetime.now().timestamp()}",
        product_data=sample_product
    )

    print(f"   Review ID: {result['review_id']}")
    print(f"   Score: {result['score']}")
    print(f"   Decision: {result['decision']}")

    review_id = result['review_id']

    # Step 2: Check approval queue
    print("\nStep 2: Checking approval queue...")
    aq = ApprovalQueueManager()
    review_item = aq.get_item(review_id)

    print(f"   Status: {review_item.get('reviewer_status')}")
    print(f"   Content Status: {review_item.get('content_status')}")

    # Step 3: Get upload queue items for this review
    print("\nStep 3: Checking upload queue...")
    upload_manager = ChannelUploadManager()

    import sqlite3
    db_path = Path(__file__).parent / "data" / "approval_queue.db"

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT upload_id, channel, upload_status, validation_status
            FROM channel_upload_queue
            WHERE review_id = ?
        ''', (review_id,))

        upload_items = [dict(row) for row in cursor.fetchall()]

    print(f"   Upload items created: {len(upload_items)}")
    for item in upload_items:
        print(f"   - {item['upload_id']}: {item['channel']} ({item['upload_status']})")

    # Step 4: Validate upload items
    print("\nStep 4: Validating upload items...")
    validator = UploadValidator()

    for item in upload_items:
        upload_item = upload_manager.get_upload_by_id(item['upload_id'])
        content = json.loads(upload_item['content_json'])

        validation_result = validator.validate(item['channel'], content)

        print(f"   {item['channel']:8} - Valid: {validation_result['valid']}, "
              f"Errors: {len(validation_result['errors'])}")

    # Step 5: Export ready items
    print("\nStep 5: Exporting to CSV...")
    uploader = SemiAutoUploader()

    upload_ids = [item['upload_id'] for item in upload_items]
    csv_data = uploader.export_to_csv(upload_ids)

    print(f"   CSV size: {len(csv_data)} bytes")
    print(f"   Rows: {csv_data.count(chr(10))} lines")

    print("\n✅ End-to-End Pipeline Test PASSED")

def main():
    print("\n" + "="*70)
    print("  🧪 PHASE 3 INTEGRATION TEST SUITE")
    print("="*70)

    try:
        # Run all tests
        test_auto_scoring_trigger()
        test_upload_validator()
        test_semi_auto_uploader()
        test_end_to_end_pipeline()

        print("\n" + "="*70)
        print("  ✅ ALL PHASE 3 TESTS PASSED")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
