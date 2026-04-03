import json
from approval_queue import ApprovalQueueManager
from product_registration_agent import ProductRegistrationAgent

def generate_examples():
    aq = ApprovalQueueManager()
    agent = ProductRegistrationAgent()
    agent.client = None # mock execution
    
    # Clean Ready item
    from unittest.mock import patch
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "런닝화 나이키 에어 270",
        "normalized_options_ko": ["스몰", "라지"],
        "short_description_ko": "가볍고 편안한 운동화"
    }):
        ready_res = agent.execute({
            "source_title": "Nike Air Running Shoes 270",
            "source_options": ["Small", "Large"],
            "compliance_flags": []
        }).output
        
    print("\n--- READY CASE ---")
    print(json.dumps(ready_res, ensure_ascii=False, indent=2))
        
    # Hold / Risky item
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "통증 완화 마사지기",
        "normalized_options_ko": [],
        "short_description_ko": "근육 통증을 치료하는 데 도움을 줍니다."
    }):
        hold_res = agent.execute({
            "source_title": "Muscle relaxer massage gun",
            "source_options": []
        }).output
        
    print("\n--- HOLD CASE ---")
    print(json.dumps(hold_res, ensure_ascii=False, indent=2))
    
    # Send to Queue manually to grab actual items
    # Test DB is stored locally at approval_queue.db
    r1 = aq.create_item("product_registration", "Dog Food", hold_res)
    
    aq.update_reviewer_status(r1, "needs_edit", "위험 문구 삭제 요망")
    
    with patch.object(agent, '_generate_drafts', return_value={"registration_title_ko": "관절 영양제", "normalized_options_ko": [], "short_description_ko": "튼튼한 관절"}):
        sens_res = agent.execute({"source_title": "Dog supplement", "source_options": []}).output
        r2 = aq.create_item("product_registration", "Dog supplement", sens_res)
        
    print("\n--- QUEUE ITEM 1 (needs_edit) ---")
    print(json.dumps(aq.get_item(r1), ensure_ascii=False, indent=2))
    
    print("\n--- QUEUE ITEM 2 (pending) ---")
    print(json.dumps(aq.get_item(r2), ensure_ascii=False, indent=2))
    
if __name__ == "__main__":
    generate_examples()
