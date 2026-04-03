import json
import pytest
from unittest.mock import patch

from product_registration_agent import ProductRegistrationAgent, ProductRegistrationInputSchema

@pytest.fixture
def agent():
    return ProductRegistrationAgent()

def test_reject_garbage_title(agent):
    # Empty title
    res1 = agent.execute({"source_title": "   "})
    assert res1.is_success()  # The executor wraps return from _do_execute safely
    assert res1.output["registration_status"] == "reject"
    assert "상품명 누락" in res1.output["reject_reason"]

    # Symbols only
    res2 = agent.execute({"source_title": "!!! @@@ ~~~"})
    assert res2.output["registration_status"] == "reject"
    assert "특수 기호" in res2.output["reject_reason"]
    
    # Dirty word
    res3 = agent.execute({"source_title": "new product test_1"})
    assert res3.output["registration_status"] == "reject"
    assert "테스트" in res3.output["reject_reason"] or "test" in res1.output.get("reject_reason", "")

def test_hold_ambiguous_options(agent):
    # Missing option translations trigger hold via rule pre-check
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "정상 이름",
        "normalized_options_ko": ["빨강", "파랑", "null"],
        "short_description_ko": "정상 설명"
    }):
        # 'undefined' in source_options -> hold
        res = agent.execute({
            "source_title": "Normal Product",
            "source_options": ["red", "undefined", "blue"]
        })
        assert res.output["registration_status"] == "hold"
        assert res.output["needs_human_review"] is True
        assert "특수문자 또는 식별 불가능한 값" in res.output["hold_reason"]

def test_hold_compliance_flag(agent):
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "건강기능식품 영양제",
        "normalized_options_ko": [],
        "short_description_ko": "좋음"
    }):
        res = agent.execute({
            "source_title": "Vitamin C",
            "compliance_flags": ["MEDICAL_CLAIM", "RESTRICTED_INGREDIENT"]
        })
        assert res.output["registration_status"] == "hold"
        assert res.output["needs_human_review"] is True
        assert "MEDICAL_CLAIM" in res.output["hold_reason"]

def test_happy_path_ready(agent):
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "런닝화 나이키 에어 270",
        "normalized_options_ko": ["스몰", "라지"],
        "short_description_ko": "가볍고 편안한 운동화"
    }):
        res = agent.execute({
            "source_title": "Nike Air Running Shoes 270",
            "source_options": ["Small", "Large"],
            "compliance_flags": []
        })
        assert res.output["registration_status"] == "ready"
        assert res.output["needs_human_review"] is False
        assert res.output["hold_reason"] is None
        assert res.output["reject_reason"] is None
        assert res.output["normalized_options_ko"] == ["스몰", "라지"]

def test_llm_json_parse_fallback(agent):
    res = agent.execute({
        "source_title": "Valid Product",
        "source_options": ["Opt1"],
    })
    assert res.output["registration_status"] == "hold"
    assert res.output["needs_human_review"] is True
    assert "LLM API 에러" in res.output["hold_reason"]

def test_hold_sensitive_category(agent):
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "관절 영양제 강아지용",
        "normalized_options_ko": [],
        "short_description_ko": "튼튼한 관절"
    }):
        res = agent.execute({
            "source_title": "Dog Joint Supplement Vitamin",
            "source_options": [],
        })
        # "강아지" + "관절", plus "영양제" directly.
        assert res.output["registration_status"] == "hold"
        assert res.output["needs_human_review"] is True
        assert "민감 카테고리" in res.output["risk_notes"]

def test_hold_risky_wording(agent):
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "허리디스크 완화 및 관절 통증 치료 마사지기",
        "normalized_options_ko": ["본체"],
        "short_description_ko": "통증을 개선하고 회복에 도움을 줍니다."
    }):
        res = agent.execute({
            "source_title": "Back pain massage tool",
            "source_options": ["Body"],
        })
        assert res.output["registration_status"] == "hold"
        assert res.output["needs_human_review"] is True
        assert "위험 문구 포함" in res.output["risk_notes"]
        assert "위험" in res.output["hold_reason"]

def test_missing_source_options_safe(agent):
    with patch.object(agent, '_generate_drafts', return_value={
        "registration_title_ko": "스마트폰 거치대",
        "normalized_options_ko": [],
        "short_description_ko": "튼튼한 거치대"
    }):
        # NO source_options passed
        res = agent.execute({
            "source_title": "Smartphone mount holder stand"
        })
        assert res.output["registration_status"] == "ready"
        assert res.output["needs_human_review"] is False
