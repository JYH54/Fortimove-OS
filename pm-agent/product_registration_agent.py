"""
상품 등록 에이전트 MVP (Product Registration Agent) Phase 4
- 하이브리드 판정 방식: LLM은 오직 초안(Drafting) 텍스트 렌더링에만 사용.
- 핵심 상태(Status), 리뷰 요구(Human Review), 보류/거절(Hold/Reject)은 철저히 Rule-based로 통제.
"""
import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel, Field
from anthropic import Anthropic

from agent_framework import BaseAgent

logger = logging.getLogger(__name__)

class ProductRegistrationInputSchema(BaseModel):
    source_title: str
    source_options: Optional[List[str]] = Field(default_factory=list)
    source_attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)
    source_description: Optional[str] = None
    market: Optional[str] = None
    target_platform: Optional[str] = None
    margin_summary: Optional[Dict[str, Any]] = Field(default_factory=dict)
    compliance_flags: Optional[List[str]] = Field(default_factory=list)
    source_url: Optional[str] = None
    language_hint: Optional[str] = None
    # Retry/Revision Context
    reviewer_note: Optional[str] = None
    previous_output: Optional[Dict[str, Any]] = None

class ProductRegistrationOutputSchema(BaseModel):
    registration_title_ko: str
    normalized_options_ko: List[str]
    key_attributes_summary: Dict[str, Any]
    short_description_ko: str
    registration_status: str  # ready, hold, reject
    needs_human_review: bool
    hold_reason: Optional[str] = None
    reject_reason: Optional[str] = None
    risk_notes: List[str] = Field(default_factory=list)
    suggested_next_action: str

