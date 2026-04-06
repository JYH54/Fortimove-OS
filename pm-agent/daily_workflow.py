#!/usr/bin/env python3
"""
Fortimove 일일 자동 워크플로우
================================
매일 아침 실행: Scout 결과 → 등록 가치 점수 → 상위 상품 추천 → Slack 알림

사용법:
  python daily_workflow.py                      # 전체 워크플로우 실행
  python daily_workflow.py --skip-slack          # Slack 알림 생략
  python daily_workflow.py --auto-premium 1      # 1위 상품 자동 run_premium 실행
  python daily_workflow.py --dry-run             # 실행 안 하고 리포트만

cron 등록 예시 (매일 09:30):
  30 9 * * * cd /path/to/pm-agent && python daily_workflow.py >> logs/daily.log 2>&1
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# .env 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


async def fetch_today_products(min_score: int = 50) -> List[Dict]:
    """Scout DB에서 최근 수집 상품 조회"""
    try:
        import asyncpg
    except ImportError:
        logger.warning("asyncpg 미설치 — Scout DB 연동 불가")
        return []

    try:
        conn = await asyncpg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "fortimove_images"),
            user=os.getenv("DB_USER", "fortimove"),
            password=os.getenv("DB_PASSWORD", "changeme")
        )

        rows = await conn.fetch("""
            SELECT id, product_name, brand, price, category, trend_score,
                   korea_demand, risk_status, url, region, source, date
            FROM wellness_products
            WHERE workflow_status = 'pending'
              AND trend_score >= $1
            ORDER BY trend_score DESC
            LIMIT 30
        """, min_score)

        await conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Scout DB 연결 실패: {e}")
        return []


def score_products(products: List[Dict]) -> List[Dict]:
    """상품별 등록 가치 점수 계산"""
    from product_score import calculate_product_score
    import re

    scored = []
    for p in products:
        trend = p.get("trend_score", 0) or 0
        price_str = str(p.get("price", "0"))
        numbers = re.findall(r'[\d.]+', price_str)
        price_val = float(numbers[0]) if numbers else 0

        # 지역별 국가 매핑
        region = (p.get("region", "") or "").lower()
        country_map = {"japan": "JP", "us": "US", "china": "CN", "uk": "US"}
        country = country_map.get(region, "CN")

        # 대략적 KRW 환산
        from country_config import get_country
        cc = get_country(country)
        rate = cc.exchange_rate if cc else 195
        estimated_krw = price_val * rate * 1.4 if price_val > 0 else 20000

        # 카테고리 매핑
        cat = (p.get("category", "") or "").lower()
        mapped = "general"
        for k, v in {"영양제": "supplement", "보충제": "supplement", "비타민": "supplement",
                      "건강": "wellness", "면역력": "wellness", "프로틴": "supplement",
                      "피트니스": "fitness", "뷰티": "beauty"}.items():
            if k in cat:
                mapped = v
                break

        # 소모품 여부
        consumable = any(kw in (p.get("product_name", "") or "")
                        for kw in ["분말", "정", "캡슐", "비타민", "프로틴", "콜라겐", "powder", "capsule"])

        score = calculate_product_score(
            margin_rate=28,
            risk_flags=[],
            sourcing_decision="통과" if p.get("risk_status") != "보류" else "보류",
            trend_score=trend,
            price_krw=estimated_krw,
            category=mapped,
            reorder_potential=consumable,
        )

        scored.append({
            "product": p,
            "score": score,
            "country": country,
            "category": mapped,
        })

    scored.sort(key=lambda x: x["score"].total, reverse=True)
    return scored


def generate_daily_report(scored: List[Dict]) -> str:
    """일일 리포트 텍스트 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    a_count = sum(1 for s in scored if s["score"].grade == "A")
    b_count = sum(1 for s in scored if s["score"].grade == "B")

    lines = [
        f"[Fortimove Daily Report] {now}",
        f"분석 상품: {len(scored)}개 | A등급: {a_count} | B등급: {b_count}",
        "",
    ]

    top5 = scored[:5]
    if top5:
        lines.append("=== TOP 5 추천 상품 ===")
        for i, item in enumerate(top5, 1):
            p = item["product"]
            s = item["score"]
            name = (p.get("product_name", "") or "")[:40]
            trend = p.get("trend_score", 0) or 0
            lines.append(f"{i}. [{s.grade}] {name} (트렌드:{trend}, 점수:{s.total:.0f})")

        # 1위 상품 실행 명령어
        best = top5[0]
        bp = best["product"]
        import re
        price_str = str(bp.get("price", "0"))
        nums = re.findall(r'[\d.]+', price_str)
        price = nums[0] if nums else "0"

        lines.append("")
        lines.append("=== 1위 상품 실행 명령어 ===")
        name = (bp.get("product_name", "") or "").replace('"', "'")
        lines.append(f'python run_premium.py --title "{name}" --price {price} --country {best["country"]} --category {best["category"]}')

    return "\n".join(lines)


