#!/usr/bin/env python3
"""
대기 중인 상품 일괄 처리 및 자동 승인 적용
- pending 상태 상품을 워크플로우로 처리
- Golden Pass 기준 충족 시 자동 승인
"""

import os
import sys
import time
import asyncio
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from daily_scout_integration import DailyScoutIntegration
from auto_approval import AutoApprovalEngine
from approval_queue import ApprovalQueueManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BatchProcessor:
    """대기 상품 일괄 처리"""

    def __init__(self):
        self.integration = DailyScoutIntegration()
        self.auto_approval = AutoApprovalEngine()
        self.queue = ApprovalQueueManager()

        # Rate Limit 방지 (요청 간 대기 시간)
        self.delay_between_requests = 2  # 2초

    def process_all_pending(self, max_products: int = 100):
        """
        모든 pending 상품 처리

        Args:
            max_products: 최대 처리 개수 (기본 100개)
        """
        logger.info("=" * 80)
        logger.info("🚀 대기 상품 일괄 처리 시작")
        logger.info("=" * 80)

        # 1. Pending 상품 조회
        products = self.integration.fetch_pending_products(limit=max_products)

        if not products:
            logger.info("✅ 처리할 pending 상품이 없습니다")
            return self.generate_summary_report([], [], [])

        logger.info(f"📦 총 {len(products)}개 상품 발견")
        logger.info("")

        # 결과 통계
        auto_approved = []
        manual_review = []
        failed = []

        # 2. 각 상품 처리
        for idx, product in enumerate(products, 1):
            logger.info(f"[{idx}/{len(products)}] 처리 중: {product['product_name']}")

            try:
                # Rate Limit 방지
                if idx > 1:
                    time.sleep(self.delay_between_requests)

                # 워크플로우 실행
                result = self.integration.process_single_product(product)

                if result['success']:
                    # 자동 승인 평가
                    workflow_results = result.get('workflow_results', {})
                    approved, reason, evaluation = self.auto_approval.evaluate(workflow_results)

                    result['auto_approved'] = approved
                    result['approval_reason'] = reason
                    result['evaluation'] = evaluation

                    if approved:
                        auto_approved.append({
                            'product': product,
                            'result': result
                        })
                        logger.info(f"   🏆 자동 승인! {reason}")
                    else:
                        manual_review.append({
                            'product': product,
                            'result': result
                        })
                        logger.info(f"   ⏸️ 수동 검토 필요: {reason}")
                else:
                    failed.append({
                        'product': product,
                        'error': result.get('error', 'Unknown error')
                    })
                    logger.error(f"   ❌ 처리 실패: {result.get('error')}")

                logger.info("")

            except Exception as e:
                logger.error(f"   ❌ 예외 발생: {e}")
                failed.append({
                    'product': product,
                    'error': str(e)
                })
                logger.info("")

        # 3. 요약 리포트 생성
        return self.generate_summary_report(auto_approved, manual_review, failed)

    def generate_summary_report(self, auto_approved, manual_review, failed):
        """처리 결과 요약 리포트 생성"""

        report = "\n" + "=" * 80 + "\n"
        report += "📊 일괄 처리 결과 요약\n"
        report += "=" * 80 + "\n\n"

        total = len(auto_approved) + len(manual_review) + len(failed)

        report += f"총 처리: {total}개\n"
        report += f"  🏆 자동 승인: {len(auto_approved)}개\n"
        report += f"  ⏸️ 수동 검토: {len(manual_review)}개\n"
        report += f"  ❌ 처리 실패: {len(failed)}개\n"
        report += "\n"

        # 자동 승인률
        if total > 0:
            auto_approval_rate = (len(auto_approved) / total) * 100
            report += f"자동 승인률: {auto_approval_rate:.1f}%\n\n"

        # 자동 승인 상품 목록
        if auto_approved:
            report += "🏆 자동 승인된 상품:\n"
            report += "-" * 80 + "\n"

            total_margin = 0
            total_revenue = 0

            for item in auto_approved:
                product = item['product']
                result = item['result']

                # 마진 정보 추출
                pricing_result = result.get('workflow_results', {}).get('pricing', {}).get('output', {})
                margin_rate = pricing_result.get('margin_rate', 0)
                final_price = pricing_result.get('final_price', 0)
                margin_amount = pricing_result.get('margin_amount', 0)

                total_margin += margin_amount
                total_revenue += final_price

                report += f"  • {product['product_name']}\n"
                report += f"    판매가: ₩{final_price:,} | 마진: {margin_rate*100:.1f}% (₩{margin_amount:,})\n"

            report += f"\n  💰 예상 총 수익: ₩{total_margin:,}\n"
            report += f"  💵 예상 총 매출: ₩{total_revenue:,}\n"
            report += "\n"

        # 수동 검토 필요 상품
        if manual_review:
            report += "⏸️ 수동 검토 필요 상품:\n"
            report += "-" * 80 + "\n"

            for item in manual_review:
                product = item['product']
                reason = item['result'].get('approval_reason', 'Unknown')

                report += f"  • {product['product_name']}\n"
                report += f"    사유: {reason}\n"

            report += "\n"

        # 실패 상품
        if failed:
            report += "❌ 처리 실패 상품:\n"
            report += "-" * 80 + "\n"

            for item in failed:
                product = item['product']
                error = item['error']

                report += f"  • {product['product_name']}\n"
                report += f"    오류: {error}\n"

            report += "\n"

        report += "=" * 80 + "\n"

        # 리포트 출력 및 저장
        print(report)

        # 파일로 저장
        report_file = Path(__file__).parent / "data" / f"batch_report_{int(time.time())}.txt"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(report, encoding='utf-8')

        logger.info(f"📄 리포트 저장: {report_file}")

        return {
            'total': total,
            'auto_approved': len(auto_approved),
            'manual_review': len(manual_review),
            'failed': len(failed),
            'auto_approval_rate': (len(auto_approved) / total * 100) if total > 0 else 0,
            'report': report
        }


