"""
에이전트 통합 프레임워크 (Agent Integration Framework) Phase 4

목적:
- Pydantic Schema 기반 입출력
- 명시적 의존성 및 상태(depends_on, expected_status) 관리
- 데이터 매핑 엔진(DataResolver) (e.g. step_id.output.key)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type, Callable
from enum import Enum
from datetime import datetime
import json
import logging
import time
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TaskResult(BaseModel):
    agent_name: str
    status: str
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    def is_success(self) -> bool:
        return self.status == AgentStatus.COMPLETED.value
    def is_failure(self) -> bool:
        return self.status == AgentStatus.FAILED.value

class WorkflowStep(BaseModel):
    step_id: str
    agent: str
    depends_on: List[str] = Field(default_factory=list)
    expected_status: List[str] = Field(default=["COMPLETED"])
    input_mapping: Dict[str, str] = Field(default_factory=dict)
    checks: Dict[str, Any] = Field(default_factory=dict)

from pydantic import model_validator

class WorkflowDefinition(BaseModel):
    task_type: str
    summary: str
    workflow: List[WorkflowStep]

    @model_validator(mode='after')
    def validate_workflow_logic(self):
        step_ids = set()
        for step in self.workflow:
            if step.step_id in step_ids:
                raise ValueError(f"Duplicate step_id found: {step.step_id}")
            step_ids.add(step.step_id)
            
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise ValueError(f"depends_on reference '{dep}' in step '{step.step_id}' must refer to a preceding step_id")
                    
            allowed_agents = ["sourcing", "product_registration", "margin_check", "content_creation", "cs", "image_localization", "daily_scout_status", "echo"]
            if step.agent not in allowed_agents:
                raise ValueError(f"Agent '{step.agent}' is not allowed or not found in registry")
        return self

class ExecutionContext:
    def __init__(self, raw_message: str, structured_input: Dict[str, Any] = None):
        self.request = raw_message
        self.results: Dict[str, TaskResult] = {}
        self.shared_data: Dict[str, Any] = structured_input or {}
        self.execution_log: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

    def add_result(self, step_id: str, agent_name: str, result: TaskResult):
        self.results[step_id] = result
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "step_id": step_id,
            "agent": agent_name,
            "status": result.status,
            "has_error": bool(result.error)
        })
        logger.info(f"📝 결과 저장: Step [{step_id}] ({agent_name}) → {result.status}")

    def get_result(self, step_id: str) -> Optional[TaskResult]:
        return self.results.get(step_id)
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request,
            "results": {k: v.model_dump() for k, v in self.results.items()},
            "shared_data": self.shared_data,
            "execution_log": self.execution_log,
            "duration_seconds": (datetime.now() - self.start_time).total_seconds()
        }

class DataResolver:
    @staticmethod
    def resolve(mapping: Dict[str, str], context: ExecutionContext) -> Dict[str, Any]:
        resolved = {}
        for tgt_key, src_path in mapping.items():
            if src_path.startswith("literal."):
                literal_value = src_path[len("literal."):]
                # JSON 파싱 시도 (리스트, 딕셔너리, 숫자 등)
                try:
                    import json
                    resolved[tgt_key] = json.loads(literal_value)
                except:
                    # 파싱 실패 시 문자열 그대로
                    resolved[tgt_key] = literal_value
            elif src_path == "user_input.raw_message":
                resolved[tgt_key] = context.request
            elif src_path.startswith("user_input.structured."):
                key = src_path[len("user_input.structured."):]
                resolved[tgt_key] = context.shared_data.get(key)
            else:
                parts = src_path.split(".")
                if len(parts) >= 3 and parts[1] == "output":
                    step_id = parts[0]
                    key_path = parts[2:]
                    res = context.get_result(step_id)
                    if not res:
                        raise ValueError(f"Mapping source step not found: {src_path}")
                    if not res.output:
                        raise ValueError(f"Mapping source has no output: {src_path}")
                    
                    val = res.output
                    for p in key_path:
                        if isinstance(val, dict) and p in val:
                            val = val[p]
                        else:
                            raise ValueError(f"Mapping source key missing: {src_path}")
                    resolved[tgt_key] = val
                else:
                    raise ValueError(f"Invalid mapping format or unsupported source: {src_path}")
        return resolved

class BaseAgent(ABC):
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"agent.{agent_name}")
        self._check_dependencies()

    def _check_dependencies(self):
        """
        Graceful Fail: 필수 의존성 체크
        - ANTHROPIC_API_KEY 없으면 경고 로그만 출력 (시스템 전체 중단 방지)
        """
        import os
        api_key = os.getenv('ANTHROPIC_API_KEY', '')

        if not api_key or 'PLACEHOLDER' in api_key:
            self.logger.warning(
                f"⚠️ [{self.agent_name}] ANTHROPIC_API_KEY가 설정되지 않았거나 플레이스홀더입니다. "
                f"AI 기능이 제한될 수 있습니다. "
                f"설정 방법: https://docs.fortimove.com/setup-api-key"
            )
            self._api_available = False
        else:
            self._api_available = True
            self.logger.info(f"✅ [{self.agent_name}] API 키 확인됨")

    @property
    @abstractmethod
    def input_schema(self) -> Type[BaseModel]:
        pass

    @property
    @abstractmethod
    def output_schema(self) -> Type[BaseModel]:
        pass

    def execute(self, input_data: Dict[str, Any]) -> TaskResult:
        try:
            validated_input = self.input_schema(**input_data)
        except ValidationError as e:
            self.logger.error(f"Input validation failed: {str(e)}")
            return TaskResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED.value,
                error=f"Input schema error: {str(e)}",
                metadata={"input_keys": list(input_data.keys())}
            )
            
        try:
            result_data = self._do_execute(validated_input)
            validated_output = self.output_schema(**result_data)
        except Exception as e:
            self.logger.error(f"Execution failed: {str(e)}")
            return TaskResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED.value,
                error=str(e),
                metadata={"exception_type": type(e).__name__}
            )
            
        return TaskResult(
            agent_name=self.agent_name,
            status=AgentStatus.COMPLETED.value,
            output=validated_output.model_dump(),
            metadata={}
        )

    @abstractmethod
    def _do_execute(self, input_model: BaseModel) -> Dict[str, Any]:
        pass

class AgentRegistry:
    _instance = None
    _agents: Dict[str, BaseAgent] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, agent_name: str, agent: BaseAgent):
        self._agents[agent_name] = agent
        logger.info(f"✅ 에이전트 등록: {agent_name}")

    def get(self, agent_name: str) -> Optional[BaseAgent]:
        return self._agents.get(agent_name)

def register_agent(agent_id: str):
    """
    Decorator 패턴: 에이전트 클래스에 @register_agent("agent_id")를 추가하면
    자동으로 AgentRegistry에 등록됨

    사용법:
        @register_agent("sourcing")
        class SourcingAgent(BaseAgent):
            ...
    """
    def decorator(cls):
        # 클래스 정의 시점에 즉시 인스턴스 생성 및 등록
        registry = AgentRegistry()
        instance = cls()
        registry.register(agent_id, instance)
        logger.info(f"🎯 [@register_agent] {agent_id} 자동 등록 완료 ({cls.__name__})")
        return cls
    return decorator

class WorkflowExecutor:
    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or AgentRegistry()
        self.max_retries = 3
        self.retry_delay = 1.0
        self.post_execution_hooks: List[Callable] = []

        # Agent Status Tracker 초기화
        try:
            from agent_status_tracker import AgentStatusTracker
            self.agent_tracker = AgentStatusTracker()
            logger.info("✅ Agent Status Tracker 초기화 완료")
        except Exception as e:
            self.agent_tracker = None
            logger.warning(f"⚠️ Agent Status Tracker 초기화 실패: {e}")

    def add_post_execution_hook(self, hook: Callable):
        self.post_execution_hooks.append(hook)

    def execute_sequential(self, steps_data: List[Dict[str, Any]], context: ExecutionContext) -> ExecutionContext:
        logger.info(f"🚀 구조화된 워크플로우 엔진 시작: {len(steps_data)}개 단계")

        # Workflow ID 생성
        workflow_id = f"wf-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        logger.info(f"📋 Workflow ID: {workflow_id}")

        # Schema validation for workflow steps
        steps = []
        for step_dict in steps_data:
            try:
                steps.append(WorkflowStep(**step_dict))
            except ValidationError as e:
                logger.error(f"워크플로우 스펙 오류: {e}")
                context.add_result(
                    step_dict.get('step_id', 'unknown'),
                    "system",
                    TaskResult(
                        agent_name="system",
                        status=AgentStatus.FAILED.value,
                        error=f"WorkflowStep schema error: {str(e)}"
                    )
                )
                return context

        for i, step in enumerate(steps, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Step {i}/{len(steps)}: [{step.step_id}] -> {step.agent}")
            logger.info(f"{'='*60}")

            # 1. 의존성 평가 (depends_on / expected_status)
            deps_met = True
            for dep_id in step.depends_on:
                res = context.get_result(dep_id)
                if not res:
                    logger.warning(f"⚠️ 선행 단계({dep_id})를 찾을 수 없음 → 건너뜀")
                    deps_met = False
                    break
                if res.status not in step.expected_status:
                    logger.warning(f"⚠️ 선행 단계({dep_id}) 상태 불일치 (기대: {step.expected_status}, 실제: {res.status}) → 건너뜀")
                    deps_met = False
                    break

            if not deps_met:
                context.add_result(
                    step.step_id,
                    step.agent,
                    TaskResult(agent_name=step.agent, status=AgentStatus.SKIPPED.value, error="의존성 조건 미충족")
                )
                continue
                
            # 2. Input Mapping Resolver 실행
            try:
                mapped_input = DataResolver.resolve(step.input_mapping, context)
            except ValueError as e:
                logger.error(f"❌ 데이터 매핑 실패: {e}")
                context.add_result(
                    step.step_id,
                    step.agent,
                    TaskResult(agent_name=step.agent, status=AgentStatus.FAILED.value, error=str(e))
                )
                break # 파라미터 매핑 실패 시 워크플로우 붕괴 위험 (Hard Stop)
                
            # 3. Validation Checks (required_fields, fail_message)
            checks_passed = True
            if step.checks:
                req_fields = step.checks.get("required_fields", [])
                missing = [f for f in req_fields if f not in mapped_input]
                if missing:
                    fail_msg = step.checks.get("fail_message", f"필수 파라미터 누락: {missing}")
                    logger.error(f"❌ 체크(Check) 단계 실패: {fail_msg}")
                    context.add_result(
                        step.step_id,
                        step.agent,
                        TaskResult(agent_name=step.agent, status=AgentStatus.FAILED.value, error=fail_msg)
                    )
                    checks_passed = False

            if not checks_passed:
                break # Soft Stop (or break depending on design; fail fast is safer)

            # 4. Agent 실행 전 상태 업데이트
            if self.agent_tracker:
                try:
                    self.agent_tracker.update_agent_status(
                        agent_name=step.agent,
                        status="running",
                        current_task=step.step_id,
                        workflow_id=workflow_id
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Agent status update failed (before): {e}")

            # Agent 실행
            result = self._execute_agent(step.agent, mapped_input)

            # Agent 실행 후 상태 업데이트
            if self.agent_tracker:
                try:
                    final_status = "completed" if result.is_success() else "failed"
                    self.agent_tracker.update_agent_status(
                        agent_name=step.agent,
                        status=final_status,
                        current_task=None,
                        workflow_id=workflow_id
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Agent status update failed (after): {e}")

            # 5. Post-Execution Hooks (Decoupled integrations like Approval Queue)
            for hook in self.post_execution_hooks:
                try:
                    hook(step.step_id, step.agent, mapped_input, result, context)
                except Exception as hook_err:
                    logger.warning(f"⚠️ 훅 실행 오류 ({hook.__name__}): {hook_err}")

            context.add_result(step.step_id, step.agent, result)

            if result.is_failure():
                logger.error(f"❌ Step [{step.step_id}] 실패 → 워크플로우 중단")
                break

        # Workflow 완료 기록
        duration = (datetime.now() - context.start_time).total_seconds()
        logger.info(f"\n🏁 워크플로우 실행 종료 - {duration:.1f}초")

        if self.agent_tracker:
            try:
                workflow_status = "completed"
                has_failure = any(r.is_failure() for r in context.results.values() if r)
                if has_failure:
                    workflow_status = "failed"

                self.agent_tracker.record_workflow_execution(
                    workflow_id=workflow_id,
                    task_type="sequential_workflow",
                    steps=[{"step_id": s.step_id, "agent": s.agent, "status": context.get_result(s.step_id).status if context.get_result(s.step_id) else "skipped"} for s in steps],
                    status=workflow_status,
                    duration_seconds=duration,
                    error=None if workflow_status == "completed" else "워크플로우 중 일부 단계 실패"
                )
                logger.info(f"✅ Workflow 이력 기록 완료: {workflow_id}")
            except Exception as e:
                logger.warning(f"⚠️ Workflow 이력 기록 실패: {e}")

        return context

    def _execute_agent(self, agent_name: str, input_data: Dict[str, Any]) -> TaskResult:
        agent = self.registry.get(agent_name)
        if not agent:
            return TaskResult(
                agent_name=agent_name,
                status=AgentStatus.FAILED.value,
                error=f"에이전트 '{agent_name}' 객체를 레지스트리에서 찾을 수 없습니다."
            )

        for attempt in range(1, self.max_retries + 1):
            try:
                res = agent.execute(input_data)
                if res.is_success():
                    return res
                    
                if attempt < self.max_retries:
                    logger.warning(f"⚠️ {agent_name} 실패: {res.error} (재시도 대기: {self.retry_delay}s)")
                    time.sleep(self.retry_delay)
                else:
                    return res
            except Exception as e:
                if attempt == self.max_retries:
                    return TaskResult(
                        agent_name=agent_name,
                        status=AgentStatus.FAILED.value,
                        error=f"Executor exception: {str(e)}"
                    )
        
        return TaskResult(agent_name=agent_name, status=AgentStatus.FAILED.value, error="재시도 초과")
