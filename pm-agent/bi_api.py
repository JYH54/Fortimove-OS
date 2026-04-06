"""
BI & FinOps API — 전사 경영 인텔리전스 + AI 비용 통제
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bi", tags=["BI-FinOps"])

# CORS 추가 (브라우저 확장 프로그램용)
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


def _query(sql: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _query_one(sql: str, params: tuple = ()):
    rows = _query(sql, params)
    return rows[0] if rows else {}


# ═══════════════════════════════════════════════════════════
# BI: 전사 경영 대시보드
# ═══════════════════════════════════════════════════════════

@router.get("/overview")
async def bi_overview():
    """전사 KPI 개요"""
    # 상품 파이프라인 현황
    pipeline = _query_one("""
        SELECT
            COUNT(*) as total_products,
            SUM(CASE WHEN review_status='draft' THEN 1 ELSE 0 END) as draft,
            SUM(CASE WHEN review_status='under_review' THEN 1 ELSE 0 END) as under_review,
            SUM(CASE WHEN review_status='approved_for_export' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN review_status='rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN review_status='hold' THEN 1 ELSE 0 END) as hold,
            SUM(CASE WHEN content_status='completed' THEN 1 ELSE 0 END) as content_done,
            ROUND(AVG(CASE WHEN score > 0 THEN score END), 1) as avg_score,
            MAX(score) as max_score,
            MIN(CASE WHEN score > 0 THEN score END) as min_score
        FROM approval_queue
    """)

    # 리디자인 현황
    redesign = _query_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) as processing,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed
        FROM redesign_queue
    """)

    # 7일간 일별 처리량
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    daily = _query("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM approval_queue WHERE created_at >= ?
        GROUP BY DATE(created_at) ORDER BY date
    """, (week_ago,))

    return {
        "timestamp": datetime.now().isoformat(),
        "pipeline": pipeline,
        "redesign": redesign,
        "daily_volume_7d": daily,
    }


@router.get("/agent-performance")
async def agent_performance():
    """에이전트별 성과 — 재무적 가치 환산"""
    # 에이전트 실행 통계
    try:
        status_file = Path(__file__).parent / "pm-agent-data" / "agent-status" / "agent_status.json"
        if status_file.exists():
            raw = json.loads(status_file.read_text())
            agents = raw.get("agents", raw) if isinstance(raw, dict) else {}
        else:
            agents = {}
    except Exception:
        agents = {}

    # 마진 데이터에서 AI가 발견한 추가 이익 계산
    margin_products = _query("""
        SELECT source_title, score, raw_agent_output
        FROM approval_queue
        WHERE raw_agent_output IS NOT NULL AND score > 0
    """)

    total_margin_value = 0
    total_risk_blocked = 0
    product_details = []

    for item in margin_products:
        try:
            rao = item.get("raw_agent_output") or "{}"
            if isinstance(rao, str):
                rao = json.loads(rao)
            if not isinstance(rao, dict):
                rao = {}
            ma = rao.get("margin_analysis", {})
            net_profit = ma.get("net_profit", 0)
            risk_warnings = rao.get("risk_warnings", [])

            if net_profit > 0:
                total_margin_value += net_profit
            if risk_warnings:
                total_risk_blocked += 1

            product_details.append({
                "title": (item["source_title"] or "")[:30],
                "score": item["score"],
                "margin_profit": round(net_profit),
                "risks_detected": len(risk_warnings),
                "decision": rao.get("final_decision", ""),
            })
        except Exception:
            pass

    # 리스크 방어 가치 (소싱 에이전트가 차단한 리스크)
    risk_products = _query("""
        SELECT COUNT(*) as cnt FROM approval_queue
        WHERE score < 40 OR decision = 'reject'
    """)
    risk_blocked_count = risk_products[0].get("cnt", 0) if risk_products else 0

    # 에이전트별 성과
    agent_stats = []
    for name, info in agents.items():
        if not isinstance(info, dict):
            continue
        total = info.get("total_executions", 0) or 0
        success = info.get("success_count", 0) or 0
        fail = info.get("failure_count", 0) or 0
        agent_stats.append({
            "name": name,
            "display_name": info.get("name", name),
            "total_runs": total,
            "success": success,
            "failure": fail,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "status": info.get("status", "unknown"),
        })

    return {
        "financial_impact": {
            "total_margin_discovered_krw": round(total_margin_value),
            "avg_margin_per_product_krw": round(total_margin_value / len(product_details)) if product_details else 0,
            "risk_blocked_count": risk_blocked_count,
            "risk_blocked_value_est_krw": risk_blocked_count * 500000,  # 건당 제재/손실 추정 50만원
            "products_analyzed": len(product_details),
        },
        "agent_stats": sorted(agent_stats, key=lambda x: x["total_runs"], reverse=True),
        "top_products": sorted(product_details, key=lambda x: x["margin_profit"], reverse=True)[:10],
    }


@router.get("/content-analytics")
async def content_analytics():
    """콘텐츠 생성 분석"""
    content = _query("""
        SELECT
            content_status,
            COUNT(*) as count,
            SUM(CASE WHEN product_summary_json IS NOT NULL THEN 1 ELSE 0 END) as has_summary,
            SUM(CASE WHEN detail_content_json IS NOT NULL THEN 1 ELSE 0 END) as has_detail,
            SUM(CASE WHEN sales_strategy_json IS NOT NULL THEN 1 ELSE 0 END) as has_strategy,
            SUM(CASE WHEN risk_assessment_json IS NOT NULL THEN 1 ELSE 0 END) as has_risk,
            SUM(CASE WHEN generated_naver_title IS NOT NULL THEN 1 ELSE 0 END) as has_naver_title,
            SUM(CASE WHEN generated_coupang_title IS NOT NULL THEN 1 ELSE 0 END) as has_coupang_title
        FROM approval_queue
        GROUP BY content_status
    """)

    return {"content_status_breakdown": content}


# ═══════════════════════════════════════════════════════════
# FinOps: AI 비용 통제
# ═══════════════════════════════════════════════════════════

@router.get("/finops/summary")
async def finops_summary(days: int = 30):
    """AI 비용 요약"""
    since = (datetime.now() - timedelta(days=days)).isoformat()

    # 전체 요약
    total = _query_one("""
        SELECT
            COUNT(*) as total_calls,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(total_tokens) as total_tokens,
            ROUND(SUM(cost_usd), 4) as total_cost_usd,
            ROUND(SUM(cost_krw), 0) as total_cost_krw,
            SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail_count
        FROM ai_usage_log WHERE timestamp >= ?
    """, (since,))

    # 프로바이더별
    by_provider = _query("""
        SELECT
            provider,
            model,
            COUNT(*) as calls,
            SUM(total_tokens) as tokens,
            ROUND(SUM(cost_krw), 0) as cost_krw,
            SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as success
        FROM ai_usage_log WHERE timestamp >= ?
        GROUP BY provider, model
        ORDER BY cost_krw DESC
    """, (since,))

    # 작업 유형별
    by_task = _query("""
        SELECT
            task_type,
            COUNT(*) as calls,
            SUM(total_tokens) as tokens,
            ROUND(SUM(cost_krw), 0) as cost_krw
        FROM ai_usage_log WHERE timestamp >= ?
        GROUP BY task_type
        ORDER BY cost_krw DESC
    """, (since,))

    # 일별 추이
    daily_cost = _query("""
        SELECT
            DATE(timestamp) as date,
            COUNT(*) as calls,
            ROUND(SUM(cost_krw), 0) as cost_krw,
            SUM(total_tokens) as tokens
        FROM ai_usage_log WHERE timestamp >= ?
        GROUP BY DATE(timestamp)
        ORDER BY date
    """, (since,))

    return {
        "period_days": days,
        "total": total,
        "by_provider": by_provider,
        "by_task": by_task,
        "daily_trend": daily_cost,
    }


@router.get("/finops/budget")
async def finops_budget():
    """월별 예산 현황"""
    budgets = _query("""
        SELECT month, budget_krw, spent_krw, alert_threshold,
               ROUND(spent_krw / budget_krw * 100, 1) as usage_pct
        FROM ai_budget
        ORDER BY month DESC LIMIT 6
    """)

    current_month = datetime.now().strftime('%Y-%m')
    current = next((b for b in budgets if b["month"] == current_month), None)

    return {
        "current_month": current,
        "history": budgets,
        "alert": current and current.get("usage_pct", 0) >= (current.get("alert_threshold", 0.8) * 100),
    }


class BudgetUpdateRequest(BaseModel):
    budget_krw: float
    alert_threshold: float = 0.8


@router.post("/finops/budget/{month}")
async def update_budget(month: str, request: BudgetUpdateRequest):
    """월별 예산 설정/수정"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO ai_budget (month, budget_krw, alert_threshold, spent_krw) VALUES (?, ?, ?, COALESCE((SELECT spent_krw FROM ai_budget WHERE month=?), 0))',
            (month, request.budget_krw, request.alert_threshold, month)
        )
        conn.commit()
    return {"status": "success", "month": month, "budget_krw": request.budget_krw}


