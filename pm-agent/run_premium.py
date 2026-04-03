#!/usr/bin/env python3
"""
Fortimove 프리미엄 파이프라인
================================
1개 상품 → 바로 판매 가능한 수준의 전체 결과물

출력물:
  - 소싱 리스크 판정 + 벤더 질문
  - 11변수 원가/마진 분석
  - SEO 최적화 상품명 (네이버/쿠팡)
  - 초퀄리티 상세페이지 (네이버 8섹션 + 쿠팡)
  - 네이버 쇼핑 검색광고 키워드 + 입찰 전략
  - 경쟁 차별화 분석
  - 이미지 배치 가이드

사용법:
  python run_premium.py --title "콜라겐 펩타이드 분말" --price 52 --category wellness
  python run_premium.py --title "스테인리스 텀블러" --price 28 --target "직장인 30대"
  python run_premium.py --title "비타민C" --price 45 --features "고함량 1000mg" "60정" "GMP 인증"
"""

import os
import sys
import json
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


def run_premium(args):
    from agent_framework import AgentRegistry
    from real_agents import register_real_agents
    from product_registration_agent import register_product_registration_agent
    from premium_detail_page import PremiumDetailPageGenerator

    registry = register_real_agents()
    register_product_registration_agent(registry)

    from country_config import get_country

    results = {}
    start_time = datetime.now()
    country_code = getattr(args, 'country', 'CN') or 'CN'
    country = get_country(country_code)
    country_name = country.name_ko if country else "중국"
    currency = country.currency if country else "CNY"

    print(f"\n{'='*60}")
    print(f"  FORTIMOVE PREMIUM PIPELINE")
    print(f"  상품: {args.title}")
    print(f"  매입가: {args.price} {currency}  |  소싱국: {country_name}  |  카테고리: {args.category}")
    print(f"{'='*60}\n")

    # ── 1. 소싱 리스크 ──
    print(f"[1/4] 소싱 리스크 분석 ({country_name})...", end=" ", flush=True)
    sourcing = registry.get("sourcing")
    if sourcing:
        sr = sourcing.execute({
            "source_url": args.url or "",
            "source_title": args.title,
            "source_description": args.desc or "",
            "source_price_cny": args.price,
            "market": "korea"
        })
        if sr.is_success():
            results["sourcing"] = sr.output
            d = sr.output.get("sourcing_decision", "?")
            flags = sr.output.get("risk_flags", [])
            print(f"{'✅ ' + d if d == '통과' else '⚠️ ' + d} {('(' + ', '.join(flags) + ')') if flags else ''}")
            if d == "제외":
                print(f"\n  ❌ 소싱 제외 — 이 상품은 등록 불가합니다.")
                _save_and_exit(results, args)
                return
        else:
            print(f"❌ {sr.error}")
    print()

    # ── 2. 마진 분석 ──
    print(f"[2/4] 11변수 마진 분석 ({currency})...", end=" ", flush=True)
    pricing = registry.get("pricing")
    if pricing:
        pr = pricing.execute({
            "source_price_cny": args.price,
            "source_country": country_code,
            "category": args.category,
            "weight_kg": args.weight,
            "product_name": args.title,
            "platform_fee_rate": args.platform_fee,
        })
        if pr.is_success():
            results["pricing"] = pr.output
            fp = pr.output.get("final_price", 0)
            mr = pr.output.get("margin_rate", 0)
            decision = pr.output.get("pricing_decision", "?")
            print(f"₩{fp:,.0f} | 순마진 {mr:.1f}% | {decision}")
        else:
            print(f"❌ {pr.error}")
    print()

    price_krw = int(results.get("pricing", {}).get("final_price", 19900))
    margin_rate = results.get("pricing", {}).get("margin_rate", 0)

    # ── 3. SEO 상품 등록 초안 ──
    print("[3/4] SEO 상품 등록 초안...", end=" ", flush=True)
    reg = registry.get("product_registration")
    if reg:
        rr = reg.execute({
            "source_title": args.title,
            "source_description": args.desc or "",
            "market": "korea"
        })
        if rr.is_success():
            results["registration"] = rr.output
            title_ko = rr.output.get("registration_title_ko", "?")
            print(f"✅ {title_ko[:50]}")
        else:
            print(f"❌ {rr.error}")
    print()

    # ── 등록 가치 점수 ──
    from product_score import calculate_product_score, print_score
    score = calculate_product_score(
        margin_rate=margin_rate,
        risk_flags=results.get("sourcing", {}).get("risk_flags", []),
        sourcing_decision=results.get("sourcing", {}).get("sourcing_decision", "통과"),
        price_krw=price_krw,
        weight_kg=args.weight,
        category=args.category,
    )
    results["score"] = {"total": score.total, "grade": score.grade, "decision": score.decision, "breakdown": score.breakdown}
    print_score(score, args.title)

    if score.grade == "D":
        print(f"\n  ❌ D등급 — 1,000개 한도 낭비입니다. 등록하지 마세요.")
        _save_and_exit(results, args)
        return

    print()

    # ── 4. 초퀄리티 상세페이지 + 광고 전략 ──
    print("[4/4] 초퀄리티 상세페이지 + 광고 전략 생성 중...")
    print("      (네이버 8섹션 + 쿠팡 + SEO + 검색광고 + 경쟁분석)")
    print("      ⏳ 약 30~60초 소요...\n")

    gen = PremiumDetailPageGenerator()
    detail = gen.generate(
        title=args.title,
        price_krw=price_krw,
        category=args.category,
        description=args.desc or "",
        target_customer=args.target or "",
        key_features=args.features or [],
        competitors=args.competitors or [],
        margin_rate=margin_rate,
        source_country=country_code,
    )
    results["detail_page"] = detail

    if "error" not in detail:
        titles = detail.get("product_titles", {})
        hooks = detail.get("hook_copies", [])
        sections = detail.get("naver_detail_page", {}).get("sections", [])
        ad = detail.get("ad_strategy", {})
        seo = detail.get("seo_strategy", {})

        print(f"  ✅ 상품명 (스마트스토어): {titles.get('smartstore', '')}")
        print(f"  ✅ 상품명 (쿠팡): {titles.get('coupang', '')[:60]}")
        print(f"  ✅ 후크 카피: {len(hooks)}개")
        print(f"  ✅ 상세페이지 섹션: {len(sections)}개")
        print(f"  ✅ 광고 키워드: {len(ad.get('keywords', []))}개")
        print(f"  ✅ SEO 태그: {len(seo.get('shopping_tags', []))}개")
        if detail.get("compliance_warnings"):
            print(f"  ⚠️  컴플라이언스 자동 치환: {len(detail['compliance_warnings'])}건")
    else:
        print(f"  ❌ 상세페이지 생성 실패: {detail.get('error')}")

    elapsed = (datetime.now() - start_time).total_seconds()

    # ── 결과 저장 ──
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = f"reports/premium_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "input": {"title": args.title, "price_cny": args.price, "category": args.category},
            "results": results
        }, f, ensure_ascii=False, indent=2)

    # 상세페이지 텍스트 파일 (복사 붙여넣기용)
    if "error" not in detail:
        naver_path = f"reports/premium_{timestamp}_naver.txt"
        with open(naver_path, 'w', encoding='utf-8') as f:
            f.write(gen.render_naver_text(detail))

        ad_path = f"reports/premium_{timestamp}_ad_strategy.txt"
        with open(ad_path, 'w', encoding='utf-8') as f:
            f.write(gen.render_ad_strategy(detail))

        # ── 상세페이지 이미지 자동 생성 ──
        img_dir = f"reports/premium_{timestamp}_images"
        detail_with_pricing = dict(detail)
        detail_with_pricing["pricing"] = results.get("pricing", {})
        generated_images = []

        # Gemini 우선 시도
        if os.getenv("GEMINI_API_KEY"):
            try:
                from gemini_image import generate_full_detail_page
                print("  🖼️ Gemini로 상세페이지 이미지 생성 중...")
                generated_images = generate_full_detail_page(detail_with_pricing, img_dir)
                print(f"  🖼️ Gemini 이미지: {len(generated_images)}장 생성")
            except Exception as e:
                logger.warning(f"Gemini 이미지 생성 실패: {e}")
                generated_images = []

        # Gemini 실패/미설정 시 Pillow fallback
        if not generated_images:
            try:
                from detail_image_generator import generate_detail_page_images
                generated_images = generate_detail_page_images(detail_with_pricing, img_dir)
                print(f"  🖼️ 상세페이지 이미지 (Pillow): {len(generated_images)}장 생성")
            except Exception as e:
                logger.warning(f"이미지 생성 실패: {e}")

        print(f"\n{'='*60}")
        print(f"  PREMIUM PIPELINE 완료 ({elapsed:.0f}초)")
        print(f"{'='*60}")
        print(f"  📁 전체 결과: {json_path}")
        print(f"  📝 네이버 카피: {naver_path}")
        print(f"  📊 광고 전략: {ad_path}")
        if generated_images:
            print(f"  🖼️ 상세페이지 이미지: {img_dir}/ ({len(generated_images)}장)")
        print(f"{'='*60}\n")

        # 핵심 요약
        print(f"▶ 판매가: ₩{price_krw:,}  |  순마진: {margin_rate:.1f}%  |  손익분기: {results.get('pricing', {}).get('breakeven_qty', '?')}개")
        print(f"▶ 일 광고예산: ₩{ad.get('daily_budget_krw', 0):,}  |  입찰가: ₩{'-'.join(str(x) for x in ad.get('bid_range_krw', [0,0]))}")
        print(f"▶ 메인 키워드: {', '.join(seo.get('main_keywords', []))}")
        edge = detail.get("competitive_edge", {})
        if edge:
            print(f"▶ 포지셔닝: {edge.get('price_positioning', '')}")
    else:
        print(f"\n  결과: {json_path}")


