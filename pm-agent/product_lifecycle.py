#!/usr/bin/env python3
"""
상품 라이프사이클 관리
=======================
테스트 → 반복 판매 → PB 전환 판단

3단계 라이프사이클:
  1. 테스트: 소량 등록, 시장 반응 확인 (2주)
  2. 반복 판매: 안정적 매출 확인, 재고 확보 (1~3개월)
  3. PB 전환 검토: 자체 브랜드화 가능 여부 판단

사용법:
  python product_lifecycle.py status              # 전체 상품 단계 현황
  python product_lifecycle.py check "콜라겐 분말"  # 특정 상품 전환 판단
  python product_lifecycle.py promote              # 승격 대상 추천
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# .env 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

from sales_tracker import SalesTracker

logging.basicConfig(level=logging.WARNING)


class LifecycleManager:
    """상품 라이프사이클 전환 판단 엔진"""

    # 테스트 → 반복 판매 전환 기준
    TEST_TO_REPEAT = {
        "min_days": 14,              # 최소 14일 운영
        "min_orders": 20,            # 최소 20건 주문
        "min_revenue": 500000,       # 최소 50만원 매출
        "min_roas": 1.5,             # 최소 ROAS 1.5x
        "max_return_rate": 0.05,     # 반품률 5% 이하
    }

    # 반복 판매 → PB 전환 검토 기준
    REPEAT_TO_PB = {
        "min_days": 60,              # 최소 60일 반복 판매
        "min_orders": 200,           # 최소 200건 주문
        "min_revenue": 5000000,      # 최소 500만원 매출
        "min_roas": 2.5,             # ROAS 2.5x 이상
        "min_monthly_growth": 0.1,   # 월 매출 성장률 10% 이상
        "min_repeat_rate": 0.15,     # 재구매율 15% 이상 (추정)
    }

    def __init__(self):
        self.tracker = SalesTracker()

    def get_lifecycle_stage(self, product_id: int) -> Dict:
        """현재 라이프사이클 단계 판단"""
        products = self.tracker.get_products()
        product = next((p for p in products if p["product_id"] == product_id), None)
        if not product:
            return {"stage": "unknown", "reason": "상품을 찾을 수 없음"}

        perf_14d = self.tracker.get_performance(product_id, days=14)
        perf_30d = self.tracker.get_performance(product_id, days=30)
        perf_60d = self.tracker.get_performance(product_id, days=60)

        # 등록일 기준 경과일
        registered = product.get("registered_at", "")
        if registered:
            try:
                reg_date = datetime.fromisoformat(registered)
                days_active = (datetime.now() - reg_date).days
            except (ValueError, TypeError):
                days_active = perf_30d.get("days_tracked", 0)
        else:
            days_active = perf_30d.get("days_tracked", 0)

        result = {
            "product_id": product_id,
            "name": product["name"],
            "days_active": days_active,
            "performance_14d": perf_14d,
            "performance_30d": perf_30d,
            "performance_60d": perf_60d,
        }

        # PB 전환 가능?
        if self._check_pb_ready(perf_60d, days_active):
            result["stage"] = "PB 전환 검토"
            result["next_action"] = "PB 브랜딩 기획 + OEM 제조사 탐색"
            result["grade"] = "S"
            return result

        # 반복 판매 가능?
        if self._check_repeat_ready(perf_30d, days_active):
            result["stage"] = "반복 판매"
            result["next_action"] = "재고 안정 확보 + 광고 최적화 + 리뷰 축적"
            result["grade"] = "A"

            # PB까지 남은 조건
            pb_gaps = self._get_pb_gaps(perf_60d, days_active)
            if pb_gaps:
                result["pb_gaps"] = pb_gaps
            return result

        # 아직 테스트 단계
        result["stage"] = "테스트"
        result["grade"] = "B" if perf_14d["total_orders"] >= 5 else "C"

        # 반복 판매까지 남은 조건
        repeat_gaps = self._get_repeat_gaps(perf_14d, days_active)
        result["repeat_gaps"] = repeat_gaps

        if perf_14d["total_orders"] == 0 and days_active >= 14:
            result["stage"] = "테스트 실패"
            result["next_action"] = "상세페이지 개선 또는 상품 교체"
            result["grade"] = "D"
        else:
            result["next_action"] = "광고 지속 + 리뷰 확보 + 데이터 수집"

        return result

    def _check_repeat_ready(self, perf: Dict, days: int) -> bool:
        c = self.TEST_TO_REPEAT
        return (
            days >= c["min_days"]
            and perf["total_orders"] >= c["min_orders"]
            and perf["total_revenue"] >= c["min_revenue"]
            and (perf["roas"] >= c["min_roas"] or perf["total_ad_spend"] == 0)
        )

    def _check_pb_ready(self, perf: Dict, days: int) -> bool:
        c = self.REPEAT_TO_PB
        return (
            days >= c["min_days"]
            and perf["total_orders"] >= c["min_orders"]
            and perf["total_revenue"] >= c["min_revenue"]
            and (perf["roas"] >= c["min_roas"] or perf["total_ad_spend"] == 0)
        )

    def _get_repeat_gaps(self, perf: Dict, days: int) -> List[str]:
        c = self.TEST_TO_REPEAT
        gaps = []
        if days < c["min_days"]:
            gaps.append(f"운영 기간: {days}일/{c['min_days']}일")
        if perf["total_orders"] < c["min_orders"]:
            gaps.append(f"주문: {perf['total_orders']}건/{c['min_orders']}건")
        if perf["total_revenue"] < c["min_revenue"]:
            gaps.append(f"매출: {perf['total_revenue']:,}원/{c['min_revenue']:,}원")
        return gaps

    def _get_pb_gaps(self, perf: Dict, days: int) -> List[str]:
        c = self.REPEAT_TO_PB
        gaps = []
        if days < c["min_days"]:
            gaps.append(f"운영 기간: {days}일/{c['min_days']}일")
        if perf["total_orders"] < c["min_orders"]:
            gaps.append(f"주문: {perf['total_orders']}건/{c['min_orders']}건")
        if perf["total_revenue"] < c["min_revenue"]:
            gaps.append(f"매출: {perf['total_revenue']:,}원/{c['min_revenue']:,}원")
        return gaps

    def get_all_stages(self) -> List[Dict]:
        """전체 상품 라이프사이클 현황"""
        products = self.tracker.get_products()
        return [self.get_lifecycle_stage(p["product_id"]) for p in products]

    def get_promote_candidates(self) -> List[Dict]:
        """승격 대상 상품 추천"""
        all_stages = self.get_all_stages()
        return [s for s in all_stages if s["stage"] in ("반복 판매", "PB 전환 검토")]


def cmd_status(args):
    mgr = LifecycleManager()
    stages = mgr.get_all_stages()

    if not stages:
        print("  등록된 상품이 없습니다")
        return

    # 단계별 집계
    counts = {}
    for s in stages:
        stage = s["stage"]
        counts[stage] = counts.get(stage, 0) + 1

    print(f"\n  상품 라이프사이클 현황 ({len(stages)}개)")
    print(f"  {'='*40}")
    for stage, count in counts.items():
        print(f"  {stage}: {count}개")
    print()

    print(f"  {'#':>3} {'등급':<3} {'단계':<12} {'상품명':<25} {'일수':>4} {'30일주문':>7} {'30일매출':>10}")
    print(f"  {'-'*70}")
    for s in stages:
        name = s["name"][:23]
        perf = s.get("performance_30d", {})
        orders = perf.get("total_orders", 0)
        revenue = perf.get("total_revenue", 0)
        print(f"  {s['product_id']:>3} [{s.get('grade','?')}] {s['stage']:<12} {name:<25} {s.get('days_active',0):>4} {orders:>7} {revenue:>10,}")


def cmd_check(args):
    mgr = LifecycleManager()
    tracker = mgr.tracker
    product = tracker.get_product_by_name(args.name)

    if not product:
        print(f"  상품을 찾을 수 없습니다: {args.name}")
        return

    stage = mgr.get_lifecycle_stage(product["product_id"])

    print(f"\n  {'='*50}")
    print(f"  상품: {stage['name']}")
    print(f"  단계: {stage['stage']} [{stage.get('grade', '?')}등급]")
    print(f"  운영: {stage.get('days_active', 0)}일")
    print(f"  {'='*50}")

    perf = stage.get("performance_30d", {})
    print(f"  30일 주문: {perf.get('total_orders', 0)}건")
    print(f"  30일 매출: {perf.get('total_revenue', 0):,}원")
    print(f"  30일 ROAS: {perf.get('roas', 0):.1f}x")
    print()

    if stage.get("next_action"):
        print(f"  다음 조치: {stage['next_action']}")

    gaps = stage.get("repeat_gaps") or stage.get("pb_gaps")
    if gaps:
        print(f"\n  다음 단계까지 부족한 조건:")
        for g in gaps:
            print(f"    - {g}")


def cmd_promote(args):
    mgr = LifecycleManager()
    candidates = mgr.get_promote_candidates()

    if not candidates:
        print("  승격 대상 상품이 없습니다")
        return

    print(f"\n  승격 대상 상품 ({len(candidates)}개)")
    print(f"  {'='*50}")
    for s in candidates:
        print(f"  [{s.get('grade','?')}] {s['name']} — {s['stage']}")
        print(f"      {s.get('next_action', '')}")
        print()


def main():
    parser = argparse.ArgumentParser(description="상품 라이프사이클 관리")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="전체 상품 단계 현황")

    p_check = sub.add_parser("check", help="특정 상품 전환 판단")
    p_check.add_argument("name", help="상품명 (부분 일치)")

    sub.add_parser("promote", help="승격 대상 추천")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"status": cmd_status, "check": cmd_check, "promote": cmd_promote}[args.command](args)


if __name__ == "__main__":
    main()
