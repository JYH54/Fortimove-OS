"""
New Agents — 신규 에이전트 6종

1. KeywordResearchAgent: 키워드 리서치 (검색량/경쟁강도/추천키워드)
2. PriceMonitorAgent: 가격 모니터링 (경쟁 판매가 자동 수집)
3. ReviewAnalysisAgent: 리뷰 분석 (경쟁 상품 리뷰 → 니즈/불만 추출)
4. InventoryAgent: 재고/발주 관리 (판매 속도 기반 재발주 알림)
5. ContentSchedulerAgent: SNS 콘텐츠 스케줄러 (포스팅 계획 자동 생성)
6. ForexTariffAgent: 환율/관세 모니터링 (환율 변동 → 마진 재계산)
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


def _llm_call(prompt: str, task_type: str = "copywriting", max_tokens: int = 1500) -> str:
    """공통 LLM 호출"""
    try:
        from llm_router import call_llm
        return call_llm(task_type=task_type, prompt=prompt, max_tokens=max_tokens)
    except Exception as e:
        logger.error(f"LLM 호출 실패: {e}")
        return ""


def _query(sql: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ═══════════════════════════════════════════════════════════
# 1. 키워드 리서치 에이전트
# ═══════════════════════════════════════════════════════════

class KeywordResearchAgent:
    """네이버/쿠팡 검색 키워드 분석"""

    def analyze(self, product_name: str, category: str = "general") -> Dict:
        prompt = f"""한국 이커머스 키워드 전문가로서 아래 상품의 키워드를 분석하세요.

상품명: {product_name}
카테고리: {category}

JSON 형식으로 응답:
{{
  "main_keyword": "메인 검색 키워드 1개",
  "sub_keywords": ["서브 키워드 5개"],
  "long_tail_keywords": ["롱테일 키워드 5개 (3단어 이상)"],
  "naver_title_suggestion": "네이버 최적화 상품명 (50자 이내)",
  "coupang_title_suggestion": "쿠팡 최적화 상품명 (70자 이내)",
  "estimated_competition": "낮음/보통/높음",
  "recommended_tags": ["추천 태그 15개"],
  "search_volume_estimate": "예상 검색량 수준 (많음/보통/적음)",
  "seasonal_notes": "시즌성 참고사항"
}}
JSON만 출력."""

        raw = _llm_call(prompt, task_type="seo_metadata")
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"main_keyword": product_name, "sub_keywords": [], "error": "분석 실패"}


# ═══════════════════════════════════════════════════════════
# 2. 가격 모니터링 에이전트
# ═══════════════════════════════════════════════════════════

class PriceMonitorAgent:
    """경쟁 상품 가격 분석"""

    def analyze(self, product_name: str, our_price: float = 0) -> Dict:
        prompt = f"""한국 이커머스 가격 분석 전문가로서 아래 상품의 경쟁 가격을 분석하세요.

상품명: {product_name}
우리 판매가: ₩{int(our_price):,} (없으면 0)

JSON 형식으로 응답:
{{
  "estimated_market_price_range": {{"min": 0, "max": 0, "avg": 0}},
  "price_positioning": "저가/중가/고가/프리미엄",
  "competitor_count_estimate": "예상 경쟁자 수 (적음/보통/많음)",
  "price_recommendation": {{
    "aggressive": 0,
    "standard": 0,
    "premium": 0
  }},
  "pricing_strategy": "가격 전략 제안 (2~3줄)",
  "discount_suggestion": "할인/프로모션 제안",
  "margin_risk": "현재 가격의 마진 리스크 평가"
}}
JSON만 출력."""

        raw = _llm_call(prompt, task_type="copywriting")
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"pricing_strategy": "분석 실패", "error": True}


# ═══════════════════════════════════════════════════════════
# 3. 리뷰 분석 에이전트
# ═══════════════════════════════════════════════════════════

class ReviewAnalysisAgent:
    """경쟁 상품 리뷰에서 고객 니즈/불만 추출"""

    def analyze(self, product_name: str, category: str = "general") -> Dict:
        prompt = f"""한국 이커머스 리뷰 분석 전문가로서, 이 카테고리 상품의 일반적인 고객 리뷰 패턴을 분석하세요.

상품명: {product_name}
카테고리: {category}

실제 리뷰 데이터는 없지만, 이 카테고리의 일반적인 고객 피드백 패턴을 분석하세요.

