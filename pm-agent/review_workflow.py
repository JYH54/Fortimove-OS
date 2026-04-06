"""
Review Workflow State Machine - Phase 4
운영자 검수 워크플로우의 상태 전환 규칙을 관리합니다.
"""

import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# DB path
DB_PATH = Path(__file__).parent / "data" / "approval_queue.db"


@dataclass
class TransitionResult:
    """상태 전환 검증 결과"""
    allowed: bool
    current_status: str
    new_status: str
    error_message: Optional[str] = None
    allowed_next_states: Optional[List[str]] = None


class ReviewWorkflow:
    """
    Review Workflow State Machine

    상태 전환 규칙:
    - draft → [under_review, hold]
    - under_review → [approved_for_export, hold, rejected]
    - approved_for_export → [approved_for_upload, hold]
    - approved_for_upload → [hold]
    - hold → [under_review, rejected]
    - rejected → [] (terminal state)
    """

    def __init__(self):
        self.status_config = {}
        self.load_status_config()

    def load_status_config(self):
        """review_status_config 테이블에서 상태 설정 로드"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT status, display_name, description, color, allowed_next_states, active
                    FROM review_status_config
                    WHERE active = 1
                ''')

                rows = cursor.fetchall()

                for row in rows:
                    status = row['status']
                    allowed_next_states_json = row['allowed_next_states']

                    # Parse allowed_next_states JSON
                    try:
                        allowed_next_states = json.loads(allowed_next_states_json) if allowed_next_states_json else []
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON for status {status}: {allowed_next_states_json}")
                        allowed_next_states = []

                    self.status_config[status] = {
                        'display_name': row['display_name'],
                        'description': row['description'],
                        'color': row['color'],
                        'allowed_next_states': allowed_next_states,
                        'active': row['active']
                    }

                logger.info(f"✅ Loaded {len(self.status_config)} status configurations")

        except sqlite3.Error as e:
            logger.error(f"Failed to load status config: {e}")
            # Fallback to hardcoded config
            self._load_fallback_config()

    def _load_fallback_config(self):
        """DB 로드 실패 시 하드코딩된 설정 사용"""
        self.status_config = {
            'draft': {
                'display_name': 'Draft',
                'allowed_next_states': ['under_review', 'hold'],
                'color': 'gray',
                'active': 1
            },
            'under_review': {
                'display_name': 'Under Review',
                'allowed_next_states': ['approved_for_export', 'hold', 'rejected'],
                'color': 'blue',
                'active': 1
            },
            'approved_for_export': {
                'display_name': 'Approved for Export',
                'allowed_next_states': ['approved_for_upload', 'hold'],
                'color': 'green',
                'active': 1
            },
            'approved_for_upload': {
                'display_name': 'Approved for Upload',
                'allowed_next_states': ['hold'],
                'color': 'teal',
                'active': 1
            },
            'hold': {
                'display_name': 'On Hold',
                'allowed_next_states': ['under_review', 'rejected'],
                'color': 'yellow',
                'active': 1
            },
            'rejected': {
                'display_name': 'Rejected',
                'allowed_next_states': [],
                'color': 'red',
                'active': 1
            }
        }
        logger.warning("Using fallback status config")

    def can_transition(self, current_status: str, new_status: str) -> bool:
        """
        상태 전환 가능 여부 확인 (True/False만 반환)

        Args:
            current_status: 현재 상태
            new_status: 전환하려는 상태

        Returns:
            bool: 전환 가능 여부
        """
        # 동일 상태로의 전환은 항상 허용 (no-op)
        if current_status == new_status:
            return True

        # 현재 상태가 설정에 없으면 불허
        if current_status not in self.status_config:
            logger.warning(f"Unknown current status: {current_status}")
            return False

        # 새 상태가 설정에 없으면 불허
        if new_status not in self.status_config:
            logger.warning(f"Unknown new status: {new_status}")
            return False

        # 허용된 다음 상태 목록에 있는지 확인
        allowed_next_states = self.status_config[current_status]['allowed_next_states']
        return new_status in allowed_next_states

    def validate_transition(self, current_status: str, new_status: str) -> TransitionResult:
        """
        상태 전환 검증 및 상세 결과 반환

        Args:
            current_status: 현재 상태
            new_status: 전환하려는 상태

        Returns:
            TransitionResult: 검증 결과 (allowed, error_message, allowed_next_states 포함)
        """
        # 동일 상태로의 전환
        if current_status == new_status:
            return TransitionResult(
                allowed=True,
                current_status=current_status,
                new_status=new_status,
                error_message=None
            )

        # 현재 상태가 설정에 없음
        if current_status not in self.status_config:
            return TransitionResult(
                allowed=False,
                current_status=current_status,
                new_status=new_status,
                error_message=f"Unknown current status: {current_status}",
                allowed_next_states=[]
            )

        # 새 상태가 설정에 없음
        if new_status not in self.status_config:
            allowed_next_states = self.status_config[current_status]['allowed_next_states']
            return TransitionResult(
                allowed=False,
                current_status=current_status,
                new_status=new_status,
                error_message=f"Unknown new status: {new_status}. Allowed states: {', '.join(allowed_next_states)}",
                allowed_next_states=allowed_next_states
            )

        # 전환 가능 여부 확인
        allowed_next_states = self.status_config[current_status]['allowed_next_states']

        if new_status in allowed_next_states:
            return TransitionResult(
                allowed=True,
                current_status=current_status,
                new_status=new_status,
                error_message=None,
                allowed_next_states=allowed_next_states
            )
        else:
            current_display = self.status_config[current_status]['display_name']
            new_display = self.status_config[new_status]['display_name']

            # Terminal state (rejected) 특별 메시지
            if current_status == 'rejected':
                error_msg = f"Cannot transition from '{current_display}' (terminal state). Create a new review instead."
            else:
                allowed_display = [self.status_config[s]['display_name'] for s in allowed_next_states]
                error_msg = f"Cannot transition from '{current_display}' to '{new_display}'. Allowed next states: {', '.join(allowed_display)}"

            return TransitionResult(
                allowed=False,
                current_status=current_status,
                new_status=new_status,
                error_message=error_msg,
                allowed_next_states=allowed_next_states
            )

    def get_allowed_actions(self, current_status: str) -> List[str]:
        """
        현재 상태에서 가능한 액션 목록 반환

        Args:
            current_status: 현재 상태

        Returns:
            List[str]: 가능한 액션 리스트 (상태 이름)
        """
        if current_status not in self.status_config:
            logger.warning(f"Unknown status: {current_status}")
            return []

        return self.status_config[current_status]['allowed_next_states']

    def get_status_display_name(self, status: str) -> str:
        """상태의 표시 이름 반환"""
        if status not in self.status_config:
            return status
        return self.status_config[status]['display_name']

    def get_status_color(self, status: str) -> str:
        """상태의 컬러 태그 반환 (UI용)"""
        if status not in self.status_config:
            return 'gray'
        return self.status_config[status]['color']

    def get_all_statuses(self) -> Dict[str, Any]:
        """모든 상태 설정 반환 (UI용)"""
        return {
            status: {
                'display_name': config['display_name'],
                'color': config['color'],
                'allowed_next_states': config['allowed_next_states'],
                'description': config.get('description', '')
            }
            for status, config in self.status_config.items()
        }

    def is_terminal_state(self, status: str) -> bool:
        """종료 상태 여부 확인 (더 이상 전환 불가)"""
        if status not in self.status_config:
            return False
        return len(self.status_config[status]['allowed_next_states']) == 0

    def get_state_path(self, start_status: str, end_status: str) -> Optional[List[str]]:
        """
        시작 상태에서 종료 상태까지의 경로 탐색 (BFS)

        Args:
            start_status: 시작 상태
            end_status: 목표 상태

        Returns:
            List[str]: 상태 경로 (없으면 None)
        """
        if start_status == end_status:
            return [start_status]

        if start_status not in self.status_config or end_status not in self.status_config:
            return None

        # BFS 탐색
        from collections import deque

        queue = deque([(start_status, [start_status])])
        visited = {start_status}

        while queue:
            current, path = queue.popleft()

            allowed_next = self.status_config[current]['allowed_next_states']

            for next_status in allowed_next:
                if next_status == end_status:
                    return path + [next_status]

                if next_status not in visited:
                    visited.add(next_status)
                    queue.append((next_status, path + [next_status]))

        return None


# ============================================================
# Singleton Instance
# ============================================================

_workflow_instance = None

def get_workflow() -> ReviewWorkflow:
    """전역 워크플로우 인스턴스 반환 (Singleton)"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = ReviewWorkflow()
    return _workflow_instance


# ============================================================
# Convenience Functions
# ============================================================

def validate_status_transition(current_status: str, new_status: str) -> TransitionResult:
    """상태 전환 검증 (전역 함수)"""
    workflow = get_workflow()
    return workflow.validate_transition(current_status, new_status)


def get_allowed_next_statuses(current_status: str) -> List[str]:
    """가능한 다음 상태 목록 반환 (전역 함수)"""
    workflow = get_workflow()
    return workflow.get_allowed_actions(current_status)