def main():
    """메인 실행 함수"""

    print("\n" + "=" * 80)
    print("🚀 Fortimove 대기 상품 일괄 처리")
    print("=" * 80 + "\n")

    # 처리 개수 입력
    max_products = int(os.getenv('MAX_PRODUCTS', '100'))

    print(f"최대 처리 개수: {max_products}개")
    print(f"Rate Limit 방지 대기 시간: 2초")
    print(f"자동 승인 기준: 마진 45% 이상, 리스크 0개, KC 불필요")
    print("")

    # AUTO_RUN 환경 변수가 있으면 자동 실행
    auto_run = os.getenv('AUTO_RUN', 'false').lower() == 'true'

    if not auto_run:
        confirm = input("처리를 시작하시겠습니까? (y/N): ")
        if confirm.lower() != 'y':
            print("취소되었습니다.")
            return

    # 처리 시작
    processor = BatchProcessor()
    summary = processor.process_all_pending(max_products=max_products)

    print("\n✅ 모든 처리가 완료되었습니다!")
    print(f"자동 승인률: {summary['auto_approval_rate']:.1f}%")

    # AUTO_RUN 모드이거나 사용자가 원하면 승인 대기열 상태 확인
    auto_run = os.getenv('AUTO_RUN', 'false').lower() == 'true'
    show_stats = auto_run

    if not auto_run:
        stats_response = input("\n승인 대기열 현황을 확인하시겠습니까? (y/N): ")
        show_stats = stats_response.lower() == 'y'

    if show_stats:
        queue = ApprovalQueueManager()
        pending = len(queue.list_items("pending"))
        approved = len(queue.list_items("approved"))

        print(f"\n현재 승인 대기열:")
        print(f"  대기중: {pending}개")
        print(f"  승인됨: {approved}개")


if __name__ == "__main__":
    main()
