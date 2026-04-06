#!/usr/bin/env python3
"""
간소화된 대기 상품 일괄 처리 스크립트
API 직접 호출 방식 (DailyScoutIntegration 의존성 제거)
"""
import os
import sys
import time
import requests
import psycopg2
import logging
from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleBatchProcessor:
    def __init__(self):
        self.api_base_url = os.getenv('PM_AGENT_URL', 'http://localhost:8001')
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME', 'fortimove_images'),
            'user': os.getenv('DB_USER', 'fortimove'),
            'password': os.getenv('DB_PASSWORD', 'fortimove123'),
        }
        self.delay_between_requests = 2  # Rate limit protection

    def get_db_connection(self):
        """DB 연결 생성"""
        return psycopg2.connect(**self.db_config)

    def fetch_pending_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """workflow_status가 'pending'인 상품 조회"""
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

            columns = [desc[0] for desc in cursor.description]
            products = []

            for row in cursor.fetchall():
                product = dict(zip(columns, row))
                products.append(product)

            return products

        finally:
            cursor.close()
            conn.close()

    def update_workflow_status(self, product_id: int, status: str):
        """상품의 workflow_status 업데이트"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            query = """
                UPDATE wellness_products
                SET workflow_status = %s,
                    workflow_updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            cursor.execute(query, (status, product_id))
            conn.commit()

        finally:
            cursor.close()
            conn.close()

    def call_workflow_api(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        PM Agent API를 직접 호출하여 워크플로우 실행
        """
        # 가격 파싱 (숫자만 추출)
        import re
        price_str = str(product.get('price', '0'))
        numbers = re.findall(r'[\d.]+', price_str)
        price_cny = float(numbers[0]) if numbers else 30.0

        # 무게 추정 (간단한 룰)
        product_name = product.get('product_name', '').lower()
        if 'protein' in product_name or 'creatine' in product_name:
            weight_kg = 1.0  # 파우더류
        elif 'capsule' in product_name or 'tablet' in product_name:
            weight_kg = 0.2  # 알약류
        else:
            weight_kg = 0.3  # 기본값

        payload = {
            "workflow_name": "quick_sourcing_check",
            "user_input": {
                "source_url": product.get('url', ''),
                "source_title": product.get('product_name', ''),
                "source_description": product.get('description', ''),
                "market": "korea",
                "source_price_cny": price_cny,
                "weight_kg": weight_kg
            },
            "save_to_queue": True  # Auto-approval 적용됨
        }

        try:
            response = requests.post(
                f"{self.api_base_url}/api/workflows/run",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ API Error {response.status_code}: {response.text[:200]}")
                return {"status": "error", "message": f"HTTP {response.status_code}"}

        except requests.exceptions.Timeout:
            logger.error(f"⏳ API Timeout")
            return {"status": "error", "message": "Timeout"}
        except Exception as e:
            logger.error(f"🔥 API Exception: {e}")
            return {"status": "error", "message": str(e)}

    def process_all_pending(self, max_products: int = 100):
        """
        모든 대기 상품을 일괄 처리
        """
        products = self.fetch_pending_products(limit=max_products)

        logger.info(f"📦 총 {len(products)}개 상품 발견")

        auto_approved = []
        manual_review = []
        failed = []

        for idx, product in enumerate(products, 1):
            product_id = product['id']
            product_name = product['product_name'][:60]

            logger.info(f"\n[{idx}/{len(products)}] 처리 중: {product_name}")

            # 1. DB 상태 업데이트 (processing)
            self.update_workflow_status(product_id, 'processing')

            # 2. API 호출
            try:
                result = self.call_workflow_api(product)

                if result.get('status') == 'completed':
                    # 3-1. 성공: completed로 업데이트
                    self.update_workflow_status(product_id, 'completed')

                    # Auto-approval 체크
                    auto_approval_info = result.get('result', {}).get('auto_approval', {})
                    if auto_approval_info.get('approved'):
                        logger.info(f"   🏆 Golden Pass 통과!")
                        auto_approved.append({
                            'product': product,
                            'result': result
                        })
                    else:
                        logger.info(f"   ⏸️ 수동 검토 필요: {auto_approval_info.get('reason', 'Unknown')}")
                        manual_review.append({
                            'product': product,
                            'result': result
                        })

                else:
                    # 3-2. 실패
                    self.update_workflow_status(product_id, 'failed')
                    failed.append({
                        'product': product,
                        'error': result.get('message', 'Unknown error')
                    })
                    logger.error(f"   ❌ 워크플로우 실패: {result.get('message', 'Unknown')}")

            except Exception as e:
                logger.error(f"   ❌ 예외 발생: {str(e)}")
                self.update_workflow_status(product_id, 'failed')
                failed.append({
                    'product': product,
                    'error': str(e)
                })

            # 4. Rate Limit 방지 대기
            if idx < len(products):
                time.sleep(self.delay_between_requests)

        # 5. 요약 리포트 생성
        return self.generate_summary(auto_approved, manual_review, failed)

    def generate_summary(self, auto_approved, manual_review, failed):
        """처리 결과 요약"""
        total = len(auto_approved) + len(manual_review) + len(failed)

        summary = {
            'total_processed': total,
            'auto_approved_count': len(auto_approved),
            'manual_review_count': len(manual_review),
            'failed_count': len(failed),
            'auto_approval_rate': (len(auto_approved) / total * 100) if total > 0 else 0,
            'auto_approved': auto_approved,
            'manual_review': manual_review,
            'failed': failed
        }

        # 콘솔 출력
        print("\n" + "=" * 80)
        print("📊 처리 결과 요약")
        print("=" * 80 + "\n")

        print(f"총 처리: {total}개")
        print(f"  🏆 자동 승인: {len(auto_approved)}개 ({summary['auto_approval_rate']:.1f}%)")
        print(f"  ⏸️ 수동 검토: {len(manual_review)}개")
        print(f"  ❌ 실패: {len(failed)}개")
        print("")

        # 자동 승인 상품 목록
        if auto_approved:
            print("🏆 자동 승인 상품 (Golden Pass):")
            for item in auto_approved[:10]:
                product = item['product']
                print(f"  • {product['product_name'][:50]}...")

        # 수동 검토 상품 (상위 5개만)
        if manual_review:
            print(f"\n⏸️ 수동 검토 필요 상품 (상위 5개):")
            for item in manual_review[:5]:
                product = item['product']
                reason = item['result'].get('result', {}).get('auto_approval', {}).get('reason', 'Unknown')
                print(f"  • {product['product_name'][:40]}... - {reason}")

        # 실패 상품
        if failed:
            print(f"\n❌ 실패한 상품 ({len(failed)}개):")
            for item in failed[:5]:
                product = item['product']
                print(f"  • {product['product_name'][:40]}...")
                print(f"    오류: {item['error']}")

        print("\n" + "=" * 80)

        return summary


def main():
    """메인 실행 함수"""

    print("\n" + "=" * 80)
    print("🚀 Fortimove 대기 상품 일괄 처리 (간소화 버전)")
    print("=" * 80 + "\n")

    max_products = int(os.getenv('MAX_PRODUCTS', '100'))

    print(f"최대 처리 개수: {max_products}개")
    print(f"Rate Limit 방지 대기 시간: 2초")
    print(f"자동 승인 기준: 마진 45% 이상, 리스크 0개, KC 불필요")
    print(f"PM Agent API: {os.getenv('PM_AGENT_URL', 'http://localhost:8001')}")
    print("")

    # 처리 시작
    processor = SimpleBatchProcessor()
    summary = processor.process_all_pending(max_products=max_products)

    print("\n✅ 모든 처리가 완료되었습니다!")


if __name__ == "__main__":
    main()
