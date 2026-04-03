#!/usr/bin/env python3
"""
상품 성과 추적 시스템
=====================
등록한 상품의 판매 성과를 추적하여 1,000개 한도 최적화

기능:
  - 상품별 매출/주문수/전환율 기록
  - 성과 기반 등급 재산정 (A~D)
  - 교체 추천 (D등급 상품 → Scout 추천으로 대체)
  - 광고 ROI 추적
  - 주간/월간 리포트

사용법:
  python sales_tracker.py add --name "콜라겐 분말" --orders 15 --revenue 448500
  python sales_tracker.py list                     # 전체 상품 성과
  python sales_tracker.py report                   # 주간 리포트
  python sales_tracker.py replace                  # 교체 추천
"""

import os
import sys
import json
import sqlite3
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# .env 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

logging.basicConfig(level=logging.WARNING)
DB_PATH = os.getenv("SALES_DB_PATH", "data/sales_tracker.db")


class SalesTracker:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA encoding = 'UTF-8'")
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    platform TEXT DEFAULT 'smartstore',
                    category TEXT DEFAULT 'general',
                    price_krw INTEGER DEFAULT 0,
                    cost_krw INTEGER DEFAULT 0,
                    registered_at TEXT DEFAULT (datetime('now')),
                    status TEXT DEFAULT 'active',
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    orders INTEGER DEFAULT 0,
                    revenue_krw INTEGER DEFAULT 0,
                    ad_spend_krw INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (product_id) REFERENCES products(product_id),
                    UNIQUE(product_id, date)
                );

                CREATE INDEX IF NOT EXISTS idx_sales_date ON daily_sales(date);
                CREATE INDEX IF NOT EXISTS idx_sales_product ON daily_sales(product_id);
            """)

    def add_product(self, name: str, platform: str = "smartstore",
                    category: str = "general", price: int = 0, cost: int = 0) -> int:
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO products (name, platform, category, price_krw, cost_krw) VALUES (?, ?, ?, ?, ?)",
                (name, platform, category, price, cost)
            )
            return cursor.lastrowid

    def record_sales(self, product_id: int, date: str, orders: int = 0,
                     revenue: int = 0, ad_spend: int = 0,
                     clicks: int = 0, impressions: int = 0):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO daily_sales (product_id, date, orders, revenue_krw, ad_spend_krw, clicks, impressions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, date) DO UPDATE SET
                    orders = excluded.orders,
                    revenue_krw = excluded.revenue_krw,
                    ad_spend_krw = excluded.ad_spend_krw,
                    clicks = excluded.clicks,
                    impressions = excluded.impressions
            """, (product_id, date, orders, revenue, ad_spend, clicks, impressions))

    def get_products(self, status: str = "active") -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE status = ? ORDER BY registered_at DESC",
                (status,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_product_by_name(self, name: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE name LIKE ?", (f"%{name}%",)
            ).fetchone()
        return dict(row) if row else None

    def get_performance(self, product_id: int, days: int = 30) -> Dict:
        """상품별 성과 요약"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as days_tracked,
                    COALESCE(SUM(orders), 0) as total_orders,
                    COALESCE(SUM(revenue_krw), 0) as total_revenue,
                    COALESCE(SUM(ad_spend_krw), 0) as total_ad_spend,
                    COALESCE(SUM(clicks), 0) as total_clicks,
                    COALESCE(SUM(impressions), 0) as total_impressions,
                    COALESCE(AVG(orders), 0) as avg_daily_orders,
                    COALESCE(AVG(revenue_krw), 0) as avg_daily_revenue
                FROM daily_sales
                WHERE product_id = ? AND date >= ?
            """, (product_id, cutoff)).fetchone()

        perf = dict(row)

        # 파생 지표
        if perf["total_clicks"] > 0:
            perf["conversion_rate"] = perf["total_orders"] / perf["total_clicks"] * 100
        else:
            perf["conversion_rate"] = 0

        if perf["total_ad_spend"] > 0:
            perf["roas"] = perf["total_revenue"] / perf["total_ad_spend"]
        else:
            perf["roas"] = 0

        profit = perf["total_revenue"] - perf["total_ad_spend"]
        perf["profit_krw"] = profit

        return perf

    def grade_product(self, product_id: int) -> str:
        """성과 기반 등급 판정"""
        perf = self.get_performance(product_id, days=14)

        # 14일 기준
        orders = perf["total_orders"]
        revenue = perf["total_revenue"]
        roas = perf["roas"]

        if orders >= 30 and roas >= 3.0:
            return "A"  # 강력한 판매 — 광고 확대
        elif orders >= 10 and roas >= 1.5:
            return "B"  # 양호 — 유지
        elif orders >= 3:
            return "C"  # 미진 — 상세페이지/광고 개선 필요
        else:
            return "D"  # 부진 — 교체 검토

    def get_replace_candidates(self) -> List[Dict]:
        """교체 대상 (D등급) 상품 목록"""
        products = self.get_products("active")
        candidates = []
        for p in products:
            grade = self.grade_product(p["product_id"])
            if grade == "D":
                perf = self.get_performance(p["product_id"], days=14)
                candidates.append({**p, "grade": grade, "performance": perf})
        return candidates


