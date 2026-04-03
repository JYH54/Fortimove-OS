"""
Approval Ranker - Approval Queue 우선순위 관리
LLM 사용 없음, 순수 DB 정렬 및 업데이트
"""

import logging
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from approval_queue import ApprovalQueueManager
from scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


class ApprovalRanker:
    """
    Approval Queue의 우선순위를 관리하는 클래스

    기능:
        1. pending 상품을 점수순으로 정렬
        2. priority 필드 업데이트 (1부터 시작)
        3. 점수가 없는 항목은 자동 점수 계산
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: approval_queue.db 경로 (None이면 기본값 사용)
        """
        self.queue = ApprovalQueueManager(db_path=db_path)
        self.scorer = ScoringEngine()
        self.db_path = db_path or self.queue.db_path

    def rank_all_pending(self) -> List[Dict[str, Any]]:
        """
        모든 pending 상품의 우선순위를 재계산

        Returns:
            정렬된 상품 목록 (점수 높은 순)
        """
        try:
            logger.info("Approval Queue 우선순위 재계산 시작")

            # 1. pending 상품 조회
            items = self.queue.list_items(reviewer_status="pending")
            logger.info(f"  - Pending 상품: {len(items)}개")

            if not items:
                logger.info("  - 처리할 pending 상품 없음")
                return []

            # 2. 점수가 없는 항목은 자동 계산
            scored_items = []
            for item in items:
                if item.get('score', 0) == 0:
                    logger.info(f"  - [{item['review_id']}] 점수 없음, 자동 계산 중...")
                    self._score_item(item['review_id'])

                # 점수 업데이트 후 다시 조회
                updated_item = self.queue.get_item(item['review_id'])
                if updated_item:
                    scored_items.append(updated_item)

            # 3. 점수순 정렬 (높은 순)
            sorted_items = sorted(
                scored_items,
                key=lambda x: (
                    x.get('score', 0),  # 1차: 점수 (높은 순)
                    -self._parse_datetime(x.get('created_at', ''))  # 2차: 생성일 (오래된 순)
                ),
                reverse=True
            )

            # 4. Priority 재계산 (1부터 시작)
            for i, item in enumerate(sorted_items, 1):
                self._update_priority(item['review_id'], i)
                logger.info(f"  - [{item['review_id']}] Priority: {i}, Score: {item.get('score', 0)}")

            logger.info(f"우선순위 재계산 완료: {len(sorted_items)}개")

            return sorted_items

        except Exception as e:
            logger.error(f"우선순위 재계산 실패: {e}", exc_info=True)
            return []

    def rank_by_decision(self, decision: str = 'auto_approve') -> List[Dict[str, Any]]:
        """
        특정 decision의 상품만 우선순위 재계산

        Args:
            decision: 'auto_approve', 'review', 'hold', 'reject'

        Returns:
            정렬된 상품 목록
        """
        try:
            logger.info(f"Decision '{decision}' 상품 우선순위 재계산")

            # 1. 모든 pending 상품 조회
            items = self.queue.list_items(reviewer_status="pending")

            # 2. decision 필터링
            filtered_items = [
                item for item in items
                if item.get('decision', 'review') == decision
            ]

            logger.info(f"  - Decision '{decision}' 상품: {len(filtered_items)}개")

            if not filtered_items:
                return []

            # 3. 점수순 정렬
            sorted_items = sorted(
                filtered_items,
                key=lambda x: x.get('score', 0),
                reverse=True
            )

            # 4. Priority 업데이트 (decision별 독립적)
            for i, item in enumerate(sorted_items, 1):
                # auto_approve는 1-10, review는 11-20, hold는 21-30 등
                priority_offset = {
                    'auto_approve': 0,
                    'review': 100,
                    'hold': 200,
                    'reject': 300
                }.get(decision, 100)

                priority = priority_offset + i
                self._update_priority(item['review_id'], priority)

            return sorted_items

        except Exception as e:
            logger.error(f"Decision별 우선순위 재계산 실패: {e}", exc_info=True)
            return []

    def get_top_items(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        우선순위 상위 N개 조회

        Args:
            limit: 조회할 개수

        Returns:
            상위 N개 상품 목록
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT *
                FROM approval_queue
                WHERE reviewer_status = 'pending'
                ORDER BY priority ASC, score DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def _score_item(self, review_id: str) -> bool:
        """
        개별 상품 점수 계산 및 DB 업데이트

        Args:
            review_id: 상품 ID

        Returns:
            성공 여부
        """
        try:
            # 1. 상품 정보 조회
            item = self.queue.get_item(review_id)
            if not item:
                logger.warning(f"상품을 찾을 수 없음: {review_id}")
                return False

            # 2. agent_output 파싱
            raw_output = item.get('raw_agent_output', '{}')
            agent_output = json.loads(raw_output) if isinstance(raw_output, str) else raw_output

            # 3. source_data 파싱
            source_data_str = item.get('source_data_json', '{}')
            source_data = json.loads(source_data_str) if isinstance(source_data_str, str) else source_data_str

            # 4. 점수 계산
            review_data = {
                'review_id': review_id,
                'source_type': item.get('source_type', ''),
                'agent_output': agent_output,
                'source_data': source_data
            }

            score_result = self.scorer.score_product(review_data)

            # 5. DB 업데이트
            self._update_score(
                review_id=review_id,
                score=score_result['score'],
                decision=score_result['decision'],
                reasons=score_result['reasons']
            )

            logger.info(f"  - [{review_id}] 점수 계산 완료: {score_result['score']}점, {score_result['decision']}")

            return True

        except Exception as e:
            logger.error(f"상품 점수 계산 실패 ({review_id}): {e}", exc_info=True)
            return False

    def _update_score(self, review_id: str, score: int, decision: str, reasons: List[str]):
        """점수 및 decision 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            reasons_json = json.dumps(reasons, ensure_ascii=False)

            cursor.execute('''
                UPDATE approval_queue
                SET score = ?,
                    decision = ?,
                    reasons_json = ?,
                    scoring_updated_at = ?
                WHERE review_id = ?
            ''', (score, decision, reasons_json, datetime.now().isoformat(), review_id))

            conn.commit()

    def _update_priority(self, review_id: str, priority: int):
        """Priority 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE approval_queue
                SET priority = ?
                WHERE review_id = ?
            ''', (priority, review_id))

            conn.commit()

    def _parse_datetime(self, datetime_str: str) -> float:
        """ISO 8601 문자열을 timestamp로 변환"""
        try:
            dt = datetime.fromisoformat(datetime_str)
            return dt.timestamp()
        except:
            return 0.0


# ============================================================
# 사용 예시
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    ranker = ApprovalRanker()

    print("\n=== Approval Queue 우선순위 재계산 ===")
    ranked_items = ranker.rank_all_pending()

    print(f"\n총 {len(ranked_items)}개 상품 정렬 완료\n")

    print("=== 상위 5개 상품 ===")
    top_items = ranker.get_top_items(limit=5)

    for i, item in enumerate(top_items, 1):
        print(f"{i}. {item.get('source_title', 'N/A')}")
        print(f"   Score: {item.get('score', 0)}, Decision: {item.get('decision', 'N/A')}")
        print(f"   Priority: {item.get('priority', 0)}")
        print()
