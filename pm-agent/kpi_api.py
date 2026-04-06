"""
KPI API — 대표의 월별 목표 설정 + 실제 달성률 추적
"""
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kpi", tags=["KPI"])

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


# ═══════════════════════════════════════════════════════════
# DB 초기화
# ═══════════════════════════════════════════════════════════

def _init_kpi_tables():
    with sqlite3.connect(DB_PATH) as conn:
        # 월별 목표 (대표가 직접 입력)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kpi_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                kpi_key TEXT NOT NULL,
                target_value REAL NOT NULL,
                unit TEXT DEFAULT '',
                note TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                UNIQUE(month, kpi_key)
            )
        """)
        # 실적 기록 (수동 입력 또는 자동 집계)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kpi_actuals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                kpi_key TEXT NOT NULL,
                actual_value REAL NOT NULL,
                source TEXT DEFAULT 'manual',
                note TEXT DEFAULT '',
                recorded_at TEXT DEFAULT '',
                UNIQUE(month, kpi_key)
            )
        """)
        conn.commit()

_init_kpi_tables()


# ═══════════════════════════════════════════════════════════
# KPI 정의 (표준 지표 목록)
# ═══════════════════════════════════════════════════════════

KPI_DEFINITIONS = {
    "revenue_krw":          {"label": "월 매출", "unit": "원", "auto": False, "icon": "💰", "category": "재무"},
    "orders_count":         {"label": "주문 건수", "unit": "건", "auto": False, "icon": "🛒", "category": "재무"},
    "avg_order_value":      {"label": "평균 객단가", "unit": "원", "auto": False, "icon": "📊", "category": "재무"},
    "gross_margin_rate":    {"label": "평균 마진율", "unit": "%", "auto": False, "icon": "📈", "category": "재무"},
    "ad_spend_krw":         {"label": "광고비 지출", "unit": "원", "auto": False, "icon": "📣", "category": "재무"},
    "products_registered":  {"label": "신규 등록 상품", "unit": "개", "auto": True, "icon": "📦", "category": "운영"},
    "products_approved":    {"label": "승인된 상품", "unit": "개", "auto": True, "icon": "✅", "category": "운영"},
    "content_generated":    {"label": "콘텐츠 생성", "unit": "개", "auto": True, "icon": "✍️", "category": "운영"},
    "redesigns_completed":  {"label": "상세페이지 완성", "unit": "개", "auto": True, "icon": "🎨", "category": "운영"},
    "ai_cost_krw":          {"label": "AI 비용", "unit": "원", "auto": True, "icon": "🤖", "category": "운영"},
    "cs_resolved":          {"label": "CS 처리 건수", "unit": "건", "auto": False, "icon": "💬", "category": "CS"},
    "return_rate":          {"label": "반품률", "unit": "%", "auto": False, "icon": "↩️", "category": "CS"},
    "review_rating":        {"label": "평균 별점", "unit": "점", "auto": False, "icon": "⭐", "category": "CS"},
    "new_winners":          {"label": "위닝 상품 발굴", "unit": "개", "auto": False, "icon": "🏆", "category": "전략"},
    "repeat_customer_rate": {"label": "재구매율", "unit": "%", "auto": False, "icon": "🔁", "category": "전략"},
}


# ═══════════════════════════════════════════════════════════
# 자동 집계 (auto=True 지표)
# ═══════════════════════════════════════════════════════════