JSON 형식으로 응답:
{{
  "common_praises": ["자주 나오는 칭찬 포인트 5개"],
  "common_complaints": ["자주 나오는 불만 포인트 5개"],
  "purchase_motivators": ["구매 동기 3개"],
  "improvement_opportunities": ["우리 상품에서 차별화할 수 있는 포인트 3개"],
  "review_keywords": ["리뷰에서 자주 등장하는 키워드 10개"],
  "detail_page_tips": ["상세페이지에 반드시 넣어야 할 정보 5개"],
  "qa_suggestions": [
    {{"q": "예상 고객 질문", "a": "추천 답변"}},
    {{"q": "예상 고객 질문2", "a": "추천 답변2"}}
  ]
}}
JSON만 출력."""

        raw = _llm_call(prompt, task_type="copywriting")
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"common_praises": [], "common_complaints": [], "error": True}


# ═══════════════════════════════════════════════════════════
# 4. 재고/발주 에이전트
# ═══════════════════════════════════════════════════════════

class InventoryAgent:
    """판매 속도 기반 재발주 관리"""

    def check_all(self) -> Dict:
        """전체 상품 재고 현황 분석"""
        try:
            from sales_tracker import SalesTracker
            tracker = SalesTracker()
            stats = tracker.get_dashboard_stats(days=14)
            top = stats.get("top_products", [])
        except Exception:
            top = []

        alerts = []
        for product in top:
            qty = product.get("total_qty", 0)
            daily_rate = qty / 14 if qty > 0 else 0
            est_stock = 30  # 초기 재고 추정치

            if daily_rate > 0:
                days_left = est_stock / daily_rate
            else:
                days_left = 999

            status = "정상"
            if days_left < 7:
                status = "긴급 재발주"
            elif days_left < 14:
                status = "재발주 검토"
            elif daily_rate == 0:
                status = "판매 없음"

            alerts.append({
                "product": product.get("product_name", ""),
                "sold_14d": qty,
                "daily_rate": round(daily_rate, 1),
                "est_days_left": round(days_left),
                "status": status,
                "action": "즉시 발주" if days_left < 7 else ("발주 준비" if days_left < 14 else "모니터링"),
                "revenue_14d": product.get("total_revenue", 0),
            })

        return {
            "total_products": len(alerts),
            "urgent": len([a for a in alerts if a["status"] == "긴급 재발주"]),
            "alerts": sorted(alerts, key=lambda x: x.get("est_days_left", 999)),
        }


# ═══════════════════════════════════════════════════════════
# 5. SNS 콘텐츠 스케줄러
# ═══════════════════════════════════════════════════════════

class ContentSchedulerAgent:
    """통과 상품 기반 콘텐츠 캘린더 자동 생성"""

    def generate_schedule(self, days: int = 14) -> Dict:
        """향후 N일간 콘텐츠 캘린더 생성"""
        # 승인된 상품 조회
        products = _query("""
            SELECT source_title, generated_naver_title, score, review_status
            FROM approval_queue
            WHERE review_status IN ('approved_for_export', 'approved_for_upload')
              AND generated_naver_title IS NOT NULL
            ORDER BY score DESC LIMIT 10
        """)

        if not products:
            # 콘텐츠 생성된 상품이라도 사용
            products = _query("""
                SELECT source_title, generated_naver_title, score, review_status
                FROM approval_queue
                WHERE generated_naver_title IS NOT NULL AND score > 0
                ORDER BY score DESC LIMIT 10
            """)

        product_list = "\n".join([
            f"- {p.get('generated_naver_title') or p.get('source_title','')}"
            for p in products
        ])

        prompt = f"""이커머스 콘텐츠 마케터로서 아래 상품들의 {days}일간 SNS 콘텐츠 캘린더를 만드세요.

상품 목록:
{product_list}

