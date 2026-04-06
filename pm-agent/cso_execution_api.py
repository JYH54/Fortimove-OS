"""
CSO Execution API — 전략을 "보고서"에서 "실행 시스템"으로 전환

제공 기능:
1. 포트폴리오 저장 (AI 생성 → 대표가 확정 → DB 저장)
2. 포트폴리오 → 실제 상품 매핑 (카테고리/브랜드/키워드)
3. 포트폴리오별 SKU/매출/마진 실시간 진행률
4. 이번 주 액션 아이템 (체크 가능)
5. 포트폴리오 수정 (SKU 목표, 매출 목표 대표가 직접 조정)
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
router = APIRouter(prefix="/api/cso", tags=["CSO-Execution"])
DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


def _init():
    with sqlite3.connect(DB_PATH) as conn:
        # 포트폴리오 (대표가 채택한 전략)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cso_portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                grade TEXT DEFAULT 'A',
                category_keywords TEXT DEFAULT '[]',
                target_sku INTEGER DEFAULT 0,
                target_margin_rate REAL DEFAULT 0,
                target_monthly_revenue REAL DEFAULT 0,
                description TEXT DEFAULT '',
                ai_recommendation TEXT DEFAULT '',
                pivot_plan TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
        """)
        # 주간 액션 아이템
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cso_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER,
                week TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                priority INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                due_date TEXT DEFAULT '',
                completed_at TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                FOREIGN KEY(portfolio_id) REFERENCES cso_portfolios(id)
            )
        """)
        conn.commit()

_init()


# ═══════════════════════════════════════════════════════════
# 모델
# ═══════════════════════════════════════════════════════════

class PortfolioRequest(BaseModel):
    name: str
    grade: str = "A"
    category_keywords: List[str] = []
    target_sku: int = 0
    target_margin_rate: float = 0
    target_monthly_revenue: float = 0
    description: str = ""
    ai_recommendation: str = ""
    pivot_plan: str = ""


class ActionRequest(BaseModel):
    portfolio_id: Optional[int] = None
    week: str  # "2026-W15"
    title: str
    description: str = ""
    priority: int = 1
    due_date: str = ""


class ActionUpdateRequest(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# 포트폴리오 CRUD
# ═══════════════════════════════════════════════════════════

@router.get("/portfolios")
async def list_portfolios():
    """활성 포트폴리오 목록 + 실제 진행률"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM cso_portfolios WHERE status='active' ORDER BY id"
        ).fetchall()
        portfolios = []
        for r in rows:
            p = dict(r)
            p["category_keywords"] = json.loads(p.get("category_keywords") or "[]")
            # 실제 진행률 계산
            p["progress"] = _calculate_progress(conn, p)
            portfolios.append(p)

    return {"portfolios": portfolios, "total": len(portfolios)}


def _calculate_progress(conn: sqlite3.Connection, portfolio: Dict) -> Dict:
    """포트폴리오별 실제 진행률 (등록 상품/승인/콘텐츠/리디자인)"""
    keywords = portfolio.get("category_keywords") or []
    if isinstance(keywords, str):
        keywords = json.loads(keywords or "[]")

    if not keywords:
        return {
            "registered_sku": 0,
            "approved_sku": 0,
            "sku_progress_pct": 0,
            "content_done": 0,
            "redesign_done": 0,
        }

    # 키워드 LIKE 조건 생성
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("(source_title LIKE ? OR generated_naver_title LIKE ?)")
        params.append(f"%{kw}%")
        params.append(f"%{kw}%")
    where = " OR ".join(conditions)

    # 등록된 상품 수
    row = conn.execute(f"SELECT COUNT(*) as c FROM approval_queue WHERE {where}", tuple(params)).fetchone()
    registered = row["c"] if row else 0

    # 승인된 상품
    row = conn.execute(
        f"SELECT COUNT(*) as c FROM approval_queue WHERE ({where}) AND review_status IN ('approved_for_export','approved_for_upload')",
        tuple(params)
    ).fetchone()
    approved = row["c"] if row else 0

    # 콘텐츠 생성 완료
    row = conn.execute(
        f"SELECT COUNT(*) as c FROM approval_queue WHERE ({where}) AND generated_naver_title IS NOT NULL",
        tuple(params)
    ).fetchone()
    content_done = row["c"] if row else 0

    # 리디자인 완료
    try:
        row = conn.execute(
            f"""SELECT COUNT(*) as c FROM redesign_queue r
                WHERE r.status='completed' AND r.review_id IN (
                    SELECT review_id FROM approval_queue WHERE {where}
                )""",
            tuple(params)
        ).fetchone()
        redesign_done = row["c"] if row else 0
    except Exception:
        redesign_done = 0

    target = portfolio.get("target_sku", 0) or 0
    pct = round(registered / target * 100, 1) if target > 0 else 0

    return {
        "registered_sku": registered,
        "approved_sku": approved,
        "sku_progress_pct": pct,
        "content_done": content_done,
        "redesign_done": redesign_done,
    }


