"""
CS 에이전트 (Customer Service Agent) Phase 4
최소 버전 v1: LLM 호출을 분리한 안전 지향적 응답 초안 반환 에이전트
"""
import os
import json
import logging
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel
from anthropic import Anthropic

from agent_framework import BaseAgent, TaskResult, AgentStatus

logger = logging.getLogger(__name__)

class CSInputSchema(BaseModel):
    customer_message: str
    order_id: Optional[str] = None
    order_status: Optional[str] = None
    tracking_number: Optional[str] = None
    internal_note: Optional[str] = None
    preferred_tone: str = "operational"

class CSOutputSchema(BaseModel):
    cs_type: str
    response_draft_ko: str
    confidence: float
    needs_human_review: bool
    suggested_next_action: str
    escalation_reason: Optional[str] = None

class CSAgent(BaseAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return CSInputSchema
    @property
    def output_schema(self) -> Type[BaseModel]:
        return CSOutputSchema

    def __init__(self):
        super().__init__("cs")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("CSAgent initiated without ANTHROPIC_API_KEY - tests will fail if actual execution is triggered.")
            
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    def _do_execute(self, input_model: CSInputSchema) -> Dict[str, Any]:
        """분리된 LLM 호출 로직을 실행. rule-based 확장을 위해 분리됨."""
        if not self.client:
            raise RuntimeError("API Key Missing")
        return self._generate_response(input_model)

    def _generate_response(self, input_model: CSInputSchema) -> Dict[str, Any]:
        prompt = f"""당신은 이커머스 운영팀 CS 상담원/운영자입니다.
고객 메시지를 분석하여 규격화된 JSON 응답 초안을 신중하게 작성하세요.

규칙 (가장 중요):
1. 답변은 반드시 한국어로, 정중하고 신뢰할 수 있게 작성합니다.
2. 정보가 부족하거나 입증되지 않은 부분(예: 주문상태 모름, 송장없음)에 대해 '다시 배송해드리겠습니다' 혹은 '환불해드렸습니다'와 같은 가짜 확답(Hallucination)을 절대로 하지 마십시오.
3. 정보가 부족하면 보수적으로 작성하여 "담당 부서에 확인 중입니다" 혹은 "운송장 확인 부탁드립니다"로 종결합니다.
4. cs_type은 다음 중 하나로 분류하세요: 배송지연, 오배송_누락, 재고없음, 환불요청, 주문확인, 일반문의.

입력 정보:
- 고객 메시지: {input_model.customer_message}
- 주문번호: {input_model.order_id or '알 수 없음'}
- 주문상태: {input_model.order_status or '알 수 없음'}
- 송장번호: {input_model.tracking_number or '없음'}
- 내부 메모: {input_model.internal_note or '없음'}

출력 JSON 형식 (다른 텍스트 없이 JSON Object 하나만 반환):
{{
  "cs_type": "...분류값...",
  "response_draft_ko": "...작성된 한국어 메시지...",
  "confidence": 0.9,
  "needs_human_review": true,
  "suggested_next_action": "...CS 담당자가 다음에 해야할 행동(예: 벤더사에 입고일정 문의)...",
  "escalation_reason": "...왜 위험한 사안인지(경고), 평범하면 null..."
}}"""
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip()
            
            # Markdown block cleanup
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
                
            return json.loads(raw)
        except Exception as e:
            self.logger.error(f"LLM CS Generation Error: {e}")
            raise

def register_cs_agent(registry):
    registry.register("cs", CSAgent())
