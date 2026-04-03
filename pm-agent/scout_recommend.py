#!/usr/bin/env python3
"""
Daily Scout → 프리미엄 파이프라인 자동 추천
=============================================
Scout가 수집한 상품 중 등록 가치가 높은 상품을 자동 선별하여
run_premium.py 실행 명령어를 생성

사용법:
  python scout_recommend.py                    # 오늘 수집 상품 중 추천
  python scout_recommend.py --min-score 80     # 트렌드 80점 이상만
  python scout_recommend.py --top 3            # 상위 3개만
  python scout_recommend.py --run              # 추천 상품을 바로 run_premium.py로 실행
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, date
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

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def fetch_scout_products(min_score: int = 0, limit: int = 50) -> List[Dict]:
    """Scout DB에서 유망 상품 조회"""
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

    rows = await conn.fetch("""
        SELECT id, product_name, brand, price, category, trend_score,
               korea_demand, risk_status, url, region, source, date
        FROM wellness_products
        WHERE workflow_status = 'pending'
          AND trend_score >= $1
        ORDER BY trend_score DESC
        LIMIT $2
    """, min_score, limit)

    await conn.close()
    return [dict(r) for r in rows]


def score_for_premium(product: Dict) -> Dict:
    """프리미엄 파이프라인 적합도 점수 계산"""
    from product_score import calculate_product_score
    import re

    trend = product.get("trend_score", 0) or 0
    price_str = str(product.get("price", "0"))
    numbers = re.findall(r'[\d.]+', price_str)
    price_cny = float(numbers[0]) if numbers else 0

    # 대략적 판매가 추정 (CNY × 195 × 1.4)
    estimated_krw = price_cny * 195 * 1.4 if price_cny > 0 else 20000

    # 카테고리 매핑
    cat = (product.get("category", "") or "").lower()
    category_map = {
        "영양제": "supplement", "보충제": "supplement", "단백질": "supplement",
        "프로틴": "supplement", "비타민": "supplement",
        "건강": "wellness", "면역력": "wellness", "장 건강": "wellness",
        "수면": "wellness", "회복": "wellness", "기능식품": "wellness",
        "피트니스": "fitness", "운동": "fitness",
    }
    mapped_cat = "general"
    for k, v in category_map.items():
        if k in cat:
            mapped_cat = v
            break

    # 재구매 가능성 (소모품 = True)
    consumable_keywords = ["분말", "정", "캡슐", "보충제", "비타민", "프로틴", "콜라겐"]
    name = product.get("product_name", "")
    reorder = any(kw in name for kw in consumable_keywords)

    score = calculate_product_score(
        margin_rate=30,  # 추정 (아직 실제 마진 계산 전)
        risk_flags=[],
        sourcing_decision="통과" if product.get("risk_status") != "보류" else "보류",
        trend_score=trend,
        price_krw=estimated_krw,
        weight_kg=0.3,
        category=mapped_cat,
        reorder_potential=reorder,
    )

    return {
        "product": product,
        "score": score,
        "estimated_price_cny": price_cny,
        "mapped_category": mapped_cat,
    }


def generate_premium_command(item: Dict) -> str:
    """run_premium.py 실행 명령어 생성"""
    product = item["product"]
    name = product.get("product_name", "").replace('"', '\\"')
    price = item["estimated_price_cny"]
    cat = item["mapped_category"]
    url = product.get("url", "")

    cmd = f'python run_premium.py --title "{name}" --price {price} --category {cat}'
    if url:
        cmd += f' --url "{url}"'
    return cmd


async def main():
    parser = argparse.ArgumentParser(description="Scout → 프리미엄 파이프라인 추천")
    parser.add_argument("--min-score", type=int, default=60, help="최소 트렌드 점수 (기본: 60)")
    parser.add_argument("--top", type=int, default=5, help="상위 N개 추천 (기본: 5)")
    parser.add_argument("--run", action="store_true", help="추천 1위 상품을 바로 run_premium.py 실행")
    args = parser.parse_args()

    print(f"\n📡 Scout DB 조회 중 (트렌드 {args.min_score}점 이상)...")
    products = await fetch_scout_products(min_score=args.min_score, limit=50)

    if not products:
        print("  ℹ️  조건에 맞는 상품이 없습니다")
        return

    print(f"  📊 {len(products)}개 상품 발견, 등록 가치 점수 계산 중...\n")

    # 점수 계산 + 정렬
    scored = [score_for_premium(p) for p in products]
    scored.sort(key=lambda x: x["score"].total, reverse=True)
    top = scored[:args.top]

    # 결과 출력
    print(f"{'#':>2} {'점수':>5} {'등급':<3} {'트렌드':>5} {'상품명':<40} {'가격':>8} {'카테고리':<10}")
    print("-" * 80)
    for i, item in enumerate(top, 1):
        p = item["product"]
        s = item["score"]
        name = (p.get("product_name", "") or "")[:38]
        trend = p.get("trend_score", 0) or 0
        price = p.get("price", "?")
        cat = item["mapped_category"]
        marker = "★" if s.grade in ("A", "B") else " "
        print(f"{marker}{i:>1} {s.total:>5.0f} [{s.grade}] {trend:>5} {name:<40} {str(price):>8} {cat:<10}")

    # A/B 등급 상품에 대한 실행 명령어
    recommended = [item for item in top if item["score"].grade in ("A", "B")]

    if recommended:
        print(f"\n{'='*60}")
        print(f"  🎯 프리미엄 파이프라인 추천 ({len(recommended)}개 상품)")
        print(f"{'='*60}\n")

        for i, item in enumerate(recommended, 1):
            p = item["product"]
            s = item["score"]
            print(f"  [{i}] {p.get('product_name', '')[:50]}")
            print(f"      등급: {s.grade} ({s.total:.0f}점) | 판정: {s.decision}")
            print(f"      실행: {generate_premium_command(item)}")
            print()

        if args.run:
            # 1위 상품 바로 실행
            best = recommended[0]
            cmd = generate_premium_command(best)
            print(f"\n  🚀 1위 상품 자동 실행 중...\n")
            print(f"  $ {cmd}\n")
            os.system(cmd)
    else:
        print(f"\n  ℹ️  A/B 등급 상품이 없습니다. 트렌드 점수 기준을 낮춰보세요.")


if __name__ == "__main__":
    asyncio.run(main())
