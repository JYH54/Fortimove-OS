"""
Scale API — 5000억 매출 목표 달성을 위한 대량 처리 인프라

핵심 3대 기능:
1. 배치 상품 분석 (일 100+개 동시 처리)
2. 판매 데이터 수집 (네이버/쿠팡 판매 실적)
3. 광고 성과 추적 (ROAS 계산)
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scale", tags=["Scale-5000억"])

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


def _init_scale_tables():
    """판매/광고 추적 테이블 초기화"""
    with sqlite3.connect(DB_PATH) as conn:
        # 판매 실적
        conn.execute('''CREATE TABLE IF NOT EXISTS sales_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT,
            product_name TEXT,
            platform TEXT,
            order_date TEXT,
            quantity INTEGER DEFAULT 0,
            revenue_krw REAL DEFAULT 0,
            cost_krw REAL DEFAULT 0,
            profit_krw REAL DEFAULT 0,
            platform_fee REAL DEFAULT 0,
            created_at TEXT
        )''')

        # 광고 성과
        conn.execute('''CREATE TABLE IF NOT EXISTS ad_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT,
            campaign_name TEXT,
            platform TEXT,
            date TEXT,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            ad_cost_krw REAL DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            revenue_krw REAL DEFAULT 0,
            roas REAL DEFAULT 0,
            ctr REAL DEFAULT 0,
            created_at TEXT
        )''')

        # 배치 작업 큐
        conn.execute('''CREATE TABLE IF NOT EXISTS batch_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT UNIQUE,
            job_type TEXT,
            total_items INTEGER DEFAULT 0,
            completed_items INTEGER DEFAULT 0,
            failed_items INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            input_json TEXT,
            result_json TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT
        )''')
        conn.commit()

_init_scale_tables()


def _query(sql: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _query_one(sql: str, params: tuple = ()):
    rows = _query(sql, params)
    return rows[0] if rows else {}


# ═══════════════════════════════════════════════════════════
# 1. 배치 상품 분석 (대량 처리)
# ═══════════════════════════════════════════════════════════

class BatchAnalyzeRequest(BaseModel):
    urls: List[str]
    category: str = "supplement"
    source_country: str = "US"
    workflow_name: str = "quick_sourcing_check"


async def _run_batch_workflow(batch_id: str, request: BatchAnalyzeRequest):
    """배치 워크플로우 실행 (BackgroundTask)"""
    import httpx
    import uuid

    total = len(request.urls)
    completed = 0
    failed = 0
    results = []

    for idx, url in enumerate(request.urls):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    "http://localhost:8051/api/workflows/run",
                    json={
                        "workflow_name": request.workflow_name,
                        "user_input": {
                            "source_url": url,
                            "source_title": "",
                            "source_country": request.source_country,
                            "weight_kg": 0.3,
                            "market": "korea",
                            "category": request.category,
                        },
                        "save_to_queue": True,
                    }
                )
                data = resp.json()
                review_id = data.get("result", {}).get("review_id")
                results.append({
                    "url": url,
                    "review_id": review_id,
                    "score": data.get("result", {}).get("scoring", {}).get("score"),
                    "status": "success",
                })
                completed += 1
        except Exception as e:
            results.append({"url": url, "status": "failed", "error": str(e)[:100]})
            failed += 1

        # 배치 진행상황 업데이트
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE batch_jobs SET completed_items=?, failed_items=? WHERE batch_id=?",
                (completed, failed, batch_id)
            )
            conn.commit()

    # 완료
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE batch_jobs SET status='completed', result_json=?, completed_at=? WHERE batch_id=?",
            (json.dumps(results, ensure_ascii=False), datetime.now().isoformat(), batch_id)
        )
        conn.commit()


@router.post("/batch/analyze")
async def batch_analyze(request: BatchAnalyzeRequest, background_tasks: BackgroundTasks):
    """N개 상품 URL을 배치로 분석 (5000억 목표: 일 100+개 처리)"""
    import uuid
    batch_id = f"batch-{uuid.uuid4().hex[:12]}"

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO batch_jobs (batch_id, job_type, total_items, status, input_json, started_at, created_at) VALUES (?, ?, ?, 'processing', ?, ?, ?)",
            (batch_id, "sourcing_analyze", len(request.urls),
             json.dumps(request.dict(), ensure_ascii=False),
             datetime.now().isoformat(), datetime.now().isoformat())
        )
        conn.commit()

    background_tasks.add_task(_run_batch_workflow, batch_id, request)

    return {
        "batch_id": batch_id,
        "total_items": len(request.urls),
        "status": "processing",
        "message": f"{len(request.urls)}개 상품 배치 분석 시작",
    }


@router.get("/batch/{batch_id}")
async def batch_status(batch_id: str):
    """배치 작업 상태 조회"""
    row = _query_one("SELECT * FROM batch_jobs WHERE batch_id=?", (batch_id,))
    if not row:
        raise HTTPException(404, "배치 작업을 찾을 수 없습니다")

    if row.get("result_json"):
        try:
            row["results"] = json.loads(row["result_json"])
        except Exception:
            row["results"] = []
    return row


@router.get("/batch/list/recent")
async def batch_list(limit: int = 20):
    """최근 배치 작업 목록"""
    rows = _query("SELECT batch_id, job_type, total_items, completed_items, failed_items, status, started_at FROM batch_jobs ORDER BY id DESC LIMIT ?", (limit,))
    return {"batches": rows, "count": len(rows)}


# ═══════════════════════════════════════════════════════════
# 2. 판매 데이터 수집 + 조회
# ═══════════════════════════════════════════════════════════

class SalesDataRequest(BaseModel):
    review_id: Optional[str] = None
    product_name: str
    platform: str  # naver / coupang / both
    order_date: str  # YYYY-MM-DD
    quantity: int
    revenue_krw: float
    cost_krw: float = 0
    platform_fee_rate: float = 0.15


@router.post("/sales/record")
async def sales_record(request: SalesDataRequest):
    """판매 실적 기록 (수동 입력 또는 API 연동)"""
    platform_fee = request.revenue_krw * request.platform_fee_rate
    profit = request.revenue_krw - request.cost_krw - platform_fee

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO sales_data (review_id, product_name, platform, order_date, quantity, revenue_krw, cost_krw, profit_krw, platform_fee, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.review_id, request.product_name, request.platform, request.order_date,
            request.quantity, request.revenue_krw, request.cost_krw, profit, platform_fee,
            datetime.now().isoformat()
        ))
        conn.commit()

    return {"status": "success", "profit_krw": profit}


@router.get("/sales/summary")
async def sales_summary(days: int = 30):
    """판매 실적 요약"""
    since = (datetime.now() - timedelta(days=days)).isoformat()

    total = _query_one("""
        SELECT
            COUNT(*) as order_count,
            SUM(quantity) as total_qty,
            ROUND(SUM(revenue_krw), 0) as total_revenue,
            ROUND(SUM(cost_krw), 0) as total_cost,
            ROUND(SUM(profit_krw), 0) as total_profit,
            ROUND(SUM(platform_fee), 0) as total_fee
        FROM sales_data WHERE order_date >= ?
    """, (since[:10],))

    # 플랫폼별
    by_platform = _query("""
        SELECT platform, COUNT(*) as orders,
               ROUND(SUM(revenue_krw), 0) as revenue,
               ROUND(SUM(profit_krw), 0) as profit
        FROM sales_data WHERE order_date >= ?
        GROUP BY platform
    """, (since[:10],))

    # TOP 상품
    top_products = _query("""
        SELECT product_name, SUM(quantity) as qty,
               ROUND(SUM(revenue_krw), 0) as revenue,
               ROUND(SUM(profit_krw), 0) as profit
        FROM sales_data WHERE order_date >= ?
        GROUP BY product_name
        ORDER BY revenue DESC LIMIT 10
    """, (since[:10],))

    # 일별 추이
    daily = _query("""
        SELECT order_date,
               SUM(quantity) as qty,
               ROUND(SUM(revenue_krw), 0) as revenue
        FROM sales_data WHERE order_date >= ?
        GROUP BY order_date ORDER BY order_date
    """, (since[:10],))

    # 5000억 목표 진행률
    annual_target = 500_000_000_000  # 5000억
    monthly_target = annual_target / 12
    total_revenue = total.get("total_revenue") or 0
    current_monthly = total_revenue * (30 / max(days, 1))
    progress_pct = round(current_monthly / monthly_target * 100, 4) if monthly_target > 0 else 0

    # None 값 정리
    for k in ("total_revenue", "total_cost", "total_profit", "total_fee", "total_qty", "order_count"):
        if total.get(k) is None:
            total[k] = 0

    return {
        "period_days": days,
        "summary": total,
        "by_platform": by_platform,
        "top_products": top_products,
        "daily_trend": daily,
        "target": {
            "annual_target_krw": annual_target,
            "monthly_target_krw": monthly_target,
            "current_monthly_estimated_krw": round(current_monthly, 0),
            "progress_pct": progress_pct,
        }
    }


# ═══════════════════════════════════════════════════════════
# 3. 광고 성과 추적 (ROAS)
# ═══════════════════════════════════════════════════════════

class AdPerformanceRequest(BaseModel):
    review_id: Optional[str] = None
    campaign_name: str
    platform: str
    date: str
    impressions: int
    clicks: int
    ad_cost_krw: float
    conversions: int
    revenue_krw: float


@router.post("/ads/record")
async def ads_record(request: AdPerformanceRequest):
    """광고 성과 기록"""
    roas = round(request.revenue_krw / request.ad_cost_krw, 2) if request.ad_cost_krw > 0 else 0
    ctr = round(request.clicks / request.impressions * 100, 2) if request.impressions > 0 else 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO ad_performance (review_id, campaign_name, platform, date, impressions, clicks, ad_cost_krw, conversions, revenue_krw, roas, ctr, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.review_id, request.campaign_name, request.platform, request.date,
            request.impressions, request.clicks, request.ad_cost_krw, request.conversions,
            request.revenue_krw, roas, ctr, datetime.now().isoformat()
        ))
        conn.commit()

    return {"status": "success", "roas": roas, "ctr": ctr}


@router.get("/ads/summary")
async def ads_summary(days: int = 30):
    """광고 성과 요약"""
    since = (datetime.now() - timedelta(days=days)).isoformat()[:10]

    total = _query_one("""
        SELECT
            COUNT(*) as campaigns,
            SUM(impressions) as total_impressions,
            SUM(clicks) as total_clicks,
            ROUND(SUM(ad_cost_krw), 0) as total_cost,
            SUM(conversions) as total_conversions,
            ROUND(SUM(revenue_krw), 0) as total_revenue,
            ROUND(AVG(roas), 2) as avg_roas,
            ROUND(AVG(ctr), 2) as avg_ctr
        FROM ad_performance WHERE date >= ?
    """, (since,))

    # 저성과 캠페인 (ROAS < 2)
    low_roas = _query("""
        SELECT campaign_name, platform, ad_cost_krw, revenue_krw, roas
        FROM ad_performance WHERE date >= ? AND roas < 2 AND ad_cost_krw > 10000
        ORDER BY roas ASC LIMIT 10
    """, (since,))

    # 고성과 캠페인 (ROAS > 5)
    high_roas = _query("""
        SELECT campaign_name, platform, ad_cost_krw, revenue_krw, roas
        FROM ad_performance WHERE date >= ? AND roas > 5
        ORDER BY roas DESC LIMIT 10
    """, (since,))

    return {
        "period_days": days,
        "summary": total,
        "low_performing_alerts": low_roas,
        "top_performing": high_roas,
    }


# ═══════════════════════════════════════════════════════════
# 4. 종합 대시보드 (5000억 목표 진행률)
# ═══════════════════════════════════════════════════════════

@router.get("/dashboard/5000eok")
async def dashboard_5000eok():
    """5000억 매출 목표 대시보드"""
    # 판매 요약 (30일)
    sales = await sales_summary(days=30)

    # 광고 성과 (30일)
    ads = await ads_summary(days=30)

    # 처리 현황
    processed = _query_one("""
        SELECT
            COUNT(*) as total_products,
            SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) as high_score,
            SUM(CASE WHEN review_status='approved_for_export' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN generated_naver_title IS NOT NULL THEN 1 ELSE 0 END) as content_ready
        FROM approval_queue
    """)

    # 배치 작업 현황
    batch_stats = _query_one("""
        SELECT
            COUNT(*) as total_batches,
            SUM(completed_items) as total_processed,
            SUM(failed_items) as total_failed
        FROM batch_jobs
    """)

    # KPI 계산
    target_annual = 500_000_000_000
    current_monthly_est = sales.get("target", {}).get("current_monthly_estimated_krw", 0)
    current_annual_est = current_monthly_est * 12

    # 필요한 상품 수 (월 416억 / 평균 상품당 매출 100만원 가정)
    avg_revenue_per_product_monthly = 1_000_000
    products_needed = int(416_000_000_000 / 12 / avg_revenue_per_product_monthly) if current_monthly_est < 416_000_000_000 / 12 else 0

    return {
        "target": {
            "annual_krw": target_annual,
            "monthly_krw": target_annual / 12,
            "daily_krw": target_annual / 365,
        },
        "current": {
            "monthly_estimated_krw": current_monthly_est,
            "annual_estimated_krw": current_annual_est,
            "progress_pct": round(current_annual_est / target_annual * 100, 4),
        },
        "sales_30d": sales.get("summary", {}),
        "ads_30d": ads.get("summary", {}),
        "products": processed,
        "batch_processing": batch_stats,
        "recommendations": {
            "products_needed_for_target": products_needed,
            "critical_actions": [
                f"월 {products_needed}개 상품 추가 등록 필요" if products_needed > 0 else "목표 달성 궤도 진입",
                "ROAS 2 미만 캠페인 중단" if len(ads.get("low_performing_alerts", [])) > 0 else "광고 효율 양호",
                f"배치 처리 속도 증대 필요 (현재 {batch_stats.get('total_processed', 0)}개)",
            ]
        }
    }
