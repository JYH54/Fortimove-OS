"""
Sales Tracker — 매출 트래킹 시스템

1단계: CSV 업로드 (스마트스토어/쿠팡 주문 내역)
2단계: 수동 매출 입력
3단계: 자동 분석 (일별/주별/상품별)
→ COO 대시보드 연동
"""

import csv
import io
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sales_records (
    sale_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,        -- smartstore, coupang, 11st, etc
    order_id TEXT,
    product_name TEXT NOT NULL,
    option_name TEXT,
    quantity INTEGER DEFAULT 1,
    selling_price REAL DEFAULT 0,
    payment_amount REAL DEFAULT 0,
    cost_price REAL DEFAULT 0,      -- 원가
    profit REAL DEFAULT 0,          -- 순이익
    order_status TEXT,              -- 결제완료, 배송중, 배송완료, 취소, 반품
    order_date TEXT NOT NULL,       -- YYYY-MM-DD
    review_id TEXT,                 -- approval_queue FK (추적용)
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_platform ON sales_records(platform);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_records(order_date);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales_records(product_name);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales_records(order_status);
"""


class SalesTracker:

    def __init__(self):
        self.db_path = DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    # ── CSV 업로드 ────────────────────────────────────────

    def import_smartstore_csv(self, csv_content: str) -> Dict[str, int]:
        """스마트스토어 주문 CSV 임포트"""
        reader = csv.DictReader(io.StringIO(csv_content))
        imported = 0
        skipped = 0

        for row in reader:
            try:
                order_id = row.get("주문번호", row.get("상품주문번호", ""))
                if not order_id:
                    skipped += 1
                    continue

                sale_id = f"ss-{order_id}"
                if self._exists(sale_id):
                    skipped += 1
                    continue

                self._insert({
                    "sale_id": sale_id,
                    "platform": "smartstore",
                    "order_id": order_id,
                    "product_name": row.get("상품명", row.get("상품명(물품명)", "")),
                    "option_name": row.get("옵션정보", row.get("옵션", "")),
                    "quantity": int(row.get("수량", 1)),
                    "selling_price": self._parse_number(row.get("상품가격", row.get("판매가", 0))),
                    "payment_amount": self._parse_number(row.get("결제금액", row.get("총결제금액", 0))),
                    "order_status": row.get("주문상태", row.get("발주확인 여부", "")),
                    "order_date": self._parse_date(row.get("결제일", row.get("주문일시", ""))),
                })
                imported += 1
            except Exception as e:
                logger.warning(f"CSV 행 처리 실패: {e}")
                skipped += 1

        return {"imported": imported, "skipped": skipped}

    def import_coupang_csv(self, csv_content: str) -> Dict[str, int]:
        """쿠팡 주문 CSV 임포트"""
        reader = csv.DictReader(io.StringIO(csv_content))
        imported = 0
        skipped = 0

        for row in reader:
            try:
                order_id = row.get("주문번호", row.get("묶음배송번호", ""))
                if not order_id:
                    skipped += 1
                    continue

                sale_id = f"cp-{order_id}"
                if self._exists(sale_id):
                    skipped += 1
                    continue

                self._insert({
                    "sale_id": sale_id,
                    "platform": "coupang",
                    "order_id": order_id,
                    "product_name": row.get("노출상품명", row.get("상품명", "")),
                    "option_name": row.get("옵션", ""),
                    "quantity": int(row.get("수량", 1)),
                    "selling_price": self._parse_number(row.get("판매가", 0)),
                    "payment_amount": self._parse_number(row.get("결제액", row.get("정산예정금액", 0))),
                    "order_status": row.get("주문상태", ""),
                    "order_date": self._parse_date(row.get("주문일", row.get("결제일", ""))),
                })
                imported += 1
            except Exception as e:
                logger.warning(f"CSV 행 처리 실패: {e}")
                skipped += 1

        return {"imported": imported, "skipped": skipped}

    # ── 수동 입력 ─────────────────────────────────────────

    def add_sale(
        self,
        platform: str,
        product_name: str,
        selling_price: float,
        quantity: int = 1,
        cost_price: float = 0,
        order_date: str = None,
        option_name: str = "",
        order_status: str = "결제완료",
    ) -> str:
        import uuid
        sale_id = f"manual-{uuid.uuid4().hex[:8]}"
        profit = (selling_price - cost_price) * quantity if cost_price > 0 else 0

        self._insert({
            "sale_id": sale_id,
            "platform": platform,
            "order_id": sale_id,
            "product_name": product_name,
            "option_name": option_name,
            "quantity": quantity,
            "selling_price": selling_price,
            "payment_amount": selling_price * quantity,
            "cost_price": cost_price,
            "profit": profit,
            "order_status": order_status,
            "order_date": order_date or datetime.now().strftime("%Y-%m-%d"),
        })
        return sale_id

    # ── 분석 ──────────────────────────────────────────────

    def get_dashboard_stats(self, days: int = 30) -> Dict[str, Any]:
        """COO 대시보드용 매출 통계"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 전체 매출
            total = conn.execute("""
                SELECT
                    COUNT(*) as order_count,
                    COALESCE(SUM(quantity), 0) as total_quantity,
                    COALESCE(SUM(payment_amount), 0) as total_revenue,
                    COALESCE(SUM(profit), 0) as total_profit
                FROM sales_records
                WHERE order_date >= ? AND order_status NOT IN ('취소', '반품')
            """, (since,)).fetchone()

            # 플랫폼별
            by_platform = [dict(r) for r in conn.execute("""
                SELECT platform,
                    COUNT(*) as orders,
                    COALESCE(SUM(payment_amount), 0) as revenue
                FROM sales_records
                WHERE order_date >= ? AND order_status NOT IN ('취소', '반품')
                GROUP BY platform
            """, (since,)).fetchall()]

            # 일별 추이
            daily = [dict(r) for r in conn.execute("""
                SELECT order_date as date,
                    COUNT(*) as orders,
                    COALESCE(SUM(payment_amount), 0) as revenue
                FROM sales_records
                WHERE order_date >= ? AND order_status NOT IN ('취소', '반품')
                GROUP BY order_date ORDER BY order_date
            """, (since,)).fetchall()]

            # 상품별 TOP 10
            top_products = [dict(r) for r in conn.execute("""
                SELECT product_name,
                    SUM(quantity) as total_qty,
                    SUM(payment_amount) as total_revenue,
                    COUNT(*) as order_count
                FROM sales_records
                WHERE order_date >= ? AND order_status NOT IN ('취소', '반품')
                GROUP BY product_name
                ORDER BY total_revenue DESC LIMIT 10
            """, (since,)).fetchall()]

            # 취소/반품률
            cancel = conn.execute("""
                SELECT
                    COUNT(*) as cancel_count,
                    COALESCE(SUM(payment_amount), 0) as cancel_amount
                FROM sales_records
                WHERE order_date >= ? AND order_status IN ('취소', '반품')
            """, (since,)).fetchone()

        return {
            "period_days": days,
            "total": dict(total),
            "by_platform": by_platform,
            "daily_trend": daily,
            "top_products": top_products,
            "cancellations": dict(cancel),
        }

    def get_product_performance(self, product_name: str) -> Dict[str, Any]:
        """개별 상품 실적"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute("""
                SELECT * FROM sales_records
                WHERE product_name LIKE ?
                ORDER BY order_date DESC LIMIT 50
            """, (f"%{product_name}%",)).fetchall()]

        return {
            "product_name": product_name,
            "total_orders": len(rows),
            "total_revenue": sum(r.get("payment_amount", 0) for r in rows),
            "records": rows,
        }

    # ── 유틸 ──────────────────────────────────────────────

    def _exists(self, sale_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT 1 FROM sales_records WHERE sale_id=?", (sale_id,)).fetchone() is not None

    def _insert(self, data: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sales_records
                (sale_id, platform, order_id, product_name, option_name,
                 quantity, selling_price, payment_amount, cost_price, profit,
                 order_status, order_date, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data["sale_id"], data["platform"], data.get("order_id", ""),
                data["product_name"], data.get("option_name", ""),
                data.get("quantity", 1), data.get("selling_price", 0),
                data.get("payment_amount", 0), data.get("cost_price", 0),
                data.get("profit", 0), data.get("order_status", ""),
                data["order_date"], datetime.now().isoformat(),
            ))

    def _parse_number(self, val) -> float:
        if not val:
            return 0
        try:
            import re
            cleaned = re.sub(r"[^\d.]", "", str(val))
            return float(cleaned) if cleaned else 0
        except (ValueError, TypeError):
            return 0

    def _parse_date(self, val) -> str:
        if not val:
            return datetime.now().strftime("%Y-%m-%d")
        import re
        match = re.search(r"(\d{4})[.-/](\d{1,2})[.-/](\d{1,2})", str(val))
        if match:
            return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
        return datetime.now().strftime("%Y-%m-%d")
