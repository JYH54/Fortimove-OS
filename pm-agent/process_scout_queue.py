#!/usr/bin/env python3
"""
Daily Scout → Fast-Track 자동 처리
==================================
Scout가 수집한 pending 상품을 자동으로 소싱+마진 검증 처리

사용법:
  python process_scout_queue.py                    # pending 전부 처리
  python process_scout_queue.py --limit 10         # 10개만 처리
  python process_scout_queue.py --region japan     # 일본 상품만
  python process_scout_queue.py --min-score 70     # 트렌드 점수 70 이상만
  python process_scout_queue.py --dry-run          # 처리 안 하고 목록만 확인

필수: PostgreSQL DB 연결 (Docker 실행 중이어야 함)
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime
from pathlib import Path

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


async def fetch_pending_products(args) -> list:
    """Scout DB에서 pending 상품 조회"""
    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg 필요: pip install asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "fortimove_images"),
        user=os.getenv("DB_USER", "fortimove"),
        password=os.getenv("DB_PASSWORD", "changeme")
    )

    query = """
        SELECT id, product_name, brand, price, category, trend_score,
               korea_demand, risk_status, url, region, source
        FROM wellness_products
        WHERE workflow_status = 'pending'
    """
    params = []

    if args.region:
        query += f" AND region = ${len(params)+1}"
        params.append(args.region)

    if args.min_score:
        query += f" AND trend_score >= ${len(params)+1}"
        params.append(args.min_score)

    query += " ORDER BY trend_score DESC"

    if args.limit:
        query += f" LIMIT ${len(params)+1}"
        params.append(args.limit)

    rows = await conn.fetch(query, *params)
    await conn.close()

    return [dict(r) for r in rows]


async def update_product_status(product_id: int, status: str, result_json: str = None):
    """상품 워크플로우 상태 업데이트"""
    import asyncpg

    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "fortimove_images"),
        user=os.getenv("DB_USER", "fortimove"),
        password=os.getenv("DB_PASSWORD", "changeme")
    )

    await conn.execute(
        "UPDATE wellness_products SET workflow_status = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
        status, product_id
    )
    await conn.close()


def process_product(product: dict) -> dict:
    """개별 상품을 소싱+마진 에이전트로 처리"""
    from agent_framework import AgentRegistry
    from real_agents import register_real_agents
    from product_registration_agent import register_product_registration_agent

    registry = register_real_agents()
    register_product_registration_agent(registry)

    result = {"product_id": product["id"], "product_name": product["product_name"]}

    # 소싱 리스크 체크
    sourcing = registry.get("sourcing")
    if sourcing:
        sourcing_input = {
            "source_url": product.get("url", ""),
            "source_title": product["product_name"],
            "source_price_cny": _parse_price(product.get("price", "0")),
            "market": "korea"
        }
        sr = sourcing.execute(sourcing_input)
        if sr.is_success():
            result["sourcing_decision"] = sr.output.get("sourcing_decision", "?")
            result["risk_flags"] = sr.output.get("risk_flags", [])
        else:
            result["sourcing_decision"] = "오류"
            result["error"] = sr.error

    return result


def _parse_price(price_str: str) -> float:
    """가격 문자열을 float로 변환"""
    import re
    numbers = re.findall(r'[\d.]+', str(price_str))
    return float(numbers[0]) if numbers else 0.0


async def main():
    parser = argparse.ArgumentParser(description="Scout 큐 자동 처리")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 개수")
    parser.add_argument("--region", type=str, default=None, help="지역 필터 (japan/china/us/uk)")
    parser.add_argument("--min-score", type=int, default=None, help="최소 트렌드 점수")
    parser.add_argument("--dry-run", action="store_true", help="실행 안 하고 목록만 확인")
    args = parser.parse_args()

    # API 키 확인
    if not args.dry_run and not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY 환경변수가 필요합니다")
        sys.exit(1)

    print("\n📡 Scout DB에서 pending 상품 조회 중...")
    products = await fetch_pending_products(args)

    if not products:
        print("  ℹ️  처리할 pending 상품이 없습니다")
        return

    print(f"  📊 {len(products)}개 상품 발견\n")

    # 목록 출력
    print(f"{'#':>3} {'점수':>4} {'지역':<8} {'상품명':<40} {'가격':<12}")
    print("-" * 70)
    for i, p in enumerate(products, 1):
        name = p["product_name"][:38]
        print(f"{i:>3} {p.get('trend_score',0):>4} {p.get('region','?'):<8} {name:<40} {p.get('price','?'):<12}")

    if args.dry_run:
        print(f"\n  ℹ️  --dry-run 모드: 실제 처리는 하지 않습니다")
        return

    print(f"\n🚀 {len(products)}개 상품 처리 시작...\n")

    passed = 0
    held = 0
    excluded = 0
    errors = 0

    for i, product in enumerate(products, 1):
        print(f"[{i}/{len(products)}] {product['product_name'][:50]}...", end=" ")

        try:
            await update_product_status(product["id"], "processing")
            result = process_product(product)
            decision = result.get("sourcing_decision", "오류")

            if decision == "통과":
                await update_product_status(product["id"], "passed")
                print(f"✅ 통과")
                passed += 1
            elif decision == "보류":
                await update_product_status(product["id"], "hold")
                flags = result.get("risk_flags", [])
                print(f"⚠️  보류 ({', '.join(flags[:2])})")
                held += 1
            elif decision == "제외":
                await update_product_status(product["id"], "rejected")
                print(f"❌ 제외")
                excluded += 1
            else:
                await update_product_status(product["id"], "error")
                print(f"❓ {decision}")
                errors += 1

        except Exception as e:
            await update_product_status(product["id"], "error")
            print(f"💥 오류: {e}")
            errors += 1

        # API 부하 방지
        await asyncio.sleep(2)

    print(f"\n{'='*50}")
    print(f"  처리 완료: 통과 {passed} / 보류 {held} / 제외 {excluded} / 오류 {errors}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