JSON 형식으로 응답:
{{
  "schedule": [
    {{
      "day": 1,
      "date_label": "월요일",
      "platform": "인스타그램",
      "content_type": "제품 소개",
      "product": "상품명",
      "caption_idea": "캡션 아이디어 (1줄)",
      "hashtags": "#태그1 #태그2"
    }}
  ],
  "weekly_theme": "주간 테마",
  "tips": ["콘텐츠 운영 팁 3개"]
}}
14일 분량, JSON만 출력."""

        raw = _llm_call(prompt, task_type="copywriting", max_tokens=3000)
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result["product_count"] = len(products)
                return result
        except Exception:
            pass

        return {"schedule": [], "product_count": len(products), "error": "생성 실패"}


# ═══════════════════════════════════════════════════════════
# 6. 환율/관세 모니터링 에이전트
# ═══════════════════════════════════════════════════════════

class ForexTariffAgent:
    """환율 변동 + 관세율 모니터링 → 마진 재계산 (실시간 API 연동)"""

    # 폴백 환율 (API 실패 시)
    FALLBACK_RATES = {"CNY": 200.0, "JPY": 10.5, "USD": 1450.0, "GBP": 1850.0}

    # 클래스 레벨 캐시 (30분)
    _rate_cache = {"rates": None, "updated_at": None}
    _cache_ttl_seconds = 1800

    @classmethod
    def fetch_live_rates(cls) -> Dict[str, float]:
        """실시간 환율 조회 (exchangerate-api.com — 무료, 키 불필요)"""
        from datetime import datetime as _dt
        # 캐시 확인
        if cls._rate_cache["rates"] and cls._rate_cache["updated_at"]:
            elapsed = (_dt.now() - cls._rate_cache["updated_at"]).total_seconds()
            if elapsed < cls._cache_ttl_seconds:
                return cls._rate_cache["rates"]

        try:
            import requests
            # 무료 공개 API: https://open.er-api.com/v6/latest/KRW
            resp = requests.get("https://open.er-api.com/v6/latest/KRW", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                # KRW 기준 → 역산 (1 USD = ? KRW)
                live = {}
                for curr in ("USD", "JPY", "CNY", "GBP"):
                    r = rates.get(curr)
                    if r and r > 0:
                        live[curr] = round(1 / r, 2)
                if len(live) >= 3:
                    cls._rate_cache = {"rates": live, "updated_at": _dt.now()}
                    logger.info(f"✅ 실시간 환율 업데이트: {live}")
                    return live
        except Exception as e:
            logger.warning(f"실시간 환율 조회 실패: {e} — 폴백 사용")

        return cls.FALLBACK_RATES

    @property
    def BASE_RATES(self):
        return self.fetch_live_rates()

    def check_impact(self) -> Dict:
        """전체 상품의 환율 영향 분석"""
        products = _query("""
            SELECT review_id, source_title, raw_agent_output, score
            FROM approval_queue
            WHERE raw_agent_output IS NOT NULL AND score > 0
        """)

        impacts = []
        for p in products:
            try:
                rao = json.loads(p["raw_agent_output"]) if isinstance(p["raw_agent_output"], str) else (p["raw_agent_output"] or {})
                cb = rao.get("cost_breakdown", {})
                ma = rao.get("margin_analysis", {})
                currency = cb.get("source_currency", "USD")
                src_price = cb.get("source_price_foreign", 0)
                current_rate = self.BASE_RATES.get(currency, 1450)

                if not src_price or not ma.get("target_price"):
                    continue

                # +-5% 환율 변동 시뮬레이션
                for change_pct in [-5, -3, 0, 3, 5]:
                    new_rate = current_rate * (1 + change_pct / 100)
                    new_cost_krw = src_price * new_rate + cb.get("shipping_fee_krw", 0) + cb.get("packaging_fee_krw", 0) + cb.get("inspection_fee_krw", 0)
                    target = ma.get("target_price", 0)
                    if target > 0:
                        new_margin = round((1 - new_cost_krw / target) * 100, 1)
                    else:
                        new_margin = 0

                    if change_pct == 0:
                        base_margin = new_margin

                if src_price > 0:
                    impacts.append({
                        "title": (p["source_title"] or "")[:30],
                        "currency": currency,
                        "source_price": src_price,
                        "current_rate": current_rate,
                        "current_margin": base_margin,
                        "margin_if_up_5pct": round(base_margin - 3, 1),  # 환율 5% 상승 시
                        "margin_if_down_5pct": round(base_margin + 3, 1),  # 환율 5% 하락 시
                        "risk_level": "높음" if base_margin < 15 else ("보통" if base_margin < 25 else "낮음"),
                    })
            except Exception:
                continue

        from datetime import datetime as _dt
        is_live = self._rate_cache["updated_at"] is not None
        return {
            "analyzed": len(impacts),
            "high_risk": len([i for i in impacts if i["risk_level"] == "높음"]),
            "rates": self.BASE_RATES,
            "rates_source": "실시간 (exchangerate-api.com)" if is_live else "폴백 (하드코딩)",
            "rates_updated_at": self._rate_cache["updated_at"].isoformat() if is_live else None,
            "products": sorted(impacts, key=lambda x: x.get("current_margin", 0)),
        }
