"""
Daily Scout 자동 연동 시스템
- Daily Scout DB에서 새 상품 감지
- 자동으로 PM Agent 워크플로우 실행
- 결과를 Approval Queue에 저장
"""

import os
import time
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Any

from agent_framework import WorkflowExecutor, ExecutionContext
from real_agents import register_real_agents
from approval_queue import ApprovalQueueManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DailyScoutIntegration:
    """Daily Scout DB와 PM Agent를 연동하는 클래스"""

    def __init__(self):
        # DB 연결 정보
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'fortimove_images'),
            'user': os.getenv('DB_USER', 'fortimove'),
            'password': os.getenv('DB_PASSWORD', 'fortimove123')
        }

        # 워크플로우 설정
        self.registry = register_real_agents()
        self.executor = WorkflowExecutor(self.registry)
        self.queue = ApprovalQueueManager()

        # 배치 크기 (한 번에 처리할 상품 수)
        # 2026-04-01: 10 → 100개로 확장 (일일 100개 처리 체계)
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))

        # 폴링 간격 (초)
        self.polling_interval = int(os.getenv('POLLING_INTERVAL', '300'))  # 5분

    def get_db_connection(self):
        """DB 연결 생성"""
        return psycopg2.connect(**self.db_config)

    def fetch_pending_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        workflow_status가 'pending'인 상품 조회

        Returns:
            상품 리스트 (최대 limit개)
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT id, date, region, source, product_name, brand, price,
                       category, trend_score, korea_demand, risk_status,
                       description, url, created_at
                FROM wellness_products
                WHERE workflow_status = 'pending'
                ORDER BY created_at DESC
                LIMIT %s
            """

            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

            products = []
            for row in rows:
                products.append({
                    'id': row[0],
                    'date': row[1],
                    'region': row[2],
                    'source': row[3],
                    'product_name': row[4],
                    'brand': row[5],
                    'price': row[6],
                    'category': row[7],
                    'trend_score': row[8],
                    'korea_demand': row[9],
                    'risk_status': row[10],
                    'description': row[11],
                    'url': row[12],
                    'created_at': row[13]
                })

            logger.info(f"✅ {len(products)}개 pending 상품 발견")
            return products

        finally:
            cursor.close()
            conn.close()

    def update_workflow_status(self, product_id: int, status: str, error: str = None):
        """
        상품의 workflow_status 업데이트

        Args:
            product_id: 상품 ID
            status: 'processing', 'completed', 'failed'
            error: 에러 메시지 (옵션)
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            query = """
                UPDATE wellness_products
                SET workflow_status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            cursor.execute(query, (status, product_id))
            conn.commit()

            logger.info(f"✅ Product {product_id} status → {status}")

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Failed to update product {product_id}: {e}")

        finally:
            cursor.close()
            conn.close()

    def parse_price(self, price_str: str) -> float:
        """
        가격 문자열을 float으로 변환

        예: "¥50.00" → 50.0, "$25" → 25.0
        """
        if not price_str:
            return 0.0

        # 숫자와 소수점만 추출
        import re
        numbers = re.findall(r'[\d.]+', price_str)
        if numbers:
            return float(numbers[0])
        return 0.0

    def estimate_weight(self, category: str, product_name: str) -> float:
        """
        카테고리와 상품명으로 무게 추정 (kg)

        간단한 룰 기반 추정
        """
        combined = f"{category} {product_name}".lower()

        if any(word in combined for word in ['서플먼트', '영양제', '비타민', '캡슐']):
            return 0.2
        elif any(word in combined for word in ['크림', '세럼', '로션', '에센스']):
            return 0.15
        elif any(word in combined for word in ['텀블러', '블렌더', '기기']):
            return 0.8
        elif any(word in combined for word in ['마스크', '시트']):
            return 0.05
        else:
            return 0.3  # 기본값

    def run_workflow_for_product(self, product: Dict[str, Any]) -> bool:
        """
        단일 상품에 대해 워크플로우 실행

        Args:
            product: Daily Scout 상품 데이터

        Returns:
            성공 여부
        """
        product_id = product['id']
        product_name = product['product_name']

        logger.info(f"🚀 [{product_id}] {product_name} 워크플로우 시작")

        try:
            # 1. workflow_status를 'processing'으로 변경
            self.update_workflow_status(product_id, 'processing')

            # 2. 입력 데이터 준비
            price_cny = self.parse_price(product['price'])
            weight_kg = self.estimate_weight(product['category'], product_name)

            user_input = {
                'source_url': product['url'] or f"https://taobao.com/item?id={product_id}",
                'source_title': product_name,
                'product_name': product_name,
                'source_description': product['description'],
                'source_price_cny': price_cny,
                'exchange_rate': 200.0,  # 기본 환율
                'weight_kg': weight_kg,
                'target_margin_rate': 0.30,  # 목표 마진 30%
                'market': 'korea',
                'keywords': [product['category']] if product['category'] else [],
                'source_options': []
            }

            # 3. 워크플로우 정의 (빠른 버전: 소싱 + 마진만)
            workflow_steps = [
                {
                    'step_id': 'sourcing',
                    'agent': 'sourcing',
                    'input_mapping': {
                        'source_url': 'user.source_url',
                        'source_title': 'user.source_title',
                        'keywords': 'user.keywords',
                        'market': 'user.market'
                    }
                },
                {
                    'step_id': 'margin',
                    'agent': 'margin_check',
                    'depends_on': ['sourcing'],
                    'expected_status': ['completed'],
                    'input_mapping': {
                        'action': 'literal.calculate_margin',
                        'source_price_cny': 'user.source_price_cny',
                        'exchange_rate': 'user.exchange_rate',
                        'weight_kg': 'user.weight_kg',
                        'target_margin_rate': 'user.target_margin_rate'
                    }
                }
            ]

            # 4. 워크플로우 실행
            context = ExecutionContext(user_input=user_input)
            final_result = self.executor.execute_sequential(workflow_steps, context)

            # 5. 결과 확인
            sourcing_result = context.get_result('sourcing')
            margin_result = context.get_result('margin')

            if not sourcing_result or not sourcing_result.is_success():
                logger.warning(f"⚠️ [{product_id}] Sourcing 실패")
                self.update_workflow_status(product_id, 'failed', 'Sourcing failed')
                return False

            if not margin_result or not margin_result.is_success():
                logger.warning(f"⚠️ [{product_id}] Margin check 실패")
                self.update_workflow_status(product_id, 'failed', 'Margin check failed')
                return False

            # 6. 결과를 Approval Queue에 저장
            sourcing_decision = sourcing_result.output.get('sourcing_decision', 'unknown')
            margin_decision = margin_result.output.get('final_decision', 'unknown')

            # 둘 다 통과한 경우만 Queue에 추가
            if sourcing_decision == '통과' and margin_decision == '등록 가능':
                queue_item = {
                    'product_id': product_id,
                    'product_name': product_name,
                    'sourcing_result': sourcing_result.output,
                    'margin_result': margin_result.output,
                    'daily_scout_data': product
                }

                queue_id = self.queue.add_item(
                    agent_name='daily_scout_workflow',
                    agent_output=queue_item,
                    metadata={
                        'source': 'daily_scout',
                        'product_id': product_id,
                        'region': product['region']
                    }
                )

                logger.info(f"✅ [{product_id}] Approval Queue에 추가됨 (ID: {queue_id})")
                self.update_workflow_status(product_id, 'completed')
                return True

            else:
                logger.warning(f"⚠️ [{product_id}] 판정 실패: sourcing={sourcing_decision}, margin={margin_decision}")
                self.update_workflow_status(product_id, 'failed', f"Decision failed: {sourcing_decision}/{margin_decision}")
                return False

        except Exception as e:
            logger.error(f"❌ [{product_id}] 워크플로우 실행 중 오류: {e}", exc_info=True)
            self.update_workflow_status(product_id, 'failed', str(e))
            return False

    def process_batch(self):
        """배치 처리 (한 번에 여러 상품 처리)"""
        logger.info(f"📦 배치 처리 시작 (최대 {self.batch_size}개)")

        try:
            # 1. Pending 상품 가져오기
            products = self.fetch_pending_products(limit=self.batch_size)

            if not products:
                logger.info("⏸️ 처리할 상품 없음")
                return

            # 2. 각 상품에 대해 워크플로우 실행
            success_count = 0
            fail_count = 0

            for product in products:
                success = self.run_workflow_for_product(product)
                if success:
                    success_count += 1
                else:
                    fail_count += 1

                # 각 상품 처리 후 잠시 대기 (API rate limit 방지)
                time.sleep(2)

            logger.info(f"📊 배치 완료: 성공 {success_count}개, 실패 {fail_count}개")

        except Exception as e:
            logger.error(f"❌ 배치 처리 중 오류: {e}", exc_info=True)

    def run_continuous(self):
        """지속적으로 폴링하면서 처리"""
        logger.info(f"🔄 자동 연동 시작 (폴링 간격: {self.polling_interval}초)")

        while True:
            try:
                self.process_batch()
            except Exception as e:
                logger.error(f"❌ 예상치 못한 오류: {e}", exc_info=True)

            # 다음 배치까지 대기
            logger.info(f"⏳ {self.polling_interval}초 대기 중...")
            time.sleep(self.polling_interval)


def main():
    """메인 함수"""
    logger.info("="*70)
    logger.info("  Daily Scout → PM Agent 자동 연동 시스템")
    logger.info("="*70)

    integration = DailyScoutIntegration()

    # 한 번만 실행 (테스트용)
    if os.getenv('RUN_ONCE', 'false').lower() == 'true':
        logger.info("🔧 테스트 모드: 1회만 실행")
        integration.process_batch()
    else:
        # 지속적으로 실행
        integration.run_continuous()


if __name__ == '__main__':
    main()