@router.get("/finops/realtime")
async def finops_realtime():
    """실시간 최근 호출 로그 (최근 50건)"""
    logs = _query("""
        SELECT timestamp, provider, model, task_type, agent_name,
               input_tokens, output_tokens, cost_krw, success, error_message
        FROM ai_usage_log
        ORDER BY id DESC LIMIT 50
    """)
    return {"logs": logs}


# ═══════════════════════════════════════════════════════════
# 콘텐츠 소재 생성
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# Daily Scout 연동
# ═══════════════════════════════════════════════════════════

def _load_scout_blacklist() -> Dict[str, List[str]]:
    """A5: 블랙리스트 로드 (data/scout_blacklist.json)"""
    try:
        bl_path = Path(__file__).parent / "data" / "scout_blacklist.json"
        if bl_path.exists():
            with open(bl_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("categories", {})
    except Exception:
        pass
    return {}


def _apply_scout_filters(
    items: List[Dict[str, Any]],
    min_score: int = 0,
    category: Optional[str] = None,
    exclude_blacklist: bool = True,
) -> Dict[str, Any]:
    """A5: 후보 상품에 사전 컷 필터 적용"""
    blacklist_cats = _load_scout_blacklist() if exclude_blacklist else {}
    # 단일 플랫 리스트로 병합 (lowercase 비교)
    all_blacklist = []
    blacklist_lookup = {}
    for cat_name, kws in blacklist_cats.items():
        for kw in kws:
            kw_l = kw.lower().strip()
            all_blacklist.append(kw_l)
            blacklist_lookup[kw_l] = cat_name

    kept, cut = [], []
    cut_reasons: Dict[str, int] = {}

    for p in items:
        name = (p.get("product_name") or p.get("title") or "").lower()
        brand = (p.get("brand") or "").lower()
        haystack = f"{name} {brand}"
        score = p.get("trend_score") or 0

        # 1) 최소 스코어
        if score < min_score:
            cut.append(p)
            cut_reasons[f"점수<{min_score}"] = cut_reasons.get(f"점수<{min_score}", 0) + 1
            continue
        # 2) 카테고리
        if category and p.get("category") != category:
            cut.append(p)
            cut_reasons[f"카테고리≠{category}"] = cut_reasons.get(f"카테고리≠{category}", 0) + 1
            continue
        # 3) 블랙리스트
        if exclude_blacklist and all_blacklist:
            hit = next((kw for kw in all_blacklist if kw in haystack), None)
            if hit:
                cat_label = blacklist_lookup.get(hit, "기타")
                cut.append(p)
                cut_reasons[cat_label] = cut_reasons.get(cat_label, 0) + 1
                continue
        kept.append(p)

    return {"kept": kept, "cut_count": len(cut), "cut_reasons": cut_reasons}


@router.get("/scout/products")
async def scout_products(
    limit: int = 20,
    min_score: int = 0,
    category: Optional[str] = None,
    exclude_blacklist: bool = True,
):
    """Daily Scout 발견 상품 목록 + A5 사전 컷 필터 (서버 꺼지면 approval_queue 폴백)"""
    import httpx
    raw_items: List[Dict[str, Any]] = []
    source_label = "scout"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # 충분히 가져와서 필터 후 limit으로 자름
            resp = await client.get(f"http://localhost:8050/api/products?limit={limit * 3}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    raw_items = data.get("data", [])
    except Exception:
        logger.info("Scout 서버 미응답 → approval_queue 폴백")

    # 폴백: approval_queue의 최근 상품 반환 (raw_items 비어있을 때만)
    if not raw_items:
        try:
            rows = _query('''
                SELECT review_id, source_title, score,
                       source_data_json, generated_naver_title, created_at
                FROM approval_queue
                WHERE source_title IS NOT NULL
                ORDER BY created_at DESC LIMIT ?
            ''', (limit * 3,))
            for r in rows:
                sd = r.get("source_data_json") or "{}"
                if isinstance(sd, str):
                    try: sd = json.loads(sd)
                    except: sd = {}
                input_data = sd.get("input", {}) if isinstance(sd, dict) else {}
                raw_items.append({
                    "id": r.get("review_id"),
                    "product_name": r.get("source_title") or "",
                    "brand": sd.get("ext_brand") if isinstance(sd, dict) else "",
                    "price": "",
                    "category": input_data.get("category", "wellness"),
                    "trend_score": r.get("score") or 0,
                    "korea_demand": "높음" if (r.get("score") or 0) >= 70 else "보통",
                    "risk_status": "통과",
                    "url": input_data.get("source_url", ""),
                    "region": input_data.get("source_country", "US").lower(),
                    "workflow_status": "analyzed",
                    "source": "내부 분석 완료",
                })
            source_label = "fallback"
        except Exception as e:
            return {"error": str(e), "data": []}

    # A5: 필터 적용
    filtered = _apply_scout_filters(
        raw_items,
        min_score=min_score,
        category=category,
        exclude_blacklist=exclude_blacklist,
    )
    kept = filtered["kept"][:limit]

    return {
        "success": True,
        "data": kept,
        "count": len(kept),
        "raw_count": len(raw_items),
        "cut_count": filtered["cut_count"],
        "cut_reasons": filtered["cut_reasons"],
        "filters_applied": {
            "min_score": min_score,
            "category": category,
            "exclude_blacklist": exclude_blacklist,
        },
        "source": source_label,
    }


@router.get("/scout/blacklist")
async def get_scout_blacklist():
    """A5: 블랙리스트 카테고리/키워드 조회"""
    cats = _load_scout_blacklist()
    return {
        "categories": cats,
        "total_keywords": sum(len(v) for v in cats.values()),
    }


@router.get("/scout/stats")
async def scout_stats():
    """Daily Scout 크롤링 현황 (서버 꺼지면 approval_queue 기반)"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:8050/api/stats")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass

    # 폴백: approval_queue 통계
    try:
        row = _query_one("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN review_status='approved_for_export' THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN review_status='hold' THEN 1 ELSE 0 END) as pending,
                   SUM(CASE WHEN review_status='rejected' THEN 1 ELSE 0 END) as rejected,
                   MAX(score) as max_score
            FROM approval_queue
        """)
        return {
            "success": True,
            "data": {
                **row,
                "region_stats": {"us": row.get("total", 0)},
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "fallback",
            }
        }
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════
# CS 에이전트 API
# ═══════════════════════════════════════════════════════════

class CSRequest(BaseModel):
    customer_message: str
    order_id: Optional[str] = None
    order_status: Optional[str] = None


@router.post("/cs/generate")
async def cs_generate(request: CSRequest):
    """CS 답변 생성"""
    try:
        from cs_agent import CSAgent
        agent = CSAgent()
        result = agent.execute({
            "customer_message": request.customer_message,
            "order_id": request.order_id or "",
            "order_status": request.order_status or "",
        })
        if result.is_success():
            return {"status": "success", "data": result.output}
        return {"status": "failed", "error": result.error}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 콘텐츠 소재 생성
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# 신규 에이전트 6종 API
# ═══════════════════════════════════════════════════════════

class AgentRequest(BaseModel):
    product_name: str
    category: str = "general"
    price: float = 0


@router.post("/agents/keyword-research")
async def keyword_research(request: AgentRequest):
    """키워드 리서치"""
    from new_agents import KeywordResearchAgent
    return KeywordResearchAgent().analyze(request.product_name, request.category)


@router.post("/agents/price-monitor")
async def price_monitor(request: AgentRequest):
    """가격 모니터링"""
    from new_agents import PriceMonitorAgent
    return PriceMonitorAgent().analyze(request.product_name, request.price)


@router.post("/agents/review-analysis")
async def review_analysis(request: AgentRequest):
    """리뷰 분석"""
    from new_agents import ReviewAnalysisAgent
    return ReviewAnalysisAgent().analyze(request.product_name, request.category)


@router.get("/agents/inventory")
async def inventory_check():
    """재고/발주 현황"""
    from new_agents import InventoryAgent
    return InventoryAgent().check_all()


@router.get("/agents/content-schedule")
async def content_schedule(days: int = 14):
    """콘텐츠 스케줄러"""
    from new_agents import ContentSchedulerAgent
    return ContentSchedulerAgent().generate_schedule(days)


@router.get("/agents/forex-tariff")
async def forex_tariff():
    """환율/관세 모니터링"""
    from new_agents import ForexTariffAgent
    return ForexTariffAgent().check_impact()


# ═══════════════════════════════════════════════════════════
# 콘텐츠 소재 생성
# ═══════════════════════════════════════════════════════════

class MaterialRequest(BaseModel):
    prompt: str
    type: str = "sns"


# ═══════════════════════════════════════════════════════════
# CSO Agent — 최고전략책임자
# ═══════════════════════════════════════════════════════════

@router.get("/cso/categories")
async def cso_categories(force_refresh: bool = False):
    """CSO 카테고리 포트폴리오 제언"""
    from cso_agent import CSOAgent
    return CSOAgent().recommend_categories(force_refresh=force_refresh)


@router.get("/cso/roadmap-90day")
async def cso_roadmap(force_refresh: bool = False):
    """90일 실행 로드맵"""
    from cso_agent import CSOAgent
    return CSOAgent().generate_90day_roadmap(force_refresh=force_refresh)


@router.get("/cso/investment-priority")
async def cso_investment(monthly_budget_krw: float = 10000000):
    """월 예산 기반 투자 우선순위"""
    from cso_agent import CSOAgent
    return CSOAgent().prioritize_investments(monthly_budget_krw=monthly_budget_krw)


@router.get("/cso/blue-ocean")
async def cso_blue_ocean():
    """블루오션 기회 발굴"""
    from cso_agent import CSOAgent
    return CSOAgent().find_blue_ocean()


@router.get("/cso/brief")
async def cso_brief():
    """CSO 전략 브리프 (홈 대시보드용)"""
    from cso_agent import CSOAgent
    return CSOAgent().strategic_brief()


@router.get("/cso/10year-vision")
async def cso_10year_vision(force_refresh: bool = False):
    """10년 비전 — 기업가치 2조 로드맵"""
    from cso_agent import CSOAgent
    return CSOAgent().generate_10year_vision(force_refresh=force_refresh)


# ═══════════════════════════════════════════════════════════
# SNS 콘텐츠 엔진 (5000억 매출 핵심)
# ═══════════════════════════════════════════════════════════

class SNSContentRequest(BaseModel):
    product_name: str
    category: str = "supplement"
    key_benefits: list = []
    target_audience: str = "30~50대 건강 관심 고객"
    platform: str = "instagram_reels"
    tone: str = "expert"
    variant: str = "A"
    review_id: Optional[str] = None


@router.post("/sns/generate")
async def sns_generate(request: SNSContentRequest):
    """단일 플랫폼 콘텐츠 생성"""
    from sns_content_engine import SNSContentEngine
    return SNSContentEngine().generate_platform_content(
        product_name=request.product_name,
        category=request.category,
        key_benefits=request.key_benefits,
        target_audience=request.target_audience,
        platform=request.platform,
        tone=request.tone,
        variant=request.variant,
    )


@router.post("/sns/full-campaign")
async def sns_full_campaign(request: SNSContentRequest):
    """5개 플랫폼 × 2개 톤 = 10개 콘텐츠 동시 생성"""
    from sns_content_engine import SNSContentEngine
    return SNSContentEngine().generate_full_campaign(
        product_name=request.product_name,
        category=request.category,
        key_benefits=request.key_benefits,
        target_audience=request.target_audience,
        review_id=request.review_id,
    )


@router.get("/sns/calendar")
async def sns_calendar(days: int = 30, posts_per_day: int = 3):
    """N일간 포스팅 캘린더 자동 생성"""
    from sns_content_engine import generate_posting_calendar
    return generate_posting_calendar(days=days, posts_per_day=posts_per_day)


@router.get("/sns/calendar/view")
async def sns_calendar_view():
    """저장된 캘린더 조회"""
    rows = _query('''
        SELECT schedule_date, time_slot, platform, product_name, campaign_type, status
        FROM content_calendar
        WHERE schedule_date >= date('now')
        ORDER BY schedule_date, time_slot LIMIT 100
    ''')
    return {"calendar": rows, "count": len(rows)}


@router.post("/sns/influencers/suggest")
async def sns_influencers(request: SNSContentRequest):
    """인플루언서 매칭 제안"""
    from sns_content_engine import suggest_influencers_for_product
    budget = 10_000_000  # 기본 1000만원
    return suggest_influencers_for_product(request.product_name, request.category, budget)


@router.post("/sns/hooks")
async def sns_hooks(request: SNSContentRequest):
    """바이럴 후킹 카피 10개 생성"""
    from sns_content_engine import generate_viral_hooks
    return generate_viral_hooks(request.product_name, request.category, count=10)


@router.get("/sns/contents/list")
async def sns_contents_list(limit: int = 50):
    """저장된 SNS 콘텐츠 목록"""
    rows = _query('''
        SELECT id, product_name, platform, tone, hook, status, scheduled_at, created_at
        FROM sns_contents
        ORDER BY id DESC LIMIT ?
    ''', (limit,))
    return {"contents": rows, "count": len(rows)}


# ═══════════════════════════════════════════════════════════
# 웰니스 필터
# ═══════════════════════════════════════════════════════════

class WellnessCheckRequest(BaseModel):
    product_name: str
    description: Optional[str] = ""
    category: Optional[str] = ""


@router.post("/wellness/check")
async def wellness_check(request: WellnessCheckRequest):
    """단일 상품 웰니스 합법성 검증"""
    from wellness_filter import WellnessFilter
    return WellnessFilter().classify(request.product_name, request.description or "", request.category or "")


@router.post("/wellness/filter")
async def wellness_filter(products: list):
    """상품 목록 일괄 필터링"""
    from wellness_filter import WellnessFilter
    return WellnessFilter().filter_products(products)


# ═══════════════════════════════════════════════════════════
# 트렌드 인텔리전스 (매크로 시장 분석)
# ═══════════════════════════════════════════════════════════

@router.get("/trends/macro")
async def trends_macro(force_refresh: bool = False):
    """매크로 시장 트렌드 (Brainergy, GLP-1, Longevity 등)"""
    from trend_intelligence import TrendIntelligenceAgent
    return TrendIntelligenceAgent().analyze_macro_trends(force_refresh=force_refresh)


@router.get("/trends/high-margin")
async def trends_high_margin(force_refresh: bool = False):
    """고마진 상품 발굴 (순이익 70%+)"""
    from trend_intelligence import TrendIntelligenceAgent
    return TrendIntelligenceAgent().find_high_margin_opportunities(force_refresh=force_refresh)


@router.get("/trends/brief")
async def trends_brief():
    """오늘의 트렌드 브리프 (홈 대시보드용)"""
    from trend_intelligence import TrendIntelligenceAgent
    return TrendIntelligenceAgent().daily_brief()


# ═══════════════════════════════════════════════════════════
# 브라우저 확장 프로그램 연동
# ═══════════════════════════════════════════════════════════

class ExtensionSubmit(BaseModel):
    source_url: str
    source_title: str = ""
    source_brand: Optional[str] = ""
    source_category: Optional[str] = "general"
    source_price: float = 0
    source_country: str = "US"
    weight_kg: float = 0.5
    images: list = []
    description: Optional[str] = ""
    workflow_name: str = "quick_sourcing_check"
    platform: Optional[str] = ""


@router.post("/extension/submit")
async def extension_submit(request: ExtensionSubmit):
    """브라우저 확장 프로그램에서 상품 데이터 수신 → 워크플로우 실행"""
    try:
        import httpx

        # source_price_cny 계산 (CN일 경우)
        user_input = {
            "source_url": request.source_url,
            "source_title": request.source_title,
            "source_brand": request.source_brand,
            "source_price": request.source_price,
            "source_price_cny": request.source_price if request.source_country == "CN" else None,
            "source_country": request.source_country,
            "weight_kg": request.weight_kg,
            "market": "korea",
            "category": request.source_category,
            "images": request.images,  # 확장 프로그램에서 가져온 이미지
            "description": request.description,
        }

        # 내부 워크플로우 API 호출
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "http://localhost:8051/api/workflows/run",
                json={
                    "workflow_name": request.workflow_name,
                    "user_input": user_input,
                    "save_to_queue": True,
                }
            )
            result = resp.json()

        review_id = result.get("result", {}).get("review_id")
        if not review_id:
            # 폴백: 최신 리뷰에서 찾기
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    r = conn.execute("SELECT review_id FROM approval_queue ORDER BY created_at DESC LIMIT 1").fetchone()
                    if r:
                        review_id = r[0]
            except Exception:
                pass

        # 확장 프로그램의 이미지 URL을 별도 저장 (상세페이지 리디자인에서 사용)
        if review_id and request.images:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    # source_data_json 업데이트
                    row = conn.execute("SELECT source_data_json FROM approval_queue WHERE review_id=?", (review_id,)).fetchone()
                    if row and row[0]:
                        sd = json.loads(row[0])
                        sd["ext_images"] = request.images
                        sd["ext_brand"] = request.source_brand
                        sd["ext_description"] = request.description
                        sd["ext_platform"] = request.platform
                        conn.execute(
                            "UPDATE approval_queue SET source_data_json=? WHERE review_id=?",
                            (json.dumps(sd, ensure_ascii=False), review_id)
                        )
                        conn.commit()
            except Exception as e:
                logger.warning(f"확장 이미지 저장 실패: {e}")

        return {
            "status": "success",
            "review_id": review_id,
            "workflow_status": result.get("status"),
            "score": result.get("result", {}).get("scoring", {}).get("score"),
        }
    except Exception as e:
        logger.error(f"extension/submit 실패: {e}")
        return {"status": "failed", "error": str(e)}


@router.options("/extension/submit")
async def extension_submit_options():
    """CORS preflight 대응"""
    from fastapi.responses import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


@router.post("/generate-material")
async def generate_material(request: MaterialRequest):
    """통과 상품의 마케팅 소재 생성"""
    try:
        from llm_router import call_llm
        content = call_llm(
            task_type="copywriting",
            prompt=request.prompt,
            max_tokens=1500
        )
        return {"content": content, "type": request.type}
    except Exception as e:
        logger.error(f"소재 생성 실패: {e}")
        return {"content": f"생성 실패: {str(e)}", "type": request.type, "error": True}