@router.post("/portfolios")
async def create_portfolio(request: PortfolioRequest):
    """새 포트폴리오 추가"""
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
            INSERT INTO cso_portfolios
            (name, grade, category_keywords, target_sku, target_margin_rate, target_monthly_revenue,
             description, ai_recommendation, pivot_plan, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (
            request.name, request.grade,
            json.dumps(request.category_keywords, ensure_ascii=False),
            request.target_sku, request.target_margin_rate, request.target_monthly_revenue,
            request.description, request.ai_recommendation, request.pivot_plan,
            now, now
        ))
        pid = cursor.lastrowid
        conn.commit()
    return {"status": "success", "portfolio_id": pid}


@router.put("/portfolios/{portfolio_id}")
async def update_portfolio(portfolio_id: int, request: PortfolioRequest):
    """포트폴리오 수정"""
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE cso_portfolios SET
                name=?, grade=?, category_keywords=?, target_sku=?,
                target_margin_rate=?, target_monthly_revenue=?,
                description=?, pivot_plan=?, updated_at=?
            WHERE id=?
        """, (
            request.name, request.grade,
            json.dumps(request.category_keywords, ensure_ascii=False),
            request.target_sku, request.target_margin_rate, request.target_monthly_revenue,
            request.description, request.pivot_plan, now, portfolio_id
        ))
        conn.commit()
    return {"status": "success"}


@router.delete("/portfolios/{portfolio_id}")
async def delete_portfolio(portfolio_id: int):
    """포트폴리오 삭제 (비활성화)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE cso_portfolios SET status='archived' WHERE id=?", (portfolio_id,))
        conn.commit()
    return {"status": "success"}


@router.get("/portfolios/{portfolio_id}/products")
async def portfolio_products(portfolio_id: int):
    """포트폴리오에 매핑된 실제 상품 목록"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        p = conn.execute("SELECT * FROM cso_portfolios WHERE id=?", (portfolio_id,)).fetchone()
        if not p:
            raise HTTPException(404, "Portfolio not found")
        keywords = json.loads(p["category_keywords"] or "[]")

        if not keywords:
            return {"portfolio_id": portfolio_id, "products": [], "total": 0}

        conditions = []
        params = []
        for kw in keywords:
            conditions.append("(source_title LIKE ? OR generated_naver_title LIKE ?)")
            params.append(f"%{kw}%")
            params.append(f"%{kw}%")
        where = " OR ".join(conditions)

        rows = conn.execute(f"""
            SELECT review_id, source_title, generated_naver_title, score, review_status,
                   generated_price, created_at
            FROM approval_queue WHERE {where}
            ORDER BY created_at DESC LIMIT 100
        """, tuple(params)).fetchall()

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": p["name"],
            "keywords": keywords,
            "products": [dict(r) for r in rows],
            "total": len(rows),
        }


# ═══════════════════════════════════════════════════════════
# 주간 액션 아이템
# ═══════════════════════════════════════════════════════════

def _current_week() -> str:
    now = datetime.now()
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@router.get("/actions")
async def list_actions(week: Optional[str] = None, portfolio_id: Optional[int] = None):
    """주간 액션 아이템 목록"""
    if not week:
        week = _current_week()

    sql = "SELECT * FROM cso_actions WHERE week=?"
    params = [week]
    if portfolio_id:
        sql += " AND portfolio_id=?"
        params.append(portfolio_id)
    sql += " ORDER BY status, priority DESC, id"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, tuple(params)).fetchall()
        actions = [dict(r) for r in rows]

    # 요약
    total = len(actions)
    completed = sum(1 for a in actions if a["status"] == "completed")
    pending = total - completed

    return {
        "week": week,
        "actions": actions,
        "summary": {"total": total, "completed": completed, "pending": pending,
                    "completion_pct": round(completed / total * 100) if total > 0 else 0}
    }


@router.post("/actions")
async def create_action(request: ActionRequest):
    """액션 추가"""
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
            INSERT INTO cso_actions
            (portfolio_id, week, title, description, priority, due_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (request.portfolio_id, request.week, request.title, request.description,
              request.priority, request.due_date, now))
        aid = cursor.lastrowid
        conn.commit()
    return {"status": "success", "action_id": aid}


@router.patch("/actions/{action_id}")
async def update_action(action_id: int, request: ActionUpdateRequest):
    """액션 완료/수정"""
    updates = []
    params = []
    if request.status:
        updates.append("status=?")
        params.append(request.status)
        if request.status == "completed":
            updates.append("completed_at=?")
            params.append(datetime.now().isoformat())
    if request.title:
        updates.append("title=?")
        params.append(request.title)
    if request.description is not None:
        updates.append("description=?")
        params.append(request.description)
    if not updates:
        return {"status": "no_change"}
    params.append(action_id)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"UPDATE cso_actions SET {', '.join(updates)} WHERE id=?", tuple(params))
        conn.commit()
    return {"status": "success"}


@router.delete("/actions/{action_id}")
async def delete_action(action_id: int):
    """액션 삭제"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM cso_actions WHERE id=?", (action_id,))
        conn.commit()
    return {"status": "success"}


