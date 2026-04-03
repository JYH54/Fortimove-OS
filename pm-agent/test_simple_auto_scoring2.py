#!/usr/bin/env python3
"""Simple Auto-Scoring Test v2"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from scoring_engine import ScoringEngine
from approval_queue import ApprovalQueueManager
import json
from datetime import datetime

# Test data
sample_product = {
    "product_name": "프리미엄 텀블러 500ml",
    "region": "Korea",
    "url": "https://item.taobao.com/item.htm?id=987654321",
    "price": 15900,
    "category": "주방용품",
    "source_price_cny": 30.0,
    "weight_kg": 0.5,
    "margin_rate": 0.45,
    "profit": 7000,
    "risk_flags": [],
    "policy_risks": [],
    "certification_required": False,
    "options": ["300ml", "500ml"],
    "images": ["https://example.com/image1.jpg"]
}

# Build review data (include review_id for scoring_engine)
review_data = {
    "review_id": "test-001",  # Required by scoring_engine
    "source_title": sample_product['product_name'],
    "source_data": sample_product,
    "agent_output": {
        "sourcing": {"sourcing_decision": "통과"},
        "margin": {"margin_analysis": {"net_margin_rate": 0.45}},
        "registration": {
            "policy_risks": [],
            "certification_required": False,
            "options": ["300ml", "500ml"]
        }
    }
}

# Score it
print("1. Scoring product...")
engine = ScoringEngine()
result = engine.score_product(review_data)

print(f"   Score: {result['score']}")
print(f"   Decision: {result['decision']}")
print(f"   Reasons: {len(result['reasons'])} reasons")

# Save to approval queue
print("\n2. Creating approval queue item...")
aq = ApprovalQueueManager()

agent_output = {
    "registration_title_ko": sample_product['product_name'],
    "registration_status": "pending",
    "needs_human_review": True,
    "suggested_next_action": f"Review score: {result['score']}",
    "risk_notes": result['reasons']
}

review_id = aq.create_item(
    source_type="wellness_products",
    source_title=sample_product['product_name'],
    agent_output=agent_output,
    source_data=sample_product
)

print(f"   Created review: {review_id}")

# Update with Phase 3 fields
print("\n3. Updating with Phase 3 fields...")
aq.update_item(review_id, {
    "score": result['score'],
    "decision": result['decision'],
    "reasons_json": json.dumps(result['reasons'], ensure_ascii=False),
    "scoring_updated_at": datetime.now().isoformat()
})

print(f"   Updated successfully")

# Verify
print("\n4. Verifying...")
item = aq.get_item(review_id)
print(f"   Review ID: {review_id}")
print(f"   Score: {item.get('score', 'N/A')}")
print(f"   Decision: {item.get('decision', 'N/A')}")
print(f"   Status: {item.get('reviewer_status', 'N/A')}")

print("\n✅ Phase 3 Auto-Scoring Flow Test PASSED")