def _auto_collect(month: str) -> Dict[str, float]:
    """시스템 DB에서 자동으로 집계 가능한 KPI 수치"""
    # month: "2026-04"
    start = f"{month}-01"
    # 다음 달 계산
    y, m = map(int, month.split("-"))
    if m == 12:
        end = f"{y+1}-01-01"
    else:
        end = f"{y}-{m+1:02d}-01"

    result = {}
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # 신규 등록 상품 (approval_queue 생성)
        c.execute("SELECT COUNT(*) FROM approval_queue WHERE created_at >= ? AND created_at < ?", (start, end))
        result["products_registered"] = c.fetchone()[0]

        # 승인된 상품
        c.execute("""SELECT COUNT(*) FROM approval_queue
                     WHERE review_status IN ('approved_for_export', 'approved_for_upload')
                     AND updated_at >= ? AND updated_at < ?""", (start, end))
        result["products_approved"] = c.fetchone()[0]

        # 콘텐츠 생성
        c.execute("""SELECT COUNT(*) FROM approval_queue
                     WHERE generated_naver_title IS NOT NULL
                     AND updated_at >= ? AND updated_at < ?""", (start, end))
        result["content_generated"] = c.fetchone()[0]

        # 리디자인 완료
        try:
            c.execute("""SELECT COUNT(*) FROM redesign_queue
                         WHERE status='completed'
                         AND updated_at >= ? AND updated_at < ?""", (start, end))
            result["redesigns_completed"] = c.fetchone()[0]
        except Exception:
            result["redesigns_completed"] = 0

        # AI 비용 (ai_usage_log)
        try:
            c.execute("""SELECT ROUND(SUM(cost_krw), 0) FROM ai_usage_log
                         WHERE timestamp >= ? AND timestamp < ?""", (start, end))
            v = c.fetchone()[0]
            result["ai_cost_krw"] = v or 0
        except Exception:
            result["ai_cost_krw"] = 0

    return result


# ═══════════════════════════════════════════════════════════
# API 엔드포인트
# ═══════════════════════════════════════════════════════════

class TargetRequest(BaseModel):
    month: str  # "2026-04"
    kpi_key: str
    target_value: float
    note: Optional[str] = ""


class ActualRequest(BaseModel):
    month: str
    kpi_key: str
    actual_value: float
    note: Optional[str] = ""


@router.get("/definitions")
async def kpi_definitions():
    """KPI 정의 목록"""
    return {"definitions": KPI_DEFINITIONS}


@router.get("/dashboard")
async def kpi_dashboard(month: Optional[str] = None):
    """KPI 대시보드 — 목표 + 실적 + 달성률 통합 조회"""
    if not month:
        month = datetime.now().strftime("%Y-%m")

    # 자동 집계
    auto = _auto_collect(month)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        targets = {r["kpi_key"]: dict(r) for r in conn.execute(
            "SELECT * FROM kpi_targets WHERE month = ?", (month,))}
        actuals = {r["kpi_key"]: dict(r) for r in conn.execute(
            "SELECT * FROM kpi_actuals WHERE month = ?", (month,))}

    # 응답 구조화
    items = []
    for key, defn in KPI_DEFINITIONS.items():
        target = targets.get(key, {})
        actual = actuals.get(key, {})

        # 자동 집계 KPI는 auto 값이 우선
        if defn["auto"]:
            actual_value = auto.get(key, 0)
            actual_source = "auto"
        else:
            actual_value = actual.get("actual_value", 0)
            actual_source = actual.get("source", "none") if actual else "none"

        target_value = target.get("target_value", 0)
        pct = round(actual_value / target_value * 100, 1) if target_value > 0 else 0

        items.append({
            "key": key,
            "label": defn["label"],
            "unit": defn["unit"],
            "icon": defn["icon"],
            "category": defn["category"],
            "auto": defn["auto"],
            "target_value": target_value,
            "actual_value": actual_value,
            "achievement_pct": pct,
            "source": actual_source,
            "target_note": target.get("note", ""),
            "actual_note": actual.get("note", ""),
            "status": _status(pct, target_value),
        })

    # 카테고리별 그룹화
    by_category: Dict[str, List] = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item)

    return {
        "month": month,
        "items": items,
        "by_category": by_category,
        "summary": _summary(items),
    }


def _status(pct: float, target: float) -> str:
    if target <= 0:
        return "no_target"
    if pct >= 100:
        return "achieved"
    if pct >= 80:
        return "on_track"
    if pct >= 50:
        return "behind"
    return "risk"


