"""
PM/기획 에이전트 (Project Manager Agent) Phase 4
Fortimove 에이전트 시스템의 컨트롤 타워
- 새로운 DataResolver와 WorkflowStep 스키마 대응
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from anthropic import Anthropic
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PMAgent:
    """PM/기획 에이전트"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("PMAgent initiated without ANTHROPIC_API_KEY - tests will fail if PM execute_workflow is triggered.")
            
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

        self.system_prompt = """당신은 Fortimove Global의 수석 기획자(PM)입니다.
Phase 4 Workflow Engine 규격에 의거하여, 사용자의 지시를 정확하고 구조적인 JSON 워크플로우로 분해하십시오.

# 에이전트 목록 및 지원 스키마:
1. **daily_scout_status**: 소싱 DB 적재 상태 확인 전용 (실행 아님)
   - Input: {"region": "us|japan|korea"}
   - Output: scanned_count, saved_count
2. **product_registration**: 상품 등록 초안 생성 및 등록 판정 (ready/hold/reject)
   - Input: {"source_title": str, "source_options": list, "source_description": str}
   - Output: registration_title_ko, normalized_options_ko, registration_status, needs_human_review
3. **margin_check**: 마진/리스크 검수
   - Input: {"action": "check_margin|search_products", "product_id": int}
   - Output: action, product_data, analysis
4. **content**: 블로그 SNS 카피 (미구현)
5. **cs**: 고객 클레임 응대
   - Input: {"customer_message": str, "order_id": str, "preferred_tone": "operational"}
   - Output: cs_type, response_draft_ko
6. **image_localization**: 타오바오 중국어 번역
   - Input: {"image_files": list, "moodtone": "premium"}

# 출력 형식 (순수 JSON Object 하나만 반환)
{
  "task_type": "sourcing|product_registration|margin_check|image_localization|content_creation|cs_response|daily_scout_status|complex",
  "summary": "요청 1줄 요약",
  "workflow": [
    {
      "step_id": "step_1",
      "agent": "margin_check",
      "depends_on": [],
      "expected_status": ["COMPLETED"],
      "input_mapping": {
        "action": "literal.check_margin",
        "product_id": "user_input.structured.product_id"
      },
      "checks": {
        "required_fields": ["action", "product_id"],
        "fail_message": "상품 ID와 액션 종류가 필수로 요구됩니다."
      }
    },
    {
      "step_id": "step_2",
      "agent": "cs",
      "depends_on": ["step_1"],
      "expected_status": ["COMPLETED"],
      "input_mapping": {
        "customer_message": "user_input.raw_message",
        "order_status": "step_1.output.action"
      },
      "checks": {
        "required_fields": ["customer_message"]
      }
    }
  ]
}

# 매핑 룰 (input_mapping)
- literal.값: 상수 하드코딩 (예: "literal.check_margin")
- user_input.raw_message: 사용자 전체 텍스트 원본
- user_input.structured.키명: 사용자가 명시적으로 준 변수값
- <step_id>.output.<key>: 전 단계의 아웃풋. (주의: 해당 에이전트의 출력 스키마에 그 키가 존재하는지 판단)
"""

    def analyze_request(self, user_request: str) -> Dict:
        if not self.client:
            raise RuntimeError("Anthropic API Key Not Set")
            
        logger.info(f"📥 PM 분석 시작: {user_request[:50]}...")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": f"작업을 워크플로우 JSON으로 분해하십시오:\n\n{user_request}"}
                ]
            )
            content = response.content[0].text
            
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            # JSON 파싱 먼저 수행
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as parse_err:
                logger.error(f"❌ PM 출력 JSON 파싱 실패: {parse_err}")
                return {
                    "task_type": "error",
                    "summary": f"JSON Parse Error: {str(parse_err)}",
                    "workflow": []
                }

            # 스키마 검증
            from agent_framework import WorkflowDefinition
            try:
                validated = WorkflowDefinition(**result)
                logger.info(f"✅ PM 분석 및 스키마 검증 완벽 통과: {len(validated.workflow)}개 단계")
                return validated.model_dump()
            except Exception as schema_e:
                logger.error(f"❌ PM 출력 스키마 검증 실패: {schema_e}")
                return {
                    "task_type": "error",
                    "summary": f"Schema Validation Error: {str(schema_e)}",
                    "workflow": []
                }

        except Exception as e:
            logger.error(f"❌ PM 분석 실패: {e}")
            raise

    def execute_workflow(self, user_request: str, structured_input: Dict[str, Any] = None, auto_execute: bool = False) -> Dict:
        logger.info(f"🚀 PM 워크플로우 시작 (자동 실행: {auto_execute})")
        analysis = self.analyze_request(user_request)

        execution_plan = {
            "request": user_request,
            "analysis": analysis,
            "status": "planned" if not auto_execute else "executing",
            "workflow": analysis.get('workflow', [])
        }

        if not auto_execute:
            return execution_plan

        try:
            from agent_framework import AgentRegistry, ExecutionContext, WorkflowExecutor
            from real_agents import register_real_agents
            from cs_agent import register_cs_agent
            from product_registration_agent import register_product_registration_agent
            from approval_integration import approval_queue_hook

            registry = register_real_agents()
            register_cs_agent(registry)
            register_product_registration_agent(registry)

            context = ExecutionContext(user_request, structured_input)
            executor = WorkflowExecutor(registry)
            executor.add_post_execution_hook(approval_queue_hook)
            
            result_context = executor.execute_sequential(
                analysis.get('workflow', []),
                context
            )

            execution_plan['status'] = 'completed'
            execution_plan['execution_context'] = result_context.to_dict()
            logger.info(f"✅ 자동 실행 완료")

        except Exception as e:
            logger.error(f"❌ 자동 실행 실패: {e}")
            execution_plan['status'] = 'failed'
            execution_plan['error'] = str(e)

        return execution_plan

    def format_output(self, workflow_result: Dict) -> str:
        # Simplification for logging output presentation
        output = [f"# 📋 PM 에이전트 작업 분석 결과\n"]
        analysis = workflow_result.get('analysis', {})
        output.append(f"## 요약: {analysis.get('summary', 'N/A')}")
        output.append(f"## 유형: `{analysis.get('task_type', 'N/A')}`\n")
        
        for step in analysis.get('workflow', []):
            output.append(f"- [{step.get('step_id')}] `{step.get('agent')}`")
            output.append(f"  의존성: {step.get('depends_on')}")
            for k, v in step.get("input_mapping", {}).items():
                output.append(f"  > Input [{k}] = {v}")
                
        output.append(f"\n상태: {workflow_result.get('status', 'unknown').upper()}")
        return "\n".join(output)

if __name__ == "__main__":
    import sys
    pm = PMAgent()
    req = sys.argv[1] if len(sys.argv) > 1 else "타오바오 이미지 세팅해"
    print(pm.format_output(pm.execute_workflow(req, auto_execute=False)))
