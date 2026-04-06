"""
Scoring Engine v2 — 감점 방식 (기본 통과 + 문제 발견 시 감점)

설계 철학:
- 기본 점수: 70점 (통과 선)
- 긍정 요소: +5~+15 가점
- 부정 요소: -5~-30 감점
- 중립 (데이터 없음): 기본값 유지

점수 구간:
- 85+: auto_approve (자동 승인)
- 65-84: review (검토 권장)
- 45-64: hold (보류, 개선 필요)
- <45: reject (거부)
"""

import logging
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ScoringEngine:
    """감점 방식 스코어링 엔진"""

    BASE_SCORE = 70  # 통과 기준

    def __init__(self):
        pass

    def score_product(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """상품 점수 계산 (감점 방식)"""
        try:
            review_id = review_data.get('review_id', 'unknown')
            logger.info(f"[{review_id}] 점수 계산 시작")

            # 데이터 경로 통합 파싱 (소싱 에이전트 출력 + 워크플로우 결과)
            context = self._parse_context(review_data)

            score = self.BASE_SCORE
            reasons = []
            breakdown = {'base': self.BASE_SCORE}

            # 1. 마진 점수 (±15점)
            delta, reason = self._score_margin(context)
            score += delta
            breakdown['margin'] = delta
            if reason:
                reasons.append(reason)

            # 2. 리스크 점수 (-30~0점)
            delta, reason = self._score_risk(context)
            score += delta
            breakdown['risk'] = delta
            if reason:
                reasons.append(reason)

            # 3. 브랜드 신뢰도 (0~+10점)
            delta, reason = self._score_brand(context)
            score += delta
            breakdown['brand'] = delta
            if reason:
                reasons.append(reason)

            # 4. 카테고리 적합성 (-10~+10점)
            delta, reason = self._score_category(context)
            score += delta
            breakdown['category'] = delta
            if reason:
                reasons.append(reason)

            # 5. 이미지/데이터 완성도 (0~+5점)
            delta, reason = self._score_completeness(context)
            score += delta
            breakdown['completeness'] = delta
            if reason:
                reasons.append(reason)

            # 6. 소싱 판정 (-20~+5점)
            delta, reason = self._score_sourcing_decision(context)
            score += delta
            breakdown['sourcing'] = delta
            if reason:
                reasons.append(reason)

            # 범위 제한
            score = max(0, min(100, score))

            # 의사결정
            decision = self._make_decision(score, breakdown)

            result = {
                'score': score,
                'decision': decision,
                'reasons': reasons,
                'breakdown': breakdown,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"[{review_id}] 점수: {score}, 결정: {decision}")
            return result

        except Exception as e:
            logger.error(f"점수 계산 실패: {e}", exc_info=True)
            return {
                'score': self.BASE_SCORE,
                'decision': 'review',
                'reasons': [f'점수 계산 오류: {str(e)} — 기본값 사용'],
                'breakdown': {'base': self.BASE_SCORE},
                'timestamp': datetime.now().isoformat()
            }

    def _parse_context(self, review_data: Dict) -> Dict:
        """다양한 데이터 경로에서 통합 컨텍스트 생성"""
        ctx = {
            'title': review_data.get('source_title', ''),
            'margin_rate': None,
            'risk_flags': [],
            'brand': None,
            'category': None,
            'sourcing_decision': None,
            'has_images': False,
            'has_description': False,
        }

        # source_data_json 파싱
        sd = review_data.get('source_data_json') or review_data.get('source_data') or {}
        if isinstance(sd, str):
            try:
                sd = json.loads(sd)
            except Exception:
                sd = {}

        # raw_agent_output 파싱
        rao = review_data.get('raw_agent_output') or {}
        if isinstance(rao, str):
            try:
                rao = json.loads(rao)
            except Exception:
                rao = {}

        # 워크플로우 all_results 경로 (sourcing/margin이 직접 output dict)
        all_results = sd.get('all_results', {}) if isinstance(sd, dict) else {}

        # 마진 데이터 (all_results.margin이 직접 margin 에이전트 output)
        margin_output = all_results.get('margin', {}) if isinstance(all_results, dict) else {}
        if not isinstance(margin_output, dict):
            margin_output = {}
        # 폴백: raw_agent_output
        if not margin_output and isinstance(rao, dict) and 'margin_analysis' in rao:
            margin_output = rao

        if margin_output:
            ma = margin_output.get('margin_analysis', {})
            rate = ma.get('net_margin_rate')
            if rate is None:
                rate = ma.get('margin_rate')
                if rate and rate < 1:
                    rate = rate * 100
            if rate is not None:
                ctx['margin_rate'] = float(rate)

        # 소싱 데이터 (all_results.sourcing이 직접 sourcing 에이전트 output)
        sourcing_output = all_results.get('sourcing', {}) if isinstance(all_results, dict) else {}
        if not isinstance(sourcing_output, dict):
            sourcing_output = {}

        if sourcing_output:
            ctx['sourcing_decision'] = sourcing_output.get('sourcing_decision')
            ctx['risk_flags'] = sourcing_output.get('risk_flags', []) or []

            extracted = sourcing_output.get('extracted_info', {})
            if isinstance(extracted, dict):
                ctx['brand'] = extracted.get('brand')
                cat = extracted.get('category')
                if isinstance(cat, dict):
                    ctx['category'] = cat.get('name')
                else:
                    ctx['category'] = cat
                images = extracted.get('images', [])
                ctx['has_images'] = bool(images and len(images) > 0)
                ctx['has_description'] = bool(extracted.get('description'))

        # 사용자 입력에서 카테고리 폴백
        if not ctx['category']:
            user_input = sd.get('input', {}) if isinstance(sd, dict) else {}
            ctx['category'] = user_input.get('category') or sd.get('category')

        return ctx

    # ── 각 항목별 스코어링 ────────────────────────────

    def _score_margin(self, ctx: Dict) -> Tuple[int, str]:
        """마진율 (±15점)"""
        rate = ctx.get('margin_rate')
        if rate is None:
            return 0, None  # 데이터 없음 — 중립

        if rate >= 50:
            return 15, f"매우 높은 마진율 ({rate:.0f}%)"
        elif rate >= 40:
            return 10, f"높은 마진율 ({rate:.0f}%)"
        elif rate >= 30:
            return 5, f"적정 마진율 ({rate:.0f}%)"
        elif rate >= 20:
            return 0, f"마진율 보통 ({rate:.0f}%)"
        elif rate >= 10:
            return -10, f"낮은 마진율 ({rate:.0f}%)"
        else:
            return -15, f"마진율 부족 ({rate:.0f}%)"

    def _score_risk(self, ctx: Dict) -> Tuple[int, str]:
        """리스크 플래그 (-30~0점)"""
        flags = ctx.get('risk_flags', [])
        if not flags:
            return 0, None

        critical = {'의료기기', '의약품', '화장품', 'medical_device', 'drug'}
        has_critical = any(f in critical for f in flags)

        if has_critical:
            return -30, f"치명적 리스크: {', '.join(flags[:3])}"
        elif len(flags) >= 3:
            return -15, f"다수 리스크 ({len(flags)}개): {', '.join(flags[:3])}"
        elif len(flags) >= 1:
            return -5, f"경미한 리스크: {', '.join(flags[:2])}"
        return 0, None

    def _score_brand(self, ctx: Dict) -> Tuple[int, str]:
        """브랜드 신뢰도 (+0~+10점)"""
        brand = ctx.get('brand')
        if not brand:
            return 0, None

        # 주요 신뢰 브랜드
        premium_brands = [
            'now foods', 'california gold', 'jarrow', 'life extension',
            'optimum nutrition', 'garden of life', 'nordic naturals',
            'pure encapsulations', 'thorne', 'nature\'s bounty',
            'sports research', 'kirkland', 'solgar', 'doctor\'s best'
        ]
        brand_lower = brand.lower() if isinstance(brand, str) else ''
        if any(pb in brand_lower for pb in premium_brands):
            return 10, f"신뢰 브랜드 ({brand})"
        elif brand_lower and brand_lower not in ('unknown', 'n/a', 'generic'):
            return 5, f"브랜드 확인 ({brand})"
        return 0, None

    def _score_category(self, ctx: Dict) -> Tuple[int, str]:
        """카테고리 적합성 (-10~+10점)"""
        category = (ctx.get('category') or '').lower()
        if not category:
            return 0, None

        # 핵심 웰니스 카테고리
        core = ['supplement', '영양', '비타민', 'vitamin', 'wellness', '웰니스',
                'omega', '오메가', 'protein', '단백질', '프로틴', 'nutrition']
        # 주변 카테고리
        adjacent = ['beauty', '뷰티', 'fitness', '피트니스', 'food', '식품', 'health', '건강']
        # 제외 카테고리
        excluded = ['electronics', '전자', 'clothing', '의류', 'fashion', '패션',
                    'automotive', '자동차', 'toy', '장난감']

        if any(c in category for c in core):
            return 10, f"핵심 카테고리 ({category[:30]})"
        elif any(c in category for c in adjacent):
            return 5, f"주변 카테고리 ({category[:30]})"
        elif any(c in category for c in excluded):
            return -10, f"부적합 카테고리 ({category[:30]})"
        return 0, None

    def _score_completeness(self, ctx: Dict) -> Tuple[int, str]:
        """데이터 완성도 (+0~+5점)"""
        score = 0
        parts = []
        if ctx.get('has_images'):
            score += 3
            parts.append("이미지 O")
        if ctx.get('has_description'):
            score += 2
            parts.append("설명 O")
        if score > 0:
            return score, f"데이터 완성도 ({', '.join(parts)})"
        return 0, None

    def _score_sourcing_decision(self, ctx: Dict) -> Tuple[int, str]:
        """소싱 에이전트 판정 (-20~+5점)"""
        decision = ctx.get('sourcing_decision')
        if not decision:
            return 0, None

        if decision in ('통과', 'pass', '등록 가능'):
            return 5, f"소싱 에이전트 통과"
        elif decision in ('보류', 'hold'):
            return -5, f"소싱 에이전트 보류"
        elif decision in ('거부', 'reject', '제외'):
            return -20, f"소싱 에이전트 거부"
        return 0, None

    def _make_decision(self, score: int, breakdown: Dict) -> str:
        """
        점수 기반 판정:
        - 85+: auto_approve
        - 65-84: review
        - 45-64: hold
        - <45: reject
        """
        # 치명적 리스크 체크
        if breakdown.get('risk', 0) <= -25:
            return 'reject'

        if score >= 85:
            return 'auto_approve'
        elif score >= 65:
            return 'review'
        elif score >= 45:
            return 'hold'
        else:
            return 'reject'


# ============================================================
# 테스트
# ============================================================
if __name__ == '__main__':
    engine = ScoringEngine()

    # 테스트 1: 데이터 없는 경우 (중립)
    result = engine.score_product({'review_id': 'test1', 'source_title': '테스트'})
    print(f"데이터 없음: {result['score']}점 / {result['decision']}")

    # 테스트 2: 정상 상품
    result = engine.score_product({
        'review_id': 'test2',
        'source_title': 'NOW Foods Vitamin C',
        'raw_agent_output': {
            'margin_analysis': {'net_margin_rate': 35},
            'final_decision': '등록 가능',
        },
        'source_data_json': {
            'all_results': {
                'sourcing': {'output': {
                    'sourcing_decision': '통과',
                    'risk_flags': [],
                    'extracted_info': {
                        'brand': 'NOW Foods',
                        'category': 'Supplements',
                        'images': ['url1', 'url2'],
                        'description': '고함량 비타민 C',
                    }
                }},
                'margin': {'output': {'margin_analysis': {'net_margin_rate': 35}}}
            }
        }
    })
    print(f"정상 상품: {result['score']}점 / {result['decision']}")
    for k, v in result['breakdown'].items():
        print(f"  {k}: {v:+d}")