class ProductRegistrationAgent(BaseAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return ProductRegistrationInputSchema
    @property
    def output_schema(self) -> Type[BaseModel]:
        return ProductRegistrationOutputSchema

    def __init__(self):
        super().__init__("product_registration")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Product Registration Agent initiated without API KEY.")
            
        self.model = "claude-3-5-sonnet-20241022"

    def _do_execute(self, input_model: ProductRegistrationInputSchema) -> Dict[str, Any]:
        # 1. First-Pass Rules: Garbage Title & Basic Struct
        is_garbage, reject_reason = self._check_garbage_title(input_model.source_title)
        if is_garbage:
            return self._build_emergency_output(
                status="reject", 
                needs_human=False, 
                reject_reason=reject_reason, 
                next_action="소싱 데이터 원본 확인 및 수동 기각 처리"
            )

        ambiguous_options = self._check_ambiguous_options(input_model.source_options)
        
        # 2. Extract Draft Logic via LLM
        try:
            draft_result = self._generate_drafts(input_model)
            llm_parse_error = draft_result.pop("llm_parse_error", False)
        except Exception as e:
            logger.error(f"LLM Drafting Failed: {e}")
            return self._build_emergency_output(
                status="hold", 
                needs_human=True, 
                hold_reason=f"LLM API 에러: {str(e)}", 
                next_action="시스템/API 복구 후 재시도 또는 수동 작성"
            )

        ko_title = draft_result.get("registration_title_ko", "제목 초안 누락")
        ko_desc = draft_result.get("short_description_ko", "설명 초안 누락")

        # 3. Policy Enforcement: Sensitive Categories & Risky Wording
        combined_text_to_check = f"{input_model.source_title} {input_model.source_description or ''} {ko_title} {ko_desc}"
        is_sensitive, sensitive_reason = self._check_sensitive_category(combined_text_to_check)
        is_risky, risky_reason = self._check_risky_wording(ko_title + " " + ko_desc)

        # 4. Final Rule-Based Enforcement
        status = "ready"
        needs_human = False
        hold_reasons = []
        risk_notes = []

        if is_sensitive:
            status = "hold"
            needs_human = True
            hold_reasons.append(f"민감 카테고리 감지: {sensitive_reason}")
            risk_notes.append("민감 카테고리")

        if is_risky:
            status = "hold"
            needs_human = True
            hold_reasons.append(f"위험 문구(효능/허위) 감지: {risky_reason}")
            risk_notes.append("위험 문구 포함")

        # Compliance Check
        if input_model.compliance_flags:
            status = "hold"
            needs_human = True
            hold_reasons.append(f"Compliance flag 감지: {', '.join(input_model.compliance_flags)}")
            risk_notes.extend(input_model.compliance_flags)

        # Options Ambiguity Check
        if ambiguous_options:
            status = "hold"
            needs_human = True
            hold_reasons.append("원본 옵션 데이터에 특수문자 또는 식별 불가능한 값 포함")
            risk_notes.append("모호한 옵션")
            
        # Post-LLM Option Drift Check
        orig_opts = input_model.source_options or []
        ko_opts = draft_result.get("normalized_options_ko", [])
        if len(orig_opts) > 0 and len(orig_opts) != len(ko_opts):
            status = "hold"
            needs_human = True
            hold_reasons.append("원본 옵션 갯수와 정규화된 옵션 갯수 불일치")
            risk_notes.append("옵션 쌍 매칭 실패")

        # JSON Parse Exception Check
        if llm_parse_error:
            status = "hold"
            needs_human = True
            hold_reasons.append("LLM 초안 작성 중 JSON 파싱 오류로 인한 긴급 Fallback 작동 (원본 보존)")

        # Prepare final returns
        final_hold_reason = " | ".join(hold_reasons) if hold_reasons else None
        next_action = "마켓(스마트스토어 등) 등록 진행" if status == "ready" else "담당자 수동 리뷰 및 데이터 보완"

        return {
            "registration_title_ko": ko_title,
            "normalized_options_ko": ko_opts,
            "key_attributes_summary": draft_result.get("key_attributes_summary", {}),
            "short_description_ko": ko_desc,
            "registration_status": status,
            "needs_human_review": needs_human,
            "hold_reason": final_hold_reason,
            "reject_reason": None,
            "risk_notes": risk_notes,
            "suggested_next_action": next_action
        }

    def _check_garbage_title(self, title: str) -> (bool, Optional[str]):
        if not title or not title.strip():
            return True, "원본 상품명 누락"
        if len(title.strip()) < 3:
            return True, "원본 상품명 글자 수 미달 (3자 미만)"
        # Check if it consists only of symbols
        if re.match(r'^[\W_]+$', title.strip()):
            return True, "원본 상품명이 특수 기호로만 이루어짐"
        lower_title = title.lower()
        if "test" in lower_title or "테스트" in lower_title or "dummy" in lower_title:
            return True, "테스트/더미 데이터 더티 워드 포함"
        return False, None

    def _check_sensitive_category(self, text: str) -> (bool, str):
        # 반려동물 건강 관련성, 영양제, 의료기기 맥락 등을 간단히 체크. 강아지/고양이 단독으로는 안 잡히도록 '건강/영양'과 조합 검사하거나 강력한 단독어 검사.
        strong_keywords = ["영양제", "비타민", "의료기기", "관절약", "치료기", "수제간식", "건강기능식품"]
        for kw in strong_keywords:
            if kw in text:
                return True, f"민감 카테고리 직결 키워드({kw}) 발견"
                
        pet_words = ["강아지", "고양이", "반려동물", "펫"]
        health_words = ["관절", "건강", "면역", "염증", "피부"]
        if any(p in text for p in pet_words) and any(h in text for h in health_words):
            return True, "반려동물 건강 관련 복합 텍스트 감지"
            
        return False, ""

    def _check_risky_wording(self, generated_text: str) -> (bool, str):
        risky_terms = ["개선", "완화", "회복", "치료", "예방", "도움을 줍니다", "기능성"]
        # Allow checking all over the title and short description at once
        for term in risky_terms:
            if term in generated_text:
                return True, f"금지된 효능/의료 암시 단어 '{term}' 포함"
        return False, ""

    def _check_ambiguous_options(self, options: List[str]) -> bool:
        if not options:
            return False
        for opt in options:
            if not opt or not opt.strip():
                return True
            opt_lower = opt.lower().strip()
            if opt_lower in ["null", "none", "undefined", "?", "-", "n/a", "na"]:
                return True
            if re.match(r'^[\W_]+$', opt.strip()):
                return True
        return False

    def _generate_drafts(self, input_model: ProductRegistrationInputSchema) -> Dict[str, Any]:
        """순수 텍스트 렌더링 목적의 LLM 호출. 상태 결정권 없음."""
        if not self.client:
            raise RuntimeError("Anthropic API Key Not Configured")

        prompt = f"""당신은 이커머스 상품 관리자입니다. 주어진 원본 텍스트를 운영에 적합한 한국어 초안으로 번역 및 정규화하세요.

[필수 원칙]
1. 제목(registration_title_ko): 
   - 스팸성 키워드, 중복 단어 배제. 자연스럽고 간결하게 작성.
   - 의료적 효능 직접 과장, 허위 인증 문구 절대 포함 금지.
2. 옵션(normalized_options_ko): 
   - 불필요하게 쪼개거나 묶지 말고, 원본 갯수를 정확히 유지할 것.
   - 색상/크기/재질 등을 자연스러운 한국어로 번역.
3. 설명(short_description_ko): 
   - 가장 실용적인 기능과 스펙 2~3줄 요약.
   - 불확실한 보장("100% 효과", "당일 배송") 생성 금지.

[입력 정보]
- 원본 제목: {input_model.source_title}
- 원본 옵션: {input_model.source_options}
- 원본 설명 요약: {input_model.source_description or '없음'}
- 원본 속성: {input_model.source_attributes or '없음'}

출력(JSON Object Only):
{{
  "registration_title_ko": "정제된제목",
  "normalized_options_ko": ["옵션1", "옵션2"],
  "key_attributes_summary": {{"브랜드": "값"}},
  "short_description_ko": "정제된설명"
}}"""

        if input_model.reviewer_note and input_model.previous_output:
            # Bounded Correction Prompt Extension
            prev = input_model.previous_output
            retry_context = f"""
[REVISION REQUEST]
이전 실행 결과에 대해 리뷰어의 수정 요청이 있습니다. 아래 내용을 반영하여 초안을 다시 작성하세요.
- 리뷰어 메모: {input_model.reviewer_note}

- 이전 제목 초안: {prev.get('registration_title_ko')}
- 이전 설명 초안: {prev.get('short_description_ko')}
- 이전 옵션 초안: {prev.get('normalized_options_ko')}

이전 초안의 장점은 유지하되, [리뷰어 메모]의 지시사항을 최우선으로 반영하여 최종 JSON을 생성하세요.
"""
            prompt += retry_context

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        
        # Parse JSON reliably
        first_bracket = raw.find('{')
        last_bracket = raw.rfind('}')
        if first_bracket == -1 or last_bracket == -1:
            raise ValueError("LLM 응답에 유효한 JSON 포맷이 없습니다.")
        
        json_str = raw[first_bracket:last_bracket+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Safe Fallback to original text
            return {
                "llm_parse_error": True,
                "registration_title_ko": input_model.source_title,
                "normalized_options_ko": input_model.source_options or [],
                "key_attributes_summary": input_model.source_attributes or {},
                "short_description_ko": input_model.source_description or "설명 누락"
            }

    def _build_emergency_output(self, status: str, needs_human: bool, hold_reason: str = None, reject_reason: str = None, next_action: str = "") -> Dict[str, Any]:
        return {
            "registration_title_ko": "N/A",
            "normalized_options_ko": [],
            "key_attributes_summary": {},
            "short_description_ko": "N/A",
            "registration_status": status,
            "needs_human_review": needs_human,
            "hold_reason": hold_reason,
            "reject_reason": reject_reason,
            "risk_notes": [],
            "suggested_next_action": next_action
        }

def register_product_registration_agent(registry):
    registry.register("product_registration", ProductRegistrationAgent())
