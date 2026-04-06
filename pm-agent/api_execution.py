"""
API Execution Module
에이전트 및 워크플로우를 HTTP API로 실행할 수 있는 인터페이스 제공
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import uuid
from datetime import datetime
from pathlib import Path

from agent_framework import WorkflowExecutor, ExecutionContext, WorkflowStep
from real_agents import register_real_agents
from approval_queue import ApprovalQueueManager
from agent_status_tracker import AgentStatusTracker
from auto_approval import AutoApprovalEngine

logger = logging.getLogger(__name__)
agent_tracker = AgentStatusTracker()
auto_approval_engine = AutoApprovalEngine()

router = APIRouter()

# ============================================================
# Request/Response Models
# ============================================================

class AgentExecuteRequest(BaseModel):
    """개별 에이전트 실행 요청"""
    agent: str = Field(..., description="에이전트 이름 (sourcing, margin_check, content 등)")
    input: Dict[str, Any] = Field(..., description="에이전트 입력 데이터")
    save_to_queue: bool = Field(default=False, description="결과를 Approval Queue에 저장할지 여부")

class WorkflowExecuteRequest(BaseModel):
    """워크플로우 실행 요청"""
    workflow_name: str = Field(..., description="워크플로우 이름 (predefined 또는 custom)")
    user_input: Dict[str, Any] = Field(..., description="사용자 입력 데이터")
    save_to_queue: bool = Field(default=True, description="결과를 Approval Queue에 저장할지 여부")

class CustomWorkflowExecuteRequest(BaseModel):
    """커스텀 워크플로우 실행 요청"""
    steps: List[Dict[str, Any]] = Field(..., description="워크플로우 스텝 정의")
    user_input: Dict[str, Any] = Field(..., description="사용자 입력 데이터")
    save_to_queue: bool = Field(default=True, description="결과를 Approval Queue에 저장할지 여부")

class ExecutionResponse(BaseModel):
    """실행 결과 응답"""
    execution_id: str
    status: str  # "running", "completed", "failed"
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str

# ============================================================
# Predefined Workflows
# ============================================================

PREDEFINED_WORKFLOWS = {
    "full_product_registration": {
        "name": "전체 상품 등록 워크플로우",
        "description": "소싱 → 마진 → 등록 → 콘텐츠 → 상세페이지 리디자인 전체 자동 프로세스",
        "steps": [
            {
                "step_id": "sourcing",
                "agent": "sourcing",
                "input_mapping": {
                    "source_url": "user_input.structured.source_url",
                    "source_title": "user_input.structured.source_title",
                    "keywords": "user_input.structured.keywords",
                    "market": "user_input.structured.market"
                }
            },
            {
                "step_id": "margin",
                "agent": "margin_check",
                "depends_on": ["sourcing"],
                "expected_status": ["completed"],
                "input_mapping": {
                    "action": "literal.calculate_margin",
                    "source_country": "user_input.structured.source_country",
                    "source_price": "user_input.structured.source_price",
                    "source_price_cny": "user_input.structured.source_price_cny",
                    "weight_kg": "user_input.structured.weight_kg",
                    "target_margin_rate": "user_input.structured.target_margin_rate"
                }
            },
            {
                "step_id": "registration",
                "agent": "product_registration",
                "depends_on": ["margin"],
                "expected_status": ["completed"],
                "input_mapping": {
                    "source_title": "user_input.structured.source_title",
                    "source_options": "user_input.structured.source_options",
                    "source_description": "user_input.structured.source_description",
                    "market": "user_input.structured.market"
                }
            },
            {
                "step_id": "content",
                "agent": "content",
                "depends_on": ["registration"],
                "expected_status": ["completed"],
                "input_mapping": {
                    "product_name": "user_input.structured.source_title",
                    "product_description": "user_input.structured.source_description",
                    "content_type": "literal.product_page",
                    "compliance_mode": "literal.true"
                }
            }
        ],
        "post_actions": ["auto_approval", "score", "redesign_if_95"]
    },
    "quick_sourcing_check": {
        "name": "빠른 소싱 검증",
        "description": "소싱 → 마진 체크 → 자동 스코어링",
        "steps": [
            {
                "step_id": "sourcing",
                "agent": "sourcing",
                "input_mapping": {
                    "source_url": "user_input.structured.source_url",
                    "source_title": "user_input.structured.source_title",
                    "market": "user_input.structured.market"
                }
            },
            {
                "step_id": "margin",
                "agent": "margin_check",
                "depends_on": ["sourcing"],
                "expected_status": ["completed"],
                "input_mapping": {
                    "action": "literal.calculate_margin",
                    "source_country": "user_input.structured.source_country",
                    "source_price": "user_input.structured.source_price",
                    "source_price_cny": "user_input.structured.source_price_cny",
                    "weight_kg": "user_input.structured.weight_kg",
                    "category": "user_input.structured.category"
                }
            }
        ],
        "post_actions": ["score", "auto_approval"]
    },
    "content_only": {
        "name": "콘텐츠만 생성",
        "description": "기존 상품의 콘텐츠만 재생성",
        "steps": [
            {
                "step_id": "content",
                "agent": "content",
                "input_mapping": {
                    "product_name": "user_input.structured.product_name",
                    "product_description": "user_input.structured.product_description",
                    "key_features": "user_input.structured.key_features",
                    "price": "user_input.structured.price",
                    "content_type": "user_input.structured.content_type",
                    "compliance_mode": "literal.true"
                }
            }
        ]
    }
}

# ============================================================
# API Endpoints
# ============================================================

@router.post("/api/agents/execute", response_model=ExecutionResponse)
async def execute_agent(request: AgentExecuteRequest, background_tasks: BackgroundTasks):
    """
    개별 에이전트 실행

    예시:
    POST /api/agents/execute
    {
        "agent": "sourcing",
        "input": {
            "source_url": "https://item.taobao.com/item.htm?id=123456",
            "source_title": "휴대용 미니 블렌더"
        },
        "save_to_queue": false
    }
    """
    execution_id = f"exec-{uuid.uuid4().hex[:12]}"

    try:
        # 1. Registry에서 에이전트 가져오기
        registry = register_real_agents()

        agent = registry.get(request.agent)
        if not agent:
            # Get available agents by trying common agent names
            available_agents = []
            for name in ["sourcing", "margin_check", "product_registration", "content", "cs", "image_localization"]:
                if registry.get(name):
                    available_agents.append(name)
            raise HTTPException(
                status_code=400,
                detail=f"Agent '{request.agent}' not found. Available: {available_agents}"
            )

        # 2. 에이전트 실행 전 상태 업데이트
        agent_tracker.update_agent_status(
            agent_name=request.agent,
            status="running",
            current_task=f"Executing {execution_id}"
        )

        logger.info(f"[{execution_id}] Executing agent '{request.agent}'")
        result = agent.execute(request.input)

        # 3. 에이전트 실행 후 상태 업데이트
        if result.is_success():
            agent_tracker.update_agent_status(
                agent_name=request.agent,
                status="completed",  # "completed" status triggers success_count increment
                current_task=None
            )
            # Reset to idle after recording success
            agent_tracker.update_agent_status(
                agent_name=request.agent,
                status="idle",
                current_task=None
            )
        else:
            agent_tracker.update_agent_status(
                agent_name=request.agent,
                status="failed",  # "failed" status triggers failure_count increment
                current_task=None
            )
            # Reset to idle after recording failure
            agent_tracker.update_agent_status(
                agent_name=request.agent,
                status="idle",
                current_task=None
            )

        # 4. Approval Queue에 저장 (옵션)
        if request.save_to_queue and result.is_success():
            queue = ApprovalQueueManager()

            # source_title 추출 (입력 데이터에서)
            source_title = request.input.get('source_title') or request.input.get('product_name') or 'Unknown Product'

            # source_data 준비 (메타데이터 포함)
            source_data = {
                "execution_id": execution_id,
                "agent": request.agent,
                "source": "api_execution",
                "input": request.input
            }

            queue_id = queue.create_item(
                source_type=request.agent,
                source_title=source_title,
                agent_output=result.output,
                source_data=source_data
            )
            logger.info(f"[{execution_id}] Saved to approval queue: {queue_id}")

        # 5. 응답 생성
        if result.is_success():
            return ExecutionResponse(
                execution_id=execution_id,
                status="completed",
                message=f"Agent '{request.agent}' executed successfully",
                result=result.output,
                timestamp=datetime.now().isoformat()
            )
        else:
            return ExecutionResponse(
                execution_id=execution_id,
                status="failed",
                message=f"Agent '{request.agent}' execution failed",
                error=result.error,
                timestamp=datetime.now().isoformat()
            )

    except Exception as e:
        logger.error(f"[{execution_id}] Agent execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.post("/api/workflows/run", response_model=ExecutionResponse)
async def run_workflow(request: WorkflowExecuteRequest, background_tasks: BackgroundTasks):
    """
    사전 정의된 워크플로우 실행

    예시:
    POST /api/workflows/run
    {
        "workflow_name": "full_product_registration",
        "user_input": {
            "source_url": "https://...",
            "source_title": "상품명",
            "source_price_cny": 50.0,
            "weight_kg": 0.5
        }
    }
    """
    execution_id = f"wf-{uuid.uuid4().hex[:12]}"
    queue_id = None
    score_result = None

    try:
        # 1. Predefined workflow 가져오기
        if request.workflow_name not in PREDEFINED_WORKFLOWS:
            raise HTTPException(
                status_code=400,
                detail=f"Workflow '{request.workflow_name}' not found. Available: {list(PREDEFINED_WORKFLOWS.keys())}"
            )

        workflow_def = PREDEFINED_WORKFLOWS[request.workflow_name]

        # 2. 워크플로우 실행
        logger.info(f"[{execution_id}] Running workflow '{request.workflow_name}'")

        registry = register_real_agents()
        executor = WorkflowExecutor(registry)
        context = ExecutionContext(
            raw_message=f"Workflow: {request.workflow_name}",
            structured_input=request.user_input
        )

        final_result = executor.execute_sequential(workflow_def['steps'], context)

        # 3. Auto-Approval 평가 (Fortimove Golden Pass)
        workflow_results = {
            step['step_id']: context.get_result(step['step_id'])
            for step in workflow_def['steps']
            if context.get_result(step['step_id'])
        }

        # 워크플로우 결과를 평가용 딕셔너리로 변환
        evaluation_data = {
            step_id: {
                'output': result.output,
                'status': result.status
            }
            for step_id, result in workflow_results.items()
        }

        # 자동 승인 평가
        auto_approved, approval_reason, approval_evaluation = auto_approval_engine.evaluate(evaluation_data)

        # 4. Approval Queue에 저장 (옵션)
        if request.save_to_queue:
            queue = ApprovalQueueManager()

            # 마지막 단계 결과를 저장
            last_step = workflow_def['steps'][-1]
            last_result = context.get_result(last_step['step_id'])

            if last_result and last_result.is_success():
                # source_title 추출
                source_title = request.user_input.get('source_title') or request.user_input.get('product_name') or 'Unknown Product'

                # source_data 준비 (전체 워크플로우 결과 + 자동 승인 평가)
                # 소싱 결과에서 이미지 URL 추출
                sourcing_result = context.get_result("sourcing")
                sourcing_images = []
                if sourcing_result and sourcing_result.is_success():
                    extracted = sourcing_result.output.get("extracted_info", {})
                    sourcing_images = extracted.get("images", [])

                source_data = {
                    "execution_id": execution_id,
                    "workflow_name": request.workflow_name,
                    "source": "workflow_api",
                    "input": request.user_input,
                    "images": sourcing_images,
                    "all_results": {step['step_id']: context.get_result(step['step_id']).output
                                   for step in workflow_def['steps']
                                   if context.get_result(step['step_id'])},
                    "auto_approval": {
                        "approved": auto_approved,
                        "reason": approval_reason,
                        "evaluation": approval_evaluation
                    }
                }

                # 🏆 Golden Pass 통과 시 즉시 승인 상태로 저장
                initial_status = "approved_for_export" if auto_approved else "pending"

                queue_id = queue.create_item(
                    source_type=f"workflow:{request.workflow_name}",
                    source_title=source_title,
                    agent_output=last_result.output,
                    source_data=source_data
                )

                # 자동 승인된 경우 상태 업데이트
                if auto_approved:
                    queue.update_reviewer_status(queue_id, "approved", approval_reason)
                    logger.info(f"🏆 [{execution_id}] Golden Pass! 자동 승인: {queue_id}")
                else:
                    logger.info(f"⏸️ [{execution_id}] 수동 검토 필요: {approval_reason}")

                logger.info(f"[{execution_id}] Saved to approval queue: {queue_id}")

                # 5. Post-actions: 스코어링 + 95점 리디자인 트리거
                post_actions = workflow_def.get("post_actions", [])
                score_result = None

                if "score" in post_actions or "auto_approval" in post_actions:
                    try:
                        from scoring_engine import ScoringEngine
                        scorer = ScoringEngine()
                        review_data = {
                            "review_id": queue_id or execution_id,
                            "source_title": source_title,
                            "raw_agent_output": source_data,
                            "source_data_json": source_data,
                        }
                        score_result = scorer.score_product(review_data)
                        score_val = score_result.get('score', 0)
                        decision_val = score_result.get('decision', '')
                        logger.info(f"[{execution_id}] 스코어: {score_val}점 ({decision_val})")

                        # DB에 스코어 저장
                        if queue_id:
                            import sqlite3 as _sqlite3
                            _db = Path(__file__).parent / "data" / "approval_queue.db"
                            with _sqlite3.connect(str(_db)) as _conn:
                                _conn.execute(
                                    'UPDATE approval_queue SET score=?, decision=?, scoring_updated_at=? WHERE review_id=?',
                                    (score_val, decision_val, datetime.now().isoformat(), queue_id)
                                )
                                _conn.commit()
                            logger.info(f"[{execution_id}] 스코어 DB 저장 완료: {queue_id}")
                    except Exception as e:
                        logger.warning(f"[{execution_id}] 스코어링 실패: {e}")

                if "redesign_if_95" in post_actions and score_result:
                    score_val = score_result.get("score", 0)
                    if score_val >= 95:
                        try:
                            from redesign_queue_manager import RedesignQueueManager
                            images = request.user_input.get("images", [])
                            if images:
                                rdm = RedesignQueueManager()
                                rdsg_id = rdm.add_to_queue(
                                    source_title=source_title,
                                    source_images=images,
                                    source_type="sourcing_agent",
                                    review_id=queue_id,
                                    trigger_type="auto_score",
                                    trigger_score=score_val,
                                )
                                logger.info(f"🎨 [{execution_id}] 상세페이지 자동 리디자인 트리거: {rdsg_id} (score={score_val})")
                        except Exception as e:
                            logger.warning(f"[{execution_id}] 리디자인 트리거 실패: {e}")

        # 6. 응답 생성 (Auto-Approval 정보 포함)
        all_results = {}
        for step in workflow_def['steps']:
            step_result = context.get_result(step['step_id'])
            if step_result:
                all_results[step['step_id']] = {
                    "status": step_result.status,
                    "output": step_result.output if step_result.is_success() else None,
                    "error": step_result.error if step_result.is_failure() else None
                }

        # Auto-approval 정보 추가
        all_results['auto_approval'] = {
            "approved": auto_approved,
            "reason": approval_reason,
            "evaluation": approval_evaluation
        }

        # 스코어링 결과 추가
        if score_result:
            all_results['scoring'] = score_result

        # review_id 추가 (워크벤치에서 다음 스텝 진행에 필요)
        if queue_id:
            all_results['review_id'] = queue_id

        return ExecutionResponse(
            execution_id=execution_id,
            status="completed",
            message=f"Workflow '{request.workflow_name}' completed",
            result=all_results,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"[{execution_id}] Workflow execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@router.post("/api/workflows/custom", response_model=ExecutionResponse)
async def run_custom_workflow(request: CustomWorkflowExecuteRequest, background_tasks: BackgroundTasks):
    """
    커스텀 워크플로우 실행

    사용자가 직접 워크플로우 스텝을 정의하여 실행
    """
    execution_id = f"custom-{uuid.uuid4().hex[:12]}"

    try:
        logger.info(f"[{execution_id}] Running custom workflow with {len(request.steps)} steps")

        registry = register_real_agents()
        executor = WorkflowExecutor(registry)
        context = ExecutionContext(
            raw_message=f"Workflow: {request.workflow_name}",
            structured_input=request.user_input
        )

        final_result = executor.execute_sequential(request.steps, context)

        # Approval Queue 저장 로직 (동일)
        if request.save_to_queue:
            queue = ApprovalQueueManager()
            last_step = request.steps[-1]
            last_result = context.get_result(last_step['step_id'])

            if last_result and last_result.is_success():
                # source_title 추출
                source_title = request.user_input.get('source_title') or request.user_input.get('product_name') or 'Custom Workflow'

                # source_data 준비
                source_data = {
                    "execution_id": execution_id,
                    "workflow_type": "custom",
                    "source": "custom_workflow_api",
                    "input": request.user_input,
                    "all_results": {step['step_id']: context.get_result(step['step_id']).output
                                   for step in request.steps
                                   if context.get_result(step['step_id'])}
                }

                queue_id = queue.create_item(
                    source_type="custom_workflow",
                    source_title=source_title,
                    agent_output=last_result.output,
                    source_data=source_data
                )

        # 응답 생성
        all_results = {}
        for step in request.steps:
            step_result = context.get_result(step['step_id'])
            if step_result:
                all_results[step['step_id']] = {
                    "status": step_result.status,
                    "output": step_result.output if step_result.is_success() else None,
                    "error": step_result.error if step_result.is_failure() else None
                }

        return ExecutionResponse(
            execution_id=execution_id,
            status="completed",
            message="Custom workflow completed",
            result=all_results,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"[{execution_id}] Custom workflow error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Custom workflow failed: {str(e)}")


@router.get("/api/workflows/list")
def list_workflows():
    """사전 정의된 워크플로우 목록 조회"""
    return {
        "workflows": [
            {
                "name": name,
                "description": workflow['description'],
                "steps_count": len(workflow['steps'])
            }
            for name, workflow in PREDEFINED_WORKFLOWS.items()
        ]
    }


@router.get("/api/workflows/{workflow_name}/definition")
def get_workflow_definition(workflow_name: str):
    """특정 워크플로우 정의 조회"""
    if workflow_name not in PREDEFINED_WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found")

    return PREDEFINED_WORKFLOWS[workflow_name]
