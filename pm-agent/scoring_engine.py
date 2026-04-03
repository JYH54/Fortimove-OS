"""
Scoring Engine - 상품 자동 점수화 및 의사결정
100% 규칙 기반, LLM 사용 없음, Explainable AI
"""

import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    상품 자동 점수화 엔진

    점수 범위: 0-100점
    항목:
        - margin_score: 0-35점 (마진율)
        - policy_risk_score: 0-25점 (정책 위험)
        - certification_risk_score: 0-15점 (인증 위험)
        - sourcing_stability_score: 0-15점 (소싱 안정성)
        - option_complexity_score: 0-5점 (옵션 복잡도, 낮을수록 좋음)
        - category_fit_score: 0-5점 (카테고리 적합성)
        - competition_score: 0-0점 (경쟁 강도, 향후 구현)

    Decision:
        - auto_approve: 80점 이상
        - review: 60-79점
        - hold: 40-59점
        - reject: 40점 미만
    """

    def __init__(self):
        self.max_scores = {
            'margin': 35,
            'policy_risk': 25,
            'certification_risk': 15,
            'sourcing_stability': 15,
            'option_complexity': 5,
            'category_fit': 5,
            'competition': 0  # 향후 구현
        }

    def score_product(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        상품 점수 계산

        Args:
            review_data: {
                'review_id': str,
                'source_type': str,
                'agent_output': dict,  # sourcing, margin 결과
                'source_data': dict  # 원본 데이터
            }

        Returns:
            {
                'score': int (0-100),
                'decision': str,
                'reasons': List[str],
                'breakdown': Dict[str, int],
                'timestamp': str
            }
        """
        try:
            logger.info(f"[{review_data['review_id']}] 점수 계산 시작")

            # 에이전트 출력 파싱
            agent_output = review_data.get('agent_output', {})
            source_data = review_data.get('source_data', {})

            # 각 항목별 점수 계산
            scores = {}
            reasons = []

            # 1. 마진 점수 (0-35점)
            margin_score, margin_reason = self._score_margin(agent_output, source_data)
            scores['margin_score'] = margin_score
            reasons.append(margin_reason)

            # 2. 정책 위험 점수 (0-25점)
            policy_score, policy_reason = self._score_policy_risk(agent_output)
            scores['policy_risk_score'] = policy_score
            reasons.append(policy_reason)

            # 3. 인증 위험 점수 (0-15점)
            cert_score, cert_reason = self._score_certification_risk(agent_output)
            scores['certification_risk_score'] = cert_score
            reasons.append(cert_reason)

            # 4. 소싱 안정성 점수 (0-15점)
            sourcing_score, sourcing_reason = self._score_sourcing_stability(agent_output, source_data)
            scores['sourcing_stability_score'] = sourcing_score
            reasons.append(sourcing_reason)

            # 5. 옵션 복잡도 점수 (0-5점, 낮을수록 좋음)
            option_score, option_reason = self._score_option_complexity(source_data)
            scores['option_complexity_score'] = option_score
            reasons.append(option_reason)

            # 6. 카테고리 적합성 점수 (0-5점)
            category_score, category_reason = self._score_category_fit(source_data)
            scores['category_fit_score'] = category_score
            reasons.append(category_reason)

            # 7. 경쟁 강도 점수 (0-0점, 향후 구현)
            scores['competition_score'] = 0

            # 총점 계산
            total_score = sum(scores.values())

            # 의사결정
            decision = self._make_decision(total_score, scores)

            result = {
                'score': total_score,
                'decision': decision,
                'reasons': reasons,
                'breakdown': scores,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"[{review_data['review_id']}] 점수: {total_score}, 결정: {decision}")

            return result

        except Exception as e:
            logger.error(f"점수 계산 실패: {e}", exc_info=True)
            return {
                'score': 0,
                'decision': 'hold',
                'reasons': [f'점수 계산 오류: {str(e)}'],
                'breakdown': {},
                'timestamp': datetime.now().isoformat()
            }

    def _score_margin(self, agent_output: Dict, source_data: Dict) -> Tuple[int, str]:
        """마진율 점수 (0-35점)"""
        try:
            # margin 결과에서 margin_rate 추출
            margin_result = agent_output.get('margin', {})
            margin_analysis = margin_result.get('margin_analysis', {})
            margin_rate = margin_analysis.get('margin_rate', 0)

            if margin_rate >= 0.50:
                return 35, f"매우 높은 마진율 ({margin_rate:.1%}): +35점"
            elif margin_rate >= 0.40:
                return 30, f"높은 마진율 ({margin_rate:.1%}): +30점"
            elif margin_rate >= 0.30:
                return 20, f"적정 마진율 ({margin_rate:.1%}): +20점"
            elif margin_rate >= 0.20:
                return 10, f"낮은 마진율 ({margin_rate:.1%}): +10점"
            else:
                return 0, f"마진율 부족 ({margin_rate:.1%}): 0점"

        except Exception as e:
            logger.warning(f"마진 점수 계산 오류: {e}")
            return 0, "마진 정보 없음: 0점"

    def _score_policy_risk(self, agent_output: Dict) -> Tuple[int, str]:
        """정책 위험 점수 (0-25점)"""
        try:
            sourcing_result = agent_output.get('sourcing', {})
            policy_risks = sourcing_result.get('policy_risks', [])

            if isinstance(policy_risks, list):
                risk_count = len(policy_risks)
            else:
                risk_count = 0

            if risk_count == 0:
                return 25, "정책 위험 없음: +25점"
            elif risk_count == 1:
                return 20, f"경미한 정책 위험 (1개): +20점"
            elif risk_count == 2:
                return 15, f"경미한 정책 위험 (2개): +15점"
            elif risk_count <= 4:
                return 5, f"중간 정책 위험 ({risk_count}개): +5점"
            else:
                return 0, f"심각한 정책 위험 ({risk_count}개): 0점"

        except Exception as e:
            logger.warning(f"정책 위험 점수 계산 오류: {e}")
            return 15, "정책 위험 정보 불명: +15점 (중립)"

    def _score_certification_risk(self, agent_output: Dict) -> Tuple[int, str]:
        """인증 위험 점수 (0-15점)"""
        try:
            sourcing_result = agent_output.get('sourcing', {})
            cert_required = sourcing_result.get('certification_required', False)

            if not cert_required:
                return 15, "인증 불필요: +15점"
            else:
                return 5, "인증 필요: +5점"

        except Exception as e:
            logger.warning(f"인증 위험 점수 계산 오류: {e}")
            return 10, "인증 정보 불명: +10점 (중립)"

    def _score_sourcing_stability(self, agent_output: Dict, source_data: Dict) -> Tuple[int, str]:
        """소싱 안정성 점수 (0-15점)"""
        try:
            sourcing_result = agent_output.get('sourcing', {})
            sourcing_decision = sourcing_result.get('sourcing_decision', '')

            # 소싱 결정이 '통과'인 경우
            if sourcing_decision == '통과':
                # 추가 조건: 브랜드 또는 정규 URL
                source_url = source_data.get('source_url', '')
                brand = source_data.get('brand', '')

                if brand and brand.lower() not in ['unknown', 'n/a', '']:
                    return 15, "소싱 안정성 높음 (브랜드 확인): +15점"
                elif 'taobao.com' in source_url or 'tmall.com' in source_url:
                    return 13, "소싱 안정성 높음 (타오바오/티몰): +13점"
                else:
                    return 10, "소싱 안정성 중간: +10점"

            # 소싱 결정이 '보류'인 경우
            elif sourcing_decision == '보류':
                return 5, "소싱 안정성 낮음 (보류): +5점"

            # 소싱 결정이 '거부'인 경우
            else:
                return 0, "소싱 안정성 없음 (거부): 0점"

        except Exception as e:
            logger.warning(f"소싱 안정성 점수 계산 오류: {e}")
            return 7, "소싱 정보 불명: +7점 (중립)"

    def _score_option_complexity(self, source_data: Dict) -> Tuple[int, str]:
        """옵션 복잡도 점수 (0-5점, 낮을수록 좋음 - 감점 방식)"""
        try:
            options = source_data.get('source_options', [])

            if isinstance(options, list):
                option_count = len(options)
            else:
                option_count = 0

            if option_count == 0:
                return 5, "옵션 없음 (단일 상품): +5점"
            elif option_count <= 3:
                return 4, f"옵션 단순 ({option_count}개): +4점"
            elif option_count <= 6:
                return 2, f"옵션 보통 ({option_count}개): +2점"
            else:
                return 0, f"옵션 복잡 ({option_count}개): 0점"

        except Exception as e:
            logger.warning(f"옵션 복잡도 점수 계산 오류: {e}")
            return 3, "옵션 정보 불명: +3점 (중립)"

    def _score_category_fit(self, source_data: Dict) -> Tuple[int, str]:
        """카테고리 적합성 점수 (0-5점)"""
        try:
            category = source_data.get('category', '').lower()

            # 우선 카테고리 (헬스케어, 주방, 생활용품)
            priority_categories = [
                'health', 'wellness', 'kitchen', 'home', 'beauty',
                '건강', '웰니스', '주방', '생활', '뷰티'
            ]

            # 제외 카테고리 (전자제품, 의류)
            excluded_categories = [
                'electronics', 'clothing', 'fashion',
                '전자', '의류', '패션'
            ]

            if any(cat in category for cat in priority_categories):
                return 5, f"우선 카테고리 ({category}): +5점"
            elif any(cat in category for cat in excluded_categories):
                return 0, f"제외 카테고리 ({category}): 0점"
            else:
                return 3, f"일반 카테고리 ({category}): +3점"

        except Exception as e:
            logger.warning(f"카테고리 적합성 점수 계산 오류: {e}")
            return 3, "카테고리 정보 불명: +3점 (중립)"

    def _make_decision(self, score: int, breakdown: Dict[str, int]) -> str:
        """
        점수 기반 자동 결정

        Rules:
            - 80점 이상: auto_approve (자동 승인)
            - 60-79점: review (인간 검토 필요)
            - 40-59점: hold (보류, 개선 후 재검토)
            - 40점 미만: reject (거부)

        단, 치명적 결함이 있으면 점수와 관계없이 reject
        """
        # 치명적 결함 체크
        if breakdown.get('policy_risk_score', 0) == 0:
            if score < 60:
                return 'reject'  # 정책 위험 + 저점수 = 거부

        if breakdown.get('margin_score', 0) == 0:
            if score < 50:
                return 'reject'  # 마진 없음 + 저점수 = 거부

        # 점수 기반 결정
        if score >= 80:
            return 'auto_approve'
        elif score >= 60:
            return 'review'
        elif score >= 40:
            return 'hold'
        else:
            return 'reject'


# ============================================================
# 사용 예시
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 테스트 데이터
    test_data = {
        'review_id': 'test-123',
        'source_type': 'workflow:quick_sourcing_check',
        'agent_output': {
            'sourcing': {
                'sourcing_decision': '통과',
                'policy_risks': [],
                'certification_required': False
            },
            'margin': {
                'margin_analysis': {
                    'margin_rate': 0.45,
                    'target_price': 15900
                }
            }
        },
        'source_data': {
            'source_url': 'https://item.taobao.com/item.htm?id=123456',
            'source_price_cny': 30.0,
            'weight_kg': 0.5,
            'category': 'kitchen',
            'brand': 'Test Brand',
            'source_options': ['옵션1', '옵션2']
        }
    }

    engine = ScoringEngine()
    result = engine.score_product(test_data)

    print("\n=== 점수화 결과 ===")
    print(f"총점: {result['score']}점")
    print(f"결정: {result['decision']}")
    print(f"\n이유:")
    for reason in result['reasons']:
        print(f"  - {reason}")
    print(f"\n상세 점수:")
    for key, value in result['breakdown'].items():
        print(f"  {key}: {value}점")
