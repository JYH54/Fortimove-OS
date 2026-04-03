"""
상품 등록 가치 점수 시스템
============================
스마트스토어 1,000개 한도에서 어떤 상품을 등록할 가치가 있는지 판단

점수 = 마진점수(30) + 리스크점수(20) + 트렌드점수(20) + 경쟁점수(15) + 운영점수(15)

100점 만점:
  90+  : A등급 — 즉시 등록 (상세페이지 프리미엄 제작)
  70~89: B등급 — 등록 권장 (표준 상세페이지)
  50~69: C등급 — 보류 (개선 후 재평가)
  50 미만: D등급 — 등록 비추천 (한도 낭비)
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    total: float
    grade: str          # A/B/C/D
    decision: str       # 즉시등록/등록권장/보류/비추천
    breakdown: Dict[str, float]
    recommendations: List[str]


def calculate_product_score(
    margin_rate: float = 0,
    risk_flags: List[str] = None,
    sourcing_decision: str = "통과",
    trend_score: float = 0,        # Scout 트렌드 점수 (0~100)
    price_krw: float = 0,
    weight_kg: float = 0.5,
    category: str = "general",
    has_competitors: bool = True,
    is_seasonal: bool = False,
    reorder_potential: bool = False,  # 재구매 가능성
) -> ScoreResult:
    """
    상품 등록 가치 점수 계산

    Returns:
        ScoreResult with total score, grade, decision, breakdown
    """

    risk_flags = risk_flags or []
    breakdown = {}
    recommendations = []

    # ── 1. 마진 점수 (30점 만점) ──
    if margin_rate >= 40:
        margin_score = 30
    elif margin_rate >= 30:
        margin_score = 25
    elif margin_rate >= 25:
        margin_score = 20
    elif margin_rate >= 15:
        margin_score = 12
    else:
        margin_score = 5
        recommendations.append(f"마진율 {margin_rate:.1f}%로 낮음 — 원가 절감 또는 판매가 인상 검토")

    breakdown["margin"] = margin_score

    # ── 2. 리스크 점수 (20점 만점, 감점 방식) ──
    risk_score = 20
    if sourcing_decision == "제외":
        risk_score = 0
        recommendations.append("소싱 제외 판정 — 등록 불가")
    elif sourcing_decision == "보류":
        risk_score = 8
        recommendations.append("소싱 보류 — 리스크 해소 후 재평가 필요")
    else:
        # 리스크 플래그 개수에 따라 감점
        penalty = len(risk_flags) * 4
        risk_score = max(0, 20 - penalty)
        if risk_flags:
            recommendations.append(f"리스크 플래그: {', '.join(risk_flags)}")

    breakdown["risk"] = risk_score

    # ── 3. 트렌드/수요 점수 (20점 만점) ──
    if trend_score >= 80:
        trend_calc = 20
    elif trend_score >= 60:
        trend_calc = 16
    elif trend_score >= 40:
        trend_calc = 12
    elif trend_score > 0:
        trend_calc = 8
    else:
        trend_calc = 10  # 트렌드 데이터 없으면 중간값
        recommendations.append("트렌드 점수 미확인 — Daily Scout 데이터 확인 권장")

    breakdown["trend"] = trend_calc

    # ── 4. 경쟁/포지셔닝 점수 (15점 만점) ──
    competition_score = 10  # 기본
    if not has_competitors:
        competition_score = 15  # 경쟁 없음 = 블루오션
        recommendations.append("경쟁 상품 적음 — 선점 기회")
    elif price_krw < 15000:
        competition_score = 7  # 저가 경쟁 레드오션
        recommendations.append("저가 상품은 경쟁 치열 — 차별화 포인트 필수")
    elif price_krw > 50000:
        competition_score = 12  # 고가는 경쟁 적음
    if is_seasonal:
        competition_score = max(5, competition_score - 3)
        recommendations.append("시즌 상품 — 판매 기간 한정적")

    breakdown["competition"] = competition_score

    # ── 5. 운영 효율 점수 (15점 만점) ──
    ops_score = 10  # 기본
    if weight_kg <= 0.5:
        ops_score += 3  # 가벼운 상품 = 물류 효율
    elif weight_kg > 2.0:
        ops_score -= 3  # 무거운 상품 = 물류 부담
        recommendations.append("무게 2kg 초과 — 물류비 부담 주의")

    if reorder_potential:
        ops_score += 5  # 재구매 가능 = 안정적 매출
        recommendations.append("재구매 가능 상품 — 장기 매출 기대")

    # 카테고리 보너스
    high_demand_categories = ["wellness", "supplement", "beauty"]
    if category in high_demand_categories:
        ops_score = min(15, ops_score + 2)

    ops_score = max(0, min(15, ops_score))
    breakdown["operations"] = ops_score

    # ── 총점 ──
    total = sum(breakdown.values())

    # ── 등급 판정 ──
    if total >= 90:
        grade = "A"
        decision = "즉시등록"
        recommendations.insert(0, "A등급 — 프리미엄 상세페이지 + 광고 집행 권장")
    elif total >= 70:
        grade = "B"
        decision = "등록권장"
        recommendations.insert(0, "B등급 — 표준 상세페이지로 등록, 판매 추이 확인 후 광고")
    elif total >= 50:
        grade = "C"
        decision = "보류"
        recommendations.insert(0, "C등급 — 개선 후 재평가 (마진 인상 또는 리스크 해소)")
    else:
        grade = "D"
        decision = "비추천"
        recommendations.insert(0, "D등급 — 1,000개 한도 낭비, 등록하지 마세요")

    return ScoreResult(
        total=round(total, 1),
        grade=grade,
        decision=decision,
        breakdown=breakdown,
        recommendations=recommendations
    )


def print_score(result: ScoreResult, product_name: str = ""):
    """점수 결과 출력"""
    print(f"\n┌────────────────────────────────────────┐")
    print(f"│  상품 등록 가치 점수: {result.total:.0f}/100  [{result.grade}등급]  │")
    print(f"│  판정: {result.decision:<30} │")
    if product_name:
        print(f"│  상품: {product_name[:32]:<32} │")
    print(f"├────────────────────────────────────────┤")
    print(f"│  마진     {result.breakdown['margin']:>5.0f}/30                     │")
    print(f"│  리스크   {result.breakdown['risk']:>5.0f}/20                     │")
    print(f"│  트렌드   {result.breakdown['trend']:>5.0f}/20                     │")
    print(f"│  경쟁     {result.breakdown['competition']:>5.0f}/15                     │")
    print(f"│  운영효율 {result.breakdown['operations']:>5.0f}/15                     │")
    print(f"└────────────────────────────────────────┘")

    if result.recommendations:
        print(f"\n  권고사항:")
        for r in result.recommendations:
            print(f"  • {r}")


if __name__ == "__main__":
    # 테스트: A등급 상품
    result_a = calculate_product_score(
        margin_rate=38, risk_flags=[], sourcing_decision="통과",
        trend_score=85, price_krw=29900, weight_kg=0.15,
        category="wellness", reorder_potential=True
    )
    print_score(result_a, "콜라겐 펩타이드 분말 100g")

    # 테스트: C등급 상품
    result_c = calculate_product_score(
        margin_rate=18, risk_flags=["KC인증필수"], sourcing_decision="통과",
        trend_score=40, price_krw=12900, weight_kg=0.8
    )
    print_score(result_c, "무선 충전식 칫솔")