def send_slack_report(report: str):
    """Slack으로 일일 리포트 전송"""
    webhook = os.getenv("SLACK_WEBHOOK_URL") or os.getenv("SCOUT_SLACK_WEBHOOK_URL")
    if not webhook:
        logger.info("Slack 웹훅 미설정 — 콘솔 출력만")
        return

    import httpx
    import time

    message = {"text": f"```\n{report}\n```"}

    for attempt in range(3):
        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(webhook, json=message)
                r.raise_for_status()
            logger.info("Slack 전송 완료")
            return
        except Exception as e:
            logger.warning(f"Slack 전송 실패 (시도 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    logger.error("Slack 전송 최종 실패")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fortimove 일일 자동 워크플로우")
    parser.add_argument("--min-score", type=int, default=50, help="최소 트렌드 점수")
    parser.add_argument("--skip-slack", action="store_true", help="Slack 알림 생략")
    parser.add_argument("--auto-premium", type=int, default=0, help="상위 N개 자동 run_premium 실행")
    parser.add_argument("--dry-run", action="store_true", help="리포트만 생성")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  Fortimove Daily Workflow")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    # 1. Scout DB에서 상품 조회
    print("[1/3] Scout DB 조회 중...")
    products = await fetch_today_products(args.min_score)

    if not products:
        print("  조건에 맞는 상품이 없습니다. 워크플로우 종료.")
        return

    print(f"  {len(products)}개 상품 발견")

    # 2. 등록 가치 점수 계산
    print("[2/3] 등록 가치 점수 계산 중...")
    scored = score_products(products)

    a_items = [s for s in scored if s["score"].grade == "A"]
    b_items = [s for s in scored if s["score"].grade == "B"]
    print(f"  A등급: {len(a_items)}개, B등급: {len(b_items)}개")

    # 3. 리포트 생성
    print("[3/3] 리포트 생성 중...")
    report = generate_daily_report(scored)
    print()
    print(report)

    # 리포트 파일 저장
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"reports/daily_{timestamp}.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n  저장: {report_path}")

    # JSON도 저장
    json_path = f"reports/daily_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_analyzed": len(scored),
            "a_grade": len(a_items),
            "b_grade": len(b_items),
            "top5": [
                {
                    "name": s["product"].get("product_name", ""),
                    "score": s["score"].total,
                    "grade": s["score"].grade,
                    "trend": s["product"].get("trend_score", 0),
                    "country": s["country"],
                }
                for s in scored[:5]
            ]
        }, f, ensure_ascii=False, indent=2)

    # 4. Slack 알림
    if not args.skip_slack and not args.dry_run:
        send_slack_report(report)

    # 5. 자동 프리미엄 실행
    if args.auto_premium > 0 and not args.dry_run:
        targets = [s for s in scored if s["score"].grade in ("A", "B")][:args.auto_premium]
        for item in targets:
            p = item["product"]
            import re
            price_str = str(p.get("price", "0"))
            nums = re.findall(r'[\d.]+', price_str)
            price = nums[0] if nums else "0"
            name = (p.get("product_name", "") or "").replace('"', "'")
            cmd = f'python run_premium.py --title "{name}" --price {price} --country {item["country"]} --category {item["category"]}'

            print(f"\n  자동 실행: {name[:40]}")
            print(f"  $ {cmd}")
            os.system(cmd)

    print(f"\n{'='*50}")
    print(f"  Daily Workflow 완료")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