def cmd_add(args):
    tracker = SalesTracker()
    today = datetime.now().strftime("%Y-%m-%d")

    # 상품 존재 확인
    existing = tracker.get_product_by_name(args.name)
    if existing:
        product_id = existing["product_id"]
        print(f"  기존 상품 사용: ID {product_id}")
    else:
        product_id = tracker.add_product(
            name=args.name,
            platform=args.platform,
            category=args.category,
            price=args.price or 0,
            cost=args.cost or 0,
        )
        print(f"  ✅ 새 상품 등록: ID {product_id}")

    # 판매 데이터 기록
    tracker.record_sales(
        product_id=product_id,
        date=args.date or today,
        orders=args.orders or 0,
        revenue=args.revenue or 0,
        ad_spend=args.ad_spend or 0,
        clicks=args.clicks or 0,
        impressions=args.impressions or 0,
    )
    print(f"  ✅ 판매 데이터 기록: {args.date or today}")


def cmd_list(args):
    tracker = SalesTracker()
    products = tracker.get_products()

    if not products:
        print("  ℹ️  등록된 상품이 없습니다")
        return

    print(f"\n{'#':>3} {'등급':<3} {'상품명':<30} {'14일 주문':>8} {'14일 매출':>12} {'ROAS':>6} {'플랫폼':<12}")
    print("-" * 80)

    for p in products:
        perf = tracker.get_performance(p["product_id"], days=14)
        grade = tracker.grade_product(p["product_id"])
        name = p["name"][:28]
        roas = f"{perf['roas']:.1f}x" if perf["roas"] > 0 else "-"

        marker = {"A": "★", "B": "●", "C": "△", "D": "✕"}.get(grade, " ")
        print(f"{p['product_id']:>3} {marker}[{grade}] {name:<30} {perf['total_orders']:>8} ₩{perf['total_revenue']:>10,} {roas:>6} {p['platform']:<12}")


def cmd_report(args):
    tracker = SalesTracker()
    products = tracker.get_products()

    if not products:
        print("  ℹ️  등록된 상품이 없습니다")
        return

    total_revenue = 0
    total_orders = 0
    total_ad = 0
    grades = {"A": 0, "B": 0, "C": 0, "D": 0}

    print(f"\n{'='*60}")
    print(f"  주간 성과 리포트 ({datetime.now().strftime('%Y-%m-%d')})")
    print(f"{'='*60}\n")

    for p in products:
        perf = tracker.get_performance(p["product_id"], days=7)
        grade = tracker.grade_product(p["product_id"])
        grades[grade] = grades.get(grade, 0) + 1
        total_revenue += perf["total_revenue"]
        total_orders += perf["total_orders"]
        total_ad += perf["total_ad_spend"]

    print(f"  등록 상품: {len(products)}개 / 1,000개 한도")
    print(f"  7일 총 매출: ₩{total_revenue:,}")
    print(f"  7일 총 주문: {total_orders}건")
    print(f"  7일 광고비: ₩{total_ad:,}")
    if total_ad > 0:
        print(f"  전체 ROAS: {total_revenue/total_ad:.1f}x")
    print(f"  수익: ₩{total_revenue - total_ad:,}")
    print()
    print(f"  등급 분포: A({grades['A']}) B({grades['B']}) C({grades['C']}) D({grades['D']})")

    if grades["D"] > 0:
        print(f"\n  ⚠️  D등급 {grades['D']}개 — 교체 검토 필요 (python sales_tracker.py replace)")


def cmd_replace(args):
    tracker = SalesTracker()
    candidates = tracker.get_replace_candidates()

    if not candidates:
        print("  ✅ 교체 대상 상품이 없습니다 (모든 상품 C등급 이상)")
        return

    print(f"\n{'='*60}")
    print(f"  교체 추천 ({len(candidates)}개 D등급 상품)")
    print(f"{'='*60}\n")

    for c in candidates:
        perf = c["performance"]
        print(f"  ✕ {c['name']}")
        print(f"    14일 주문: {perf['total_orders']}건 / 매출: ₩{perf['total_revenue']:,}")
        print(f"    → 이 상품을 삭제하고 Scout 추천 상품으로 교체하세요")
        print(f"    → python scout_recommend.py --top 1")
        print()


def main():
    parser = argparse.ArgumentParser(description="상품 성과 추적")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="판매 데이터 기록")
    p_add.add_argument("--name", required=True, help="상품명")
    p_add.add_argument("--orders", type=int, default=0, help="주문 수")
    p_add.add_argument("--revenue", type=int, default=0, help="매출 (원)")
    p_add.add_argument("--ad-spend", type=int, default=0, help="광고비 (원)")
    p_add.add_argument("--clicks", type=int, default=0, help="클릭 수")
    p_add.add_argument("--impressions", type=int, default=0, help="노출 수")
    p_add.add_argument("--date", default=None, help="날짜 (YYYY-MM-DD, 기본: 오늘)")
    p_add.add_argument("--platform", default="smartstore", help="플랫폼")
    p_add.add_argument("--category", default="general", help="카테고리")
    p_add.add_argument("--price", type=int, default=0, help="판매가")
    p_add.add_argument("--cost", type=int, default=0, help="원가")

    # list
    sub.add_parser("list", help="전체 상품 성과 목록")

    # report
    sub.add_parser("report", help="주간 성과 리포트")

    # replace
    sub.add_parser("replace", help="교체 추천 (D등급 상품)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    {"add": cmd_add, "list": cmd_list, "report": cmd_report, "replace": cmd_replace}[args.command](args)


if __name__ == "__main__":
    main()
