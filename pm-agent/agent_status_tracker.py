"""
Agent Status Tracker

목적:
- 5개 에이전트 (PM, Product Registration, CS, Sourcing, Pricing)의 실시간 상태 추적
- Workflow 실행 이력 저장 및 조회
- Multi-Agent Dashboard용 데이터 제공
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class AgentStatusTracker:
    def __init__(self, data_dir: str = "./pm-agent-data/agent-status"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.status_file = self.data_dir / "agent_status.json"
        self.workflow_history_file = self.data_dir / "workflow_history.json"

        # 초기화
        self._init_status_file()

    def _init_status_file(self):
        """
        에이전트 상태 파일 초기화
        SINGLE SOURCE OF TRUTH: AgentRegistry에서 동적으로 에이전트 목록 가져옴
        """
        if not self.status_file.exists():
            # AgentRegistry에서 실제 등록된 에이전트 가져오기
            agents_dict = self._get_agents_from_registry()

            initial_status = {
                "agents": agents_dict,
                "last_workflow": None
            }
            self.status_file.write_text(json.dumps(initial_status, indent=2, ensure_ascii=False))
            logger.info(f"✅ Agent status file initialized with {len(agents_dict)} agents from AgentRegistry")

        if not self.workflow_history_file.exists():
            self.workflow_history_file.write_text(json.dumps([], indent=2, ensure_ascii=False))
            logger.info("✅ Workflow history file initialized")

    def _get_agents_from_registry(self) -> Dict[str, Dict[str, Any]]:
        """
        AgentRegistry에서 실제 등록된 에이전트 목록을 가져와 상태 딕셔너리 생성
        SINGLE SOURCE OF TRUTH 구현
        """
        try:
            from agent_framework import AgentRegistry
            registry = AgentRegistry()

            agents_dict = {}
            for agent_id, agent_instance in registry._agents.items():
                # 에이전트 이름 추출 (예: SourcingAgent → Sourcing Agent)
                agent_class_name = agent_instance.__class__.__name__
                # Remove 'Agent' suffix and add spaces
                agent_display_name = agent_class_name.replace('Agent', ' Agent')

                agents_dict[agent_id] = {
                    "name": agent_display_name,
                    "status": "idle",
                    "current_task": None,
                    "last_updated": datetime.now().isoformat(),
                    "total_executions": 0,
                    "success_count": 0,
                    "failure_count": 0
                }

            logger.info(f"📋 AgentRegistry에서 {len(agents_dict)}개 에이전트 로드: {list(agents_dict.keys())}")
            return agents_dict

        except Exception as e:
            logger.error(f"❌ AgentRegistry 로드 실패: {e}, Fallback to default agents")
            # Fallback: 최소한의 기본 에이전트
            return {
                "sourcing": {"name": "Sourcing Agent", "status": "idle", "current_task": None,
                             "last_updated": datetime.now().isoformat(), "total_executions": 0,
                             "success_count": 0, "failure_count": 0},
                "pricing": {"name": "Pricing Agent", "status": "idle", "current_task": None,
                            "last_updated": datetime.now().isoformat(), "total_executions": 0,
                            "success_count": 0, "failure_count": 0},
                "content": {"name": "Content Agent", "status": "idle", "current_task": None,
                            "last_updated": datetime.now().isoformat(), "total_executions": 0,
                            "success_count": 0, "failure_count": 0},
            }

    def update_agent_status(
        self,
        agent_name: str,
        status: str,
        current_task: Optional[str] = None,
        workflow_id: Optional[str] = None
    ):
        """에이전트 상태 업데이트"""
        try:
            data = json.loads(self.status_file.read_text())

            if agent_name not in data["agents"]:
                logger.warning(f"⚠️ Unknown agent: {agent_name}")
                return

            agent_data = data["agents"][agent_name]
            agent_data["status"] = status
            agent_data["current_task"] = current_task
            agent_data["last_updated"] = datetime.now().isoformat()

            # 통계 업데이트
            if status == "running":
                agent_data["total_executions"] += 1
            elif status == "completed":
                agent_data["success_count"] += 1
            elif status == "failed":
                agent_data["failure_count"] += 1

            # Workflow ID 저장
            if workflow_id:
                data["last_workflow"] = workflow_id

            self.status_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            logger.info(f"📊 Agent status updated: {agent_name} → {status}")

        except Exception as e:
            logger.error(f"❌ Failed to update agent status: {e}")

    def get_all_agent_status(self) -> Dict[str, Any]:
        """모든 에이전트 상태 조회"""
        try:
            return json.loads(self.status_file.read_text())
        except Exception as e:
            logger.error(f"❌ Failed to get agent status: {e}")
            return {"agents": {}, "last_workflow": None}

    def get_agent_status(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """특정 에이전트 상태 조회"""
        data = self.get_all_agent_status()
        return data["agents"].get(agent_name)

    def record_workflow_execution(
        self,
        workflow_id: str,
        task_type: str,
        steps: List[Dict[str, Any]],
        status: str,
        duration_seconds: float,
        error: Optional[str] = None
    ):
        """Workflow 실행 이력 저장"""
        try:
            history = json.loads(self.workflow_history_file.read_text())

            workflow_record = {
                "workflow_id": workflow_id,
                "task_type": task_type,
                "status": status,
                "steps": steps,
                "duration_seconds": duration_seconds,
                "error": error,
                "created_at": datetime.now().isoformat()
            }

            history.insert(0, workflow_record)  # 최신순

            # 최대 100개까지만 유지
            if len(history) > 100:
                history = history[:100]

            self.workflow_history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))
            logger.info(f"📝 Workflow recorded: {workflow_id} ({status})")

        except Exception as e:
            logger.error(f"❌ Failed to record workflow: {e}")

    def get_workflow_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Workflow 실행 이력 조회"""
        try:
            history = json.loads(self.workflow_history_file.read_text())
            return history[:limit]
        except Exception as e:
            logger.error(f"❌ Failed to get workflow history: {e}")
            return []

    def get_workflow_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """특정 Workflow 조회"""
        try:
            history = json.loads(self.workflow_history_file.read_text())
            for workflow in history:
                if workflow["workflow_id"] == workflow_id:
                    return workflow
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get workflow: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """전체 통계 조회"""
        data = self.get_all_agent_status()
        history = self.get_workflow_history(limit=100)

        total_workflows = len(history)
        completed_workflows = len([w for w in history if w["status"] == "completed"])
        failed_workflows = len([w for w in history if w["status"] == "failed"])

        running_agents = [
            agent_name for agent_name, agent_data in data["agents"].items()
            if agent_data["status"] == "running"
        ]

        return {
            "total_agents": len(data["agents"]),
            "running_agents": len(running_agents),
            "running_agent_names": running_agents,
            "total_workflows": total_workflows,
            "completed_workflows": completed_workflows,
            "failed_workflows": failed_workflows,
            "agents": data["agents"]
        }
