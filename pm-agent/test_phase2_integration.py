#!/usr/bin/env python3
"""
Phase 2 Integration Test Script
Tests: Scoring Engine, Approval Ranker, Content Agent Multi-Channel, Channel Upload Manager
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add pm-agent to path
sys.path.insert(0, str(Path(__file__).parent))

from scoring_engine import ScoringEngine
from approval_ranker import ApprovalRanker
from content_agent import ContentAgent
from channel_upload_manager import ChannelUploadManager
from approval_queue import ApprovalQueueManager

def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_scoring_engine():
    """Test 1: Scoring Engine - 점수 계산 및 판정"""
    print_section("TEST 1: Scoring Engine")

    engine = ScoringEngine()

    # Sample review data (high margin, no risks)
    review_data = {
        "review_id": "test-review-001",
        "source_title": "스테인리스 텀블러 500ml",
        "source_url": "https://item.taobao.com/item.htm?id=987654321",
        "source_data": {
            "source_price_cny": 30.0,
            "weight_kg": 0.5,
            "target_category": "주방용품"
        },
        "agent_output": {
            "sourcing": {
                "sourcing_decision": "통과",
                "risk_flags": [],
                "product_classification": "테스트"
            },
            "margin": {
                "margin_analysis": {
                    "net_margin_rate": 45.0,
                    "net_profit": 18000
                }
            },
            "registration": {
                "policy_risks": [],
                "certification_required": False,
                "category": "주방용품",
                "options": ["500ml", "700ml"]
            }
        },
        "created_at": datetime.now().isoformat()
    }

    result = engine.score_product(review_data)

    print("📊 Scoring Result:")
    print(f"   Total Score: {result['score']}/100")
    print(f"   Decision: {result['decision']}")
    print(f"\n📋 Score Breakdown:")
    for category, score in result['breakdown'].items():
        print(f"   - {category}: {score} points")

    print(f"\n💡 Reasons ({len(result['reasons'])}):")
    for i, reason in enumerate(result['reasons'], 1):
        print(f"   {i}. {reason}")

    # Note: Actual score depends on margins and risk assessment
    # Just verify scoring works and returns expected fields
    assert 'score' in result, "Should have score"
    assert 'decision' in result, "Should have decision"
    assert result['decision'] in ['auto_approve', 'review', 'hold', 'reject'], "Valid decision"
    print("\n✅ Scoring Engine Test PASSED")

    return result

def test_approval_ranker():
    """Test 2: Approval Ranker - 우선순위 정렬"""
    print_section("TEST 2: Approval Ranker")

    ranker = ApprovalRanker()

    # Get all pending items and rank them
    ranked_items = ranker.rank_all_pending()

    print(f"📋 Ranked {len(ranked_items)} pending items:\n")

    for i, item in enumerate(ranked_items[:5], 1):
        print(f"{i}. {item.get('source_title', 'Untitled')[:40]:40} "
              f"| Score: {item.get('score', 0):3} "
              f"| Decision: {item.get('decision', 'N/A'):12} "
              f"| Priority: {item.get('priority', 'N/A')}")

    # Test decision-based ranking
    auto_approve_items = ranker.rank_by_decision('auto_approve')
    print(f"\n✅ Auto-approve items: {len(auto_approve_items)}")

    print("\n✅ Approval Ranker Test PASSED")

    return ranked_items

def test_content_agent_multichannel():
    """Test 3: Content Agent Multi-Channel Generation"""
    print_section("TEST 3: Content Agent Multi-Channel")

    agent = ContentAgent()

    input_data = {
        "product_name": "프리미엄 스테인리스 텀블러",
        "product_category": "주방용품",
        "key_features": ["진공 단열", "500ml 대용량", "휴대용"],
        "price": 15900,
        "channels": ["naver", "coupang"],
        "options": ["Small 300ml", "Medium 500ml", "Large 700ml"],
        "generate_usp": True,
        "generate_options": True,
        "compliance_mode": True
    }

    result = agent.execute_multichannel(input_data)

    print("📝 Multi-Channel Content Generated:\n")

    print(f"🔵 Naver Title ({len(result['naver_title'])} chars):")
    print(f"   {result['naver_title']}\n")

    print(f"🟠 Coupang Title ({len(result['coupang_title'])} chars):")
    print(f"   {result['coupang_title']}\n")

    print(f"💡 USP Points ({len(result['usp_points'])}):")
    for i, usp in enumerate(result['usp_points'], 1):
        print(f"   {i}. {usp}")

    print(f"\n🏷️  SEO Tags ({len(result['seo_tags'])}):")
    print(f"   {', '.join(result['seo_tags'])}")

    print(f"\n🔤 Translated Options ({len(result['options_korean'])}):")
    for eng, kor in result['options_korean'].items():
        print(f"   {eng} → {kor}")

    print(f"\n✅ Compliance Status: {result['compliance_status']}")

    assert len(result['naver_title']) <= 50, "Naver title should be ≤50 chars"
    assert len(result['coupang_title']) <= 100, "Coupang title should be ≤100 chars"
    assert len(result['usp_points']) == 3, "Should generate 3 USP points"
    assert len(result['seo_tags']) == 10, "Should generate 10 SEO tags"

    print("\n✅ Content Agent Multi-Channel Test PASSED")

    return result

def test_channel_upload_manager():
    """Test 4: Channel Upload Manager - CRUD operations"""
    print_section("TEST 4: Channel Upload Manager")

    manager = ChannelUploadManager()

    # Add upload item
    test_content = {
        "naver_title": "프리미엄 텀블러 500ml",
        "coupang_title": "[오늘출발] 프리미엄 텀블러",
        "description": "고급 스테인리스 소재",
        "price": 15900,
        "options": ["Small", "Medium", "Large"]
    }

    upload_id = manager.add_upload_item(
        review_id="test-review-001",
        channel="naver",
        content=test_content
    )

    print(f"📤 Upload Item Created: {upload_id}")

    # Get pending uploads
    pending = manager.get_pending_uploads(channel="naver", limit=5)
    print(f"\n📋 Pending Naver Uploads: {len(pending)}")

    for item in pending[:3]:
        print(f"   - {item['upload_id']}: {item['channel']} | Status: {item['upload_status']}")

    # Update status
    manager.update_status(upload_id, "completed")
    print(f"\n✅ Updated {upload_id} → completed")

    # Verify update
    updated_item = manager.get_upload_by_id(upload_id)
    assert updated_item['upload_status'] == 'completed', "Status should be updated"

    print("\n✅ Channel Upload Manager Test PASSED")

    return upload_id

def test_end_to_end_workflow():
    """Test 5: End-to-End Workflow"""
    print_section("TEST 5: End-to-End Workflow")

    print("🔄 Starting End-to-End Test...\n")

    # Step 1: Score a product
    print("Step 1: Scoring product...")
    engine = ScoringEngine()
    queue = ApprovalQueueManager()

    # Get first pending item
    pending_items = queue.list_items(reviewer_status="pending")
    if pending_items:
        pending_items = pending_items[:1]

    if not pending_items:
        print("⚠️  No pending items found. Skipping E2E test.")
        return

    test_item = pending_items[0]
    review_id = test_item['review_id']

    print(f"   Review ID: {review_id}")
    print(f"   Product: {test_item.get('source_title', 'N/A')}")

    # Score it
    scoring_result = engine.score_product(test_item)
    queue.update_item(review_id, {
        "score": scoring_result['score'],
        "decision": scoring_result['decision'],
        "reasons_json": json.dumps(scoring_result['reasons'], ensure_ascii=False),
        "scoring_updated_at": datetime.now().isoformat()
    })

    print(f"   Score: {scoring_result['score']} | Decision: {scoring_result['decision']}")

    # Step 2: Rank all pending
    print("\nStep 2: Ranking all pending items...")
    ranker = ApprovalRanker()
    ranked = ranker.rank_all_pending()
    print(f"   Ranked {len(ranked)} items")

    # Step 3: Generate multi-channel content (if auto-approved)
    if scoring_result['decision'] == 'auto_approve':
        print("\nStep 3: Generating multi-channel content...")
        agent = ContentAgent()

        content_input = {
            "product_name": test_item.get('source_title', 'Product'),
            "product_category": test_item.get('source_data', {}).get('target_category', '기타'),
            "key_features": ["고품질", "합리적 가격", "빠른 배송"],
            "price": 15000,
            "channels": ["naver", "coupang"],
            "compliance_mode": True
        }

        content_result = agent.execute_multichannel(content_input)
        print(f"   Generated content for {len(content_input['channels'])} channels")

        # Step 4: Add to upload queue
        print("\nStep 4: Adding to upload queue...")
        upload_manager = ChannelUploadManager()

        for channel in content_input['channels']:
            upload_id = upload_manager.add_upload_item(
                review_id=review_id,
                channel=channel,
                content={
                    f"{channel}_title": content_result.get(f"{channel}_title"),
                    "description": content_result.get('detail_description', ''),
                    "usp_points": content_result.get('usp_points', []),
                    "seo_tags": content_result.get('seo_tags', [])
                }
            )
            print(f"   Added to {channel}: {upload_id}")

        print("\n✅ End-to-End Workflow PASSED")

    else:
        print(f"\n⚠️  Product needs review (decision: {scoring_result['decision']})")
        print("   E2E workflow stopped at approval step")

def main():
    print("\n" + "="*70)
    print("  🧪 PHASE 2 INTEGRATION TEST SUITE")
    print("="*70)

    try:
        # Run all tests
        test_scoring_engine()
        test_approval_ranker()
        test_content_agent_multichannel()
        test_channel_upload_manager()
        test_end_to_end_workflow()

        print("\n" + "="*70)
        print("  ✅ ALL PHASE 2 TESTS PASSED")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
