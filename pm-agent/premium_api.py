"""
Premium 도구 API 라우터
========================
CLI 도구들을 HTTP API로도 사용할 수 있게 노출

엔드포인트:
  POST /api/premium/analyze     — 초퀄리티 상세페이지 + 광고 전략
  POST /api/keyword/research    — 키워드 리서치
  POST /api/review/analyze      — 리뷰 분석
  GET  /api/cache/stats          — 캐시 통계
  DELETE /api/cache/clear        — 캐시 초기화
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================

class PremiumRequest(BaseModel):
    title: str = Field(..., description="상품명")
    price_cny: float = Field(..., description="매입가 (소싱국 통화)")
    category: str = Field(default="general")
    source_country: str = Field(default="CN", description="소싱국 (CN/US/JP/VN)")
    description: str = Field(default="")
    target_customer: str = Field(default="")
    key_features: List[str] = Field(default_factory=list)
    competitors: List[str] = Field(default_factory=list)
    weight_kg: float = Field(default=0.5)


class KeywordRequest(BaseModel):
    keyword: str = Field(..., description="검색 키워드")
    category: str = Field(default="general")
    price_range: str = Field(default="")
    daily_budget: int = Field(default=0)


class ReviewRequest(BaseModel):
    reviews: List[str] = Field(..., description="리뷰 텍스트 목록")
    product_name: str = Field(default="")


# ============================================================
# Premium Endpoints
# ============================================================

@router.post("/api/premium/analyze")
def analyze_premium(req: PremiumRequest):
    """초퀄리티 상세페이지 + 광고 전략 생성"""
    try:
        # 소싱 리스크
        from agent_framework import AgentRegistry
        registry = AgentRegistry()
        sourcing = registry.get("sourcing")
        sourcing_result = None
        if sourcing:
            sr = sourcing.execute({
                "source_url": "",
                "source_title": req.title,
                "source_price_cny": req.price_cny,
                "market": "korea"
            })
            if sr.is_success():
                sourcing_result = sr.output

        # 마진 계산
        pricing = registry.get("pricing")
        pricing_result = None
        if pricing:
            pr = pricing.execute({
                "source_price_cny": req.price_cny,
                "source_country": req.source_country,
                "category": req.category,
                "weight_kg": req.weight_kg,
            })
            if pr.is_success():
                pricing_result = pr.output

        price_krw = int(pricing_result.get("final_price", 19900)) if pricing_result else 19900
        margin_rate = pricing_result.get("margin_rate", 0) if pricing_result else 0

        # 등록 가치 점수
        from product_score import calculate_product_score
        score = calculate_product_score(
            margin_rate=margin_rate,
            risk_flags=sourcing_result.get("risk_flags", []) if sourcing_result else [],
            sourcing_decision=sourcing_result.get("sourcing_decision", "통과") if sourcing_result else "통과",
            price_krw=price_krw,
            category=req.category,
        )

        # 상세페이지 생성
        from premium_detail_page import PremiumDetailPageGenerator
        gen = PremiumDetailPageGenerator()
        detail = gen.generate(
            title=req.title,
            price_krw=price_krw,
            category=req.category,
            description=req.description,
            target_customer=req.target_customer,
            key_features=req.key_features,
            competitors=req.competitors,
            margin_rate=margin_rate,
            source_country=req.source_country,
        )

        return {
            "status": "completed",
            "sourcing": sourcing_result,
            "pricing": pricing_result,
            "score": {"total": score.total, "grade": score.grade, "decision": score.decision},
            "detail_page": detail,
        }

    except Exception as e:
        logger.error(f"Premium API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/keyword/research")
def research_keyword(req: KeywordRequest):
    """키워드 리서치"""
    try:
        from keyword_research import KeywordResearcher
        researcher = KeywordResearcher()
        result = researcher.research(
            keyword=req.keyword,
            category=req.category,
            price_range=req.price_range,
            daily_budget=req.daily_budget,
        )
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"Keyword API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/review/analyze")
def analyze_reviews(req: ReviewRequest):
    """리뷰 분석"""
    try:
        from review_analyzer import ReviewAnalyzer
        analyzer = ReviewAnalyzer()
        result = analyzer.analyze(req.reviews, req.product_name)
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"Review API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cache/stats")
def get_cache_stats():
    """캐시 통계"""
    try:
        from cache_manager import LLMCache
        cache = LLMCache()
        return cache.stats()
    except Exception as e:
        return {"error": str(e)}


@router.delete("/api/cache/clear")
def clear_cache():
    """캐시 전체 초기화"""
    try:
        from cache_manager import LLMCache
        cache = LLMCache()
        count = cache.clear_all()
        return {"cleared": count}
    except Exception as e:
        return {"error": str(e)}
