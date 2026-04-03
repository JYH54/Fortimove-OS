"""
Daily Scout 자동 연동 시스템 (API 버전)
- Daily Scout DB에서 새 상품 감지
- 원격 PM Agent API를 호출하여 워크플로우 실행
- 결과를 확인하고 DB 상태 업데이트
"""

import os
import time
import logging
import psycopg2
import requests
from datetime import datetime
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DailyScoutIntegrationAPI:
    """Daily Scout DB와 PM Agent API를 연동하는 클래스"""

    def __init__(self):
        # DB 연결 정보
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'fortimove_images'),
            'user': os.getenv('DB_USER', 'fortimove'),
            'password': os.getenv('DB_PASSWORD', 'fortimove123')
        }

        # PM Agent API 설정
        self.api_base_url = os.getenv('PM_AGENT_API_URL', 'https://staging-pm-agent.fortimove.com')
        self.api_timeout = 120  # 2분

        # 배치 크기 (한 번에 처리할 상품 수)
        self.batch_size = int(os.getenv('BATCH_SIZE', '5'))

        # 폴링 간격 (초)
        self.polling_interval = int(os.getenv('POLLING_INTERVAL', '300'))  # 5분

        logger.info(f"Daily Scout Integration 초기화")
        logger.info(f"  DB: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
        logger.info(f"  API: {self.api_base_url}")
        logger.info(f"  Batch Size: {self.batch_size}")
        logger.info(f"  Polling Interval: {self.polling_interval}초")

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

            return products

        finally:
            cursor.close()
            conn.close()

    def update_workflow_status(self, product_id: int, status: str, error_message: str = None):
        """
        상품의 workflow_status 업데이트

        Args:
            product_id: 상품 ID
            status: 새로운 상태 (processing, completed, failed)
            error_message: 실패 시 에러 메시지
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            if error_message:
                query = """
                    UPDATE wellness_products
                    SET workflow_status = %s,
                        workflow_error = %s,
                        workflow_updated_at = %s
                    WHERE id = %s
                """
                cursor.execute(query, (status, error_message, datetime.now(), product_id))
            else:
                query = """
                    UPDATE wellness_products
                    SET workflow_status = %s,
                        workflow_updated_at = %s
                    WHERE id = %s
                """
                cursor.execute(query, (status, datetime.now(), product_id))

            conn.commit()
            logger.info(f"[Product #{product_id}] 상태 업데이트: {status}")

        except Exception as e:
            logger.error(f"[Product #{product_id}] 상태 업데이트 실패: {e}")
            conn.rollback()

        finally:
            cursor.close()
            conn.close()

    def parse_price(self, price_str: str) -> float:
        """가격 문자열을 숫자로 변환"""
        try:
            # "30.00 CNY" -> 30.0
            return float(price_str.replace('CNY', '').replace('USD', '').strip())
        except:
            return 0.0

    def estimate_weight(self, category: str, product_name: str) -> float:
        """
        카테고리와 상품명으로 무게 추정 (kg)
        실제로는 AI 기반 추정이나 데이터베이스 조회 필요
        """
        # 간단한 휴리스틱
        if '텀블러' in product_name or 'tumbler' in product_name.lower():
            return 0.5
        elif '세럼' in product_name or 'serum' in product_name.lower():
            return 0.1
        elif '블렌더' in product_name or 'blender' in product_name.lower():
            return 1.5
        else:
            return 0.5  # 기본값

    def call_workflow_api(self, workflow_name: str, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        PM Agent API를 호출하여 워크플로우 실행

        Args:
            workflow_name: 워크플로우 이름
            user_input: 사용자 입력 데이터

        Returns:
            API 응답 (execution_id, status, result 포함)
        """
        url = f"{self.api_base_url}/api/workflows/run"

        payload = {
            "workflow_name": workflow_name,
            "user_input": user_input,
            "save_to_queue": True  # Approval Queue에 자동 저장
        }

        try:
            logger.info(f"API 호출: {workflow_name}")
            logger.debug(f"  Payload: {payload}")

            response = requests.post(url, json=payload, timeout=self.api_timeout)
            response.raise_for_status()

            result = response.json()
            logger.info(f"  실행 ID: {result['execution_id']}")
            logger.info(f"  상태: {result['status']}")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"API 호출 실패: {e}")
            raise

    def process_product(self, product: Dict[str, Any]) -> bool:
        """
        단일 상품 처리

        Args:
            product: 상품 정보

        Returns:
            성공 여부
        """
        product_id = product['id']
        product_name = product['product_name']

        logger.info(f"[Product #{product_id}] 처리 시작: {product_name}")

        # 1. 상태를 'processing'으로 업데이트
        self.update_workflow_status(product_id, 'processing')

        # 2. 워크플로우 입력 준비
        user_input = {
            'source_url': product['url'],
            'source_title': product_name,
            'market': 'korea',
            'source_price_cny': self.parse_price(product['price']),
            'weight_kg': self.estimate_weight(product['category'], product_name),
            'exchange_rate': 195.0,  # 기본 환율 (실시간 조회 가능)
            'target_margin_rate': 0.4  # 40% 마진율
        }

        try:
            # 3. API 호출 (quick_sourcing_check: sourcing + margin)
            result = self.call_workflow_api('quick_sourcing_check', user_input)

            # 4. 결과 분석
            if result['status'] == 'completed':
                workflow_results = result.get('result', {})

                sourcing_result = workflow_results.get('sourcing', {})
                margin_result = workflow_results.get('margin', {})

                sourcing_status = sourcing_result.get('status')
                margin_status = margin_result.get('status')

                logger.info(f"[Product #{product_id}] Sourcing: {sourcing_status}, Margin: {margin_status}")

                # 두 단계 모두 성공하면 'completed', 아니면 'failed'
                if sourcing_status == 'completed' and margin_status == 'completed':
                    self.update_workflow_status(product_id, 'completed')
                    logger.info(f"[Product #{product_id}] ✅ 워크플로우 완료 - Approval Queue로 이동")
                    return True
                else:
                    error_msg = sourcing_result.get('error') or margin_result.get('error') or '워크플로우 단계 실패'
                    self.update_workflow_status(product_id, 'failed', error_msg)
                    logger.warning(f"[Product #{product_id}] ⚠️ 워크플로우 실패: {error_msg}")
                    return False

            else:
                error_msg = result.get('error', 'Unknown error')
                self.update_workflow_status(product_id, 'failed', error_msg)
                logger.error(f"[Product #{product_id}] ❌ API 실행 실패: {error_msg}")
                return False

        except Exception as e:
            error_msg = str(e)
            self.update_workflow_status(product_id, 'failed', error_msg)
            logger.error(f"[Product #{product_id}] ❌ 처리 중 예외: {e}", exc_info=True)
            return False

    def process_batch(self):
        """배치 단위로 상품 처리"""
        logger.info(f"\n{'='*60}")
        logger.info(f"배치 처리 시작 (최대 {self.batch_size}개)")
        logger.info(f"{'='*60}")

        try:
            # 1. Pending 상품 조회
            products = self.fetch_pending_products(limit=self.batch_size)

            if not products:
                logger.info("처리할 pending 상품이 없습니다.")
                return

            logger.info(f"처리할 상품: {len(products)}개")

            # 2. 각 상품 처리
            success_count = 0
            for product in products:
                try:
                    if self.process_product(product):
                        success_count += 1
                    time.sleep(2)  # API 부하 방지
                except Exception as e:
                    logger.error(f"상품 처리 중 예외: {e}")
                    continue

            logger.info(f"\n배치 처리 완료: {success_count}/{len(products)} 성공")

        except Exception as e:
            logger.error(f"배치 처리 실패: {e}", exc_info=True)

    def run_continuous(self):
        """지속적으로 폴링하며 상품 처리"""
        logger.info("Daily Scout Integration 시작 (연속 모드)")
        logger.info(f"폴링 간격: {self.polling_interval}초\n")

        while True:
            try:
                self.process_batch()
            except Exception as e:
                logger.error(f"배치 처리 중 오류: {e}", exc_info=True)

            logger.info(f"\n다음 폴링까지 {self.polling_interval}초 대기...\n")
            time.sleep(self.polling_interval)


def main():
    """메인 함수"""
    integration = DailyScoutIntegrationAPI()

    # 환경 변수로 모드 선택
    mode = os.getenv('RUN_MODE', 'continuous')  # continuous | once

    if mode == 'once':
        logger.info("단일 배치 모드로 실행")
        integration.process_batch()
    else:
        logger.info("연속 폴링 모드로 실행")
        integration.run_continuous()


if __name__ == "__main__":
    main()