def _save_and_exit(results, args):
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"reports/premium_{timestamp}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)
    print(f"  📁 {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Fortimove 프리미엄 파이프라인 — 1개 상품 초퀄리티 분석",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 중국 소싱 (기본)
  python run_premium.py --title "콜라겐 펩타이드 분말 100g" --price 52 --category wellness

  # 미국 소싱 (iHerb 등)
  python run_premium.py --title "Optimum Nutrition Gold Standard Whey 5lbs" --price 65 \\
    --country US --category supplement \\
    --features "FDA 등록 시설" "GMP 인증" "글로벌 1위 프로틴"

  # 일본 소싱 (라쿠텐 등)
  python run_premium.py --title "資生堂 コラーゲンパウダー 126g" --price 3500 \\
    --country JP --category beauty \\
    --target "피부 탄력이 신경 쓰이는 30대 여성"

  # 경쟁사 지정
  python run_premium.py --title "비타민C 1000mg" --price 45 --country US \\
    --competitors "닥터린 비타민C" "종근당 비타민C"
        """
    )
    parser.add_argument("--title", required=True, help="상품명 (중국어/영어/일본어)")
    parser.add_argument("--price", type=float, required=True, help="매입가 (소싱국 통화)")
    parser.add_argument("--category", default="general", help="카테고리 (wellness/supplement/beauty/general)")
    parser.add_argument("--country", default="CN", choices=["CN", "US", "JP", "VN"], help="소싱 국가 (CN/US/JP/VN)")
    parser.add_argument("--desc", default=None, help="상품 설명")
    parser.add_argument("--target", default=None, help="타겟 고객 (예: '30대 직장인 여성')")
    parser.add_argument("--features", nargs="+", default=None, help="주요 특징 (여러 개)")
    parser.add_argument("--competitors", nargs="+", default=None, help="경쟁 상품명 (여러 개)")
    parser.add_argument("--url", default=None, help="소싱 플랫폼 URL (참조용)")
    parser.add_argument("--weight", type=float, default=0.5, help="무게 (kg)")
    parser.add_argument("--platform-fee", type=float, default=None, help="플랫폼 수수료율 (예: 0.055)")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY 환경변수가 필요합니다")
        sys.exit(1)

    run_premium(args)


if __name__ == "__main__":
    main()
