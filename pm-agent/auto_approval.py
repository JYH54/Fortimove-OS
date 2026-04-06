"""
Fortimove Golden Pass - 자동 승인 시스템
마진율 45% 이상, 리스크 0인 상품을 자동 승인
"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoApprovalEngine:
    """자동 승인 엔진 - Fortimove Golden Pass"""

    # Golden Pass 기준
    GOLDEN_PASS_CRITERIA = {
        'min_margin_rate': 0.45,  # 45%
        'min_price': 20000,        # 20,000원
        'max_price': 150000,       # 150,000원
        'required_sourcing_decision': '통과',
        'required_kc_status': False,  # KC 인증 불필요
        'max_risk_flags': 0
    }

    def __init__(self):
        self.criteria = self.GOLDEN_PASS_CRITERIA
        logger.info("🏆 Auto-Approval Engine 초기화 완료")
        logger.info(f"   마진율 기준: {self.criteria['min_margin_rate']*100}% 이상")
        logger.info(f"   가격 범위: ₩{self.criteria['min_price']:,} ~ ₩{self.criteria['max_price']:,}")

    def evaluate(self, workflow_result: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        워크플로우 결과를 평가하여 자동 승인 여부 판단

        Args:
            workflow_result: 워크플로우 실행 결과 (sourcing + pricing + margin)

        Returns:
            (승인여부, 이유, 평가상세)
        """
        evaluation = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'pass': False,
            'reason': '',
            'auto_approved': False
        }

        try:
            # 1. Sourcing 판정 체크
            sourcing_result = workflow_result.get('sourcing', {}).get('output', {})
            sourcing_decision = sourcing_result.get('sourcing_decision', '')

            evaluation['checks']['sourcing'] = {
                'required': self.criteria['required_sourcing_decision'],
                'actual': sourcing_decision,
                'pass': sourcing_decision == self.criteria['required_sourcing_decision']
            }

            if not evaluation['checks']['sourcing']['pass']:
                evaluation['reason'] = f"소싱 판정 불통과: {sourcing_decision}"
                return False, evaluation['reason'], evaluation

            # 2. 마진율 체크
            pricing_result = workflow_result.get('pricing', {}).get('output', {})
            margin_rate = pricing_result.get('margin_rate', 0)

            evaluation['checks']['margin'] = {
                'required': f">= {self.criteria['min_margin_rate']*100}%",
                'actual': f"{margin_rate*100:.1f}%",
                'pass': margin_rate >= self.criteria['min_margin_rate']
            }

            if not evaluation['checks']['margin']['pass']:
                evaluation['reason'] = f"마진율 부족: {margin_rate*100:.1f}% < {self.criteria['min_margin_rate']*100}%"
                return False, evaluation['reason'], evaluation

            # 3. 가격 범위 체크
            final_price = pricing_result.get('final_price', 0)

            evaluation['checks']['price_range'] = {
                'required': f"₩{self.criteria['min_price']:,} ~ ₩{self.criteria['max_price']:,}",
                'actual': f"₩{final_price:,}",
                'pass': self.criteria['min_price'] <= final_price <= self.criteria['max_price']
            }

            if not evaluation['checks']['price_range']['pass']:
                evaluation['reason'] = f"가격 범위 초과: ₩{final_price:,}"
                return False, evaluation['reason'], evaluation

            # 4. KC 인증 체크
            kc_required = sourcing_result.get('kc_cert_required', False)

            evaluation['checks']['kc_cert'] = {
                'required': 'KC 인증 불필요',
                'actual': 'KC 인증 필요' if kc_required else 'KC 인증 불필요',
                'pass': not kc_required
            }

            if not evaluation['checks']['kc_cert']['pass']:
                evaluation['reason'] = "KC 인증 필요 상품"
                return False, evaluation['reason'], evaluation

            # 5. 리스크 플래그 체크
            risk_flags = sourcing_result.get('risk_flags', [])
            risk_count = len(risk_flags) if isinstance(risk_flags, list) else 0

            evaluation['checks']['risk_flags'] = {
                'required': f"<= {self.criteria['max_risk_flags']}개",
                'actual': f"{risk_count}개",
                'details': risk_flags if risk_count > 0 else [],
                'pass': risk_count <= self.criteria['max_risk_flags']
            }

            if not evaluation['checks']['risk_flags']['pass']:
                evaluation['reason'] = f"리스크 플래그 {risk_count}개 감지: {risk_flags}"
                return False, evaluation['reason'], evaluation

            # 🏆 모든 조건 통과 - Golden Pass!
            evaluation['pass'] = True
            evaluation['auto_approved'] = True
            evaluation['reason'] = '🏆 Fortimove Golden Pass - 모든 조건 충족'

            logger.info(f"✅ 자동 승인: {sourcing_result.get('source_title', 'Unknown')} (마진 {margin_rate*100:.1f}%)")

            return True, evaluation['reason'], evaluation

        except Exception as e:
            logger.error(f"❌ 자동 승인 평가 오류: {e}")
            evaluation['reason'] = f"평가 오류: {str(e)}"
            return False, evaluation['reason'], evaluation

    def generate_approval_report(self, evaluation: Dict[str, Any]) -> str:
        """평가 결과 리포트 생성"""
        report = "=" * 60 + "\n"
        report += "🏆 Fortimove Golden Pass 평가 결과\n"
        report += "=" * 60 + "\n\n"

        if evaluation['auto_approved']:
            report += "✅ 자동 승인됨\n\n"
        else:
            report += "⏸️ 수동 검토 필요\n"
            report += f"사유: {evaluation['reason']}\n\n"

        report += "평가 항목:\n"
        for check_name, check_data in evaluation['checks'].items():
            status = "✅" if check_data['pass'] else "❌"
            report += f"\n{status} {check_name}:\n"
            report += f"   요구사항: {check_data['required']}\n"
            report += f"   실제값: {check_data['actual']}\n"

            if 'details' in check_data and check_data['details']:
                report += f"   상세: {check_data['details']}\n"

        report += "\n" + "=" * 60 + "\n"
        return report


def apply_auto_approval_to_workflow(workflow_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    워크플로우 결과에 자동 승인 로직 적용

    Returns:
        업데이트된 workflow_result (auto_approval 필드 추가)
    """
    engine = AutoApprovalEngine()
    approved, reason, evaluation = engine.evaluate(workflow_result)

    workflow_result['auto_approval'] = {
        'approved': approved,
        'reason': reason,
        'evaluation': evaluation,
        'timestamp': datetime.now().isoformat()
    }

    return workflow_result