def _summary(items: List[Dict]) -> Dict:
    """요약 통계"""
    with_target = [i for i in items if i["target_value"] > 0]
    if not with_target:
        return {"total": 0, "achieved": 0, "on_track": 0, "at_risk": 0, "avg_pct": 0}

    achieved = sum(1 for i in with_target if i["status"] == "achieved")
    on_track = sum(1 for i in with_target if i["status"] == "on_track")
    at_risk = sum(1 for i in with_target if i["status"] in ("behind", "risk"))
    avg_pct = round(sum(i["achievement_pct"] for i in with_target) / len(with_target), 1)

    return {
        "total": len(with_target),
        "achieved": achieved,
        "on_track": on_track,
        "at_risk": at_risk,
        "avg_pct": avg_pct,
    }


@router.post("/target")
async def set_target(request: TargetRequest):
    """월별 목표 설정/수정"""
    if request.kpi_key not in KPI_DEFINITIONS:
        raise HTTPException(400, f"Unknown KPI: {request.kpi_key}")

    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO kpi_targets (month, kpi_key, target_value, unit, note, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(month, kpi_key) DO UPDATE SET
                target_value=excluded.target_value,
                note=excluded.note,
                updated_at=excluded.updated_at
        """, (request.month, request.kpi_key, request.target_value,
              KPI_DEFINITIONS[request.kpi_key]["unit"], request.note or "", now))
        conn.commit()
    return {"status": "success", "month": request.month, "kpi_key": request.kpi_key}


@router.post("/actual")
async def record_actual(request: ActualRequest):
    """실적 수동 입력/수정"""
    if request.kpi_key not in KPI_DEFINITIONS:
        raise HTTPException(400, f"Unknown KPI: {request.kpi_key}")

    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO kpi_actuals (month, kpi_key, actual_value, source, note, recorded_at)
            VALUES (?, ?, ?, 'manual', ?, ?)
            ON CONFLICT(month, kpi_key) DO UPDATE SET
                actual_value=excluded.actual_value,
                note=excluded.note,
                recorded_at=excluded.recorded_at
        """, (request.month, request.kpi_key, request.actual_value, request.note or "", now))
        conn.commit()
    return {"status": "success"}


@router.delete("/target/{month}/{kpi_key}")
async def delete_target(month: str, kpi_key: str):
    """목표 삭제"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM kpi_targets WHERE month=? AND kpi_key=?", (month, kpi_key))
        conn.commit()
    return {"status": "success"}


@router.get("/history/{kpi_key}")
async def kpi_history(kpi_key: str, months: int = 6):
    """특정 KPI의 월별 추이 (그래프용)"""
    if kpi_key not in KPI_DEFINITIONS:
        raise HTTPException(404, f"Unknown KPI: {kpi_key}")

    # 최근 N개월 목록
    now = datetime.now()
    month_list = []
    for i in range(months - 1, -1, -1):
        y = now.year
        m = now.month - i
        while m <= 0:
            y -= 1
            m += 12
        month_list.append(f"{y}-{m:02d}")

    history = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        for month in month_list:
            tgt_row = conn.execute(
                "SELECT target_value FROM kpi_targets WHERE month=? AND kpi_key=?",
                (month, kpi_key)
            ).fetchone()

            defn = KPI_DEFINITIONS[kpi_key]
            if defn["auto"]:
                auto = _auto_collect(month)
                actual_value = auto.get(kpi_key, 0)
            else:
                act_row = conn.execute(
                    "SELECT actual_value FROM kpi_actuals WHERE month=? AND kpi_key=?",
                    (month, kpi_key)
                ).fetchone()
                actual_value = act_row["actual_value"] if act_row else 0

            target_value = tgt_row["target_value"] if tgt_row else 0
            pct = round(actual_value / target_value * 100, 1) if target_value > 0 else 0

            history.append({
                "month": month,
                "target": target_value,
                "actual": actual_value,
                "pct": pct,
            })

    return {
        "kpi_key": kpi_key,
        "label": KPI_DEFINITIONS[kpi_key]["label"],
        "unit": KPI_DEFINITIONS[kpi_key]["unit"],
        "history": history,
    }