# ═══════════════════════════════════════════════════════════
# AI 전략 → 실제 포트폴리오로 변환
# ═══════════════════════════════════════════════════════════

class AdoptRequest(BaseModel):
    """AI가 생성한 전략을 대표가 채택"""
    name: str
    grade: str = "A"
    category_keywords: List[str] = []
    target_sku: int = 0
    target_margin_rate: float = 0
    target_monthly_revenue: float = 0
    description: str = ""
    ai_recommendation: str = ""
    pivot_plan: str = ""


@router.post("/adopt")
async def adopt_strategy(request: AdoptRequest):
    """AI 전략 제안을 포트폴리오로 채택 → DB에 저장"""
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        # 동일 이름 이미 있으면 업데이트
        existing = conn.execute("SELECT id FROM cso_portfolios WHERE name=? AND status='active'", (request.name,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE cso_portfolios SET
                    grade=?, category_keywords=?, target_sku=?,
                    target_margin_rate=?, target_monthly_revenue=?,
                    description=?, ai_recommendation=?, pivot_plan=?, updated_at=?
                WHERE id=?
            """, (
                request.grade, json.dumps(request.category_keywords, ensure_ascii=False),
                request.target_sku, request.target_margin_rate, request.target_monthly_revenue,
                request.description, request.ai_recommendation, request.pivot_plan, now,
                existing[0]
            ))
            pid = existing[0]
        else:
            cursor = conn.execute("""
                INSERT INTO cso_portfolios
                (name, grade, category_keywords, target_sku, target_margin_rate, target_monthly_revenue,
                 description, ai_recommendation, pivot_plan, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """, (
                request.name, request.grade,
                json.dumps(request.category_keywords, ensure_ascii=False),
                request.target_sku, request.target_margin_rate, request.target_monthly_revenue,
                request.description, request.ai_recommendation, request.pivot_plan,
                now, now
            ))
            pid = cursor.lastrowid
        conn.commit()
    return {"status": "success", "portfolio_id": pid}


@router.get("/overview")
async def cso_overview():
    """CSO 대시보드 종합 뷰 — 포트폴리오 + 실적 + 이번 주 액션"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # 포트폴리오
        portfolios = []
        rows = conn.execute("SELECT * FROM cso_portfolios WHERE status='active' ORDER BY grade, id").fetchall()
        for r in rows:
            p = dict(r)
            p["category_keywords"] = json.loads(p.get("category_keywords") or "[]")
            p["progress"] = _calculate_progress(conn, p)
            portfolios.append(p)

        # 이번 주 액션
        week = _current_week()
        actions = [dict(r) for r in conn.execute(
            "SELECT * FROM cso_actions WHERE week=? ORDER BY status, priority DESC", (week,)
        ).fetchall()]

    # 합계 (실제 진행률 기반)
    total_target_sku = sum(p.get("target_sku", 0) for p in portfolios)
    total_registered = sum(p["progress"]["registered_sku"] for p in portfolios)
    total_approved = sum(p["progress"]["approved_sku"] for p in portfolios)
    total_target_revenue = sum(p.get("target_monthly_revenue", 0) for p in portfolios)

    return {
        "portfolios": portfolios,
        "actions": {
            "week": week,
            "items": actions,
            "total": len(actions),
            "completed": sum(1 for a in actions if a["status"] == "completed"),
        },
        "totals": {
            "portfolio_count": len(portfolios),
            "target_sku": total_target_sku,
            "registered_sku": total_registered,
            "approved_sku": total_approved,
            "sku_progress_pct": round(total_registered / total_target_sku * 100, 1) if total_target_sku > 0 else 0,
            "target_monthly_revenue": total_target_revenue,
        }
    }
