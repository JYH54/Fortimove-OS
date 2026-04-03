#!/usr/bin/env python3
"""
Fortimove Fast-Track CLI
========================
타오바오/1688 URL 하나로 소싱→마진→등록→콘텐츠 전체 파이프라인 실행

사용법:
  python run_fast_track.py --url "https://item.taobao.com/..." --price 35 --title "상품명"
  python run_fast_track.py --url "https://detail.1688.com/..." --price 28.5 --weight 0.3
  python run_fast_track.py --quick --url "..." --price 35     # 소싱+마진만 빠르게
  python run_fast_track.py --content --name "상품명" --desc "설명"  # 콘텐츠만

필수 환경변수:
  ANTHROPIC_API_KEY=sk-ant-api03-...
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


def run_full_pipeline(args):
    """소싱 → 마진 → 등록 → 콘텐츠 전체 파이프라인"""
    from agent_framework import AgentRegistry
    from real_agents import register_real_agents
    from cs_agent import register_cs_agent
    from product_registration_agent import register_product_registration_agent
    from sourcing_agent import SourcingAgent
    from pricing_agent import PricingAgent
    from content_agent import ContentAgent

    # 에이전트 등록
    registry = register_real_agents()
    register_cs_agent(registry)
    register_product_registration_agent(registry)

    print("\n" + "="*60)
    print("  FORTIMOVE FAST-TRACK PIPELINE")
    print("="*60)
    print(f"  URL:   {args.url}")
    print(f"  가격:  ¥{args.price}")
    print(f"  제목:  {args.title or '(URL에서 추출)'}")
    print(f"  무게:  {args.weight}kg")
    print("="*60 + "\n")

    results = {}
    start_time = datetime.now()

    # ── STEP 1: 소싱 리스크 분석 ──
    print("[1/4] 소싱 리스크 분석 중...")
    try:
        sourcing = registry.get("sourcing")
        sourcing_input = {
            "source_url": args.url,
            "source_title": args.title or "",
            "source_price_cny": args.price,
            "market": "korea"
        }
        sourcing_result = sourcing.execute(sourcing_input)

        if sourcing_result.is_success():
            results["sourcing"] = sourcing_result.output
            decision = sourcing_result.output.get("sourcing_decision", "?")
            flags = sourcing_result.output.get("risk_flags", [])
            print(f"  ✅ 판정: {decision}")
            if flags:
                print(f"  ⚠️  리스크: {', '.join(flags)}")
            else:
                print(f"  ✅ 리스크 없음")

            # 제외 판정이면 중단
            if decision == "제외":
                print(f"\n  ❌ 소싱 제외 판정 — 파이프라인 중단")
                print(f"  사유: {sourcing_result.output.get('risk_details', {})}")
                return results
        else:
            print(f"  ❌ 소싱 분석 실패: {sourcing_result.error}")
            results["sourcing"] = {"error": sourcing_result.error}
    except Exception as e:
        print(f"  ❌ 소싱 에이전트 오류: {e}")
        results["sourcing"] = {"error": str(e)}

    # ── STEP 2: 마진 계산 ──
    print("\n[2/4] 마진 계산 중...")
    try:
        pricing = registry.get("pricing")
        if pricing is None:
            # PricingAgent가 registry에 없으면 직접 생성
            pricing = PricingAgent()

        pricing_input = {
            "source_price_cny": args.price,
            "shipping_cny": args.shipping,
            "category": args.category or "general",
            "weight_kg": args.weight
        }
        pricing_result = pricing.execute(pricing_input)

        if pricing_result.is_success():
            results["pricing"] = pricing_result.output
            final_price = pricing_result.output.get("final_price_krw", "?")
            margin = pricing_result.output.get("margin_rate", "?")
            print(f"  ✅ 판매가: ₩{final_price:,}" if isinstance(final_price, (int, float)) else f"  ✅ 판매가: {final_price}")
            print(f"  ✅ 마진율: {margin}%")
        else:
            print(f"  ❌ 마진 계산 실패: {pricing_result.error}")
            results["pricing"] = {"error": pricing_result.error}
    except Exception as e:
        print(f"  ❌ 마진 에이전트 오류: {e}")
        results["pricing"] = {"error": str(e)}

    if args.quick:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n{'='*60}")
        print(f"  빠른 검증 완료 ({elapsed:.1f}초)")
        print(f"{'='*60}\n")
        _save_results(results, args)
        return results

    # ── STEP 3: 상품 등록 초안 ──
    print("\n[3/4] 상품 등록 초안 생성 중...")
    try:
        reg_agent = registry.get("product_registration")
        reg_input = {
            "source_title": args.title or results.get("sourcing", {}).get("extracted_info", {}).get("title", "상품"),
            "source_description": args.desc or "",
            "market": "korea"
        }
        reg_result = reg_agent.execute(reg_input)

        if reg_result.is_success():
            results["registration"] = reg_result.output
            title = reg_result.output.get("registration_title_ko", "?")
            status = reg_result.output.get("registration_status", "?")
            print(f"  ✅ 등록 제목: {title}")
            print(f"  ✅ 상태: {status}")
        else:
            print(f"  ❌ 등록 초안 실패: {reg_result.error}")
            results["registration"] = {"error": reg_result.error}
    except Exception as e:
        print(f"  ❌ 등록 에이전트 오류: {e}")
        results["registration"] = {"error": str(e)}

    # ── STEP 4: 콘텐츠 생성 ──
    print("\n[4/4] 콘텐츠 생성 중...")
    try:
        content = registry.get("content")
        product_name = results.get("registration", {}).get("registration_title_ko", args.title or "상품")
        content_input = {
            "product_name": product_name,
            "product_description": results.get("registration", {}).get("short_description_ko", ""),
            "content_type": "product_page",
            "compliance_mode": True
        }
        content_result = content.execute(content_input)

        if content_result.is_success():
            results["content"] = content_result.output
            compliance = content_result.output.get("compliance_status", "?")
            print(f"  ✅ 콘텐츠 생성 완료")
            print(f"  ✅ 컴플라이언스: {compliance}")
        else:
            print(f"  ❌ 콘텐츠 생성 실패: {content_result.error}")
            results["content"] = {"error": content_result.error}
    except Exception as e:
        print(f"  ❌ 콘텐츠 에이전트 오류: {e}")
        results["content"] = {"error": str(e)}

    # ── STEP 5 (선택): 상세페이지 전략 ──
    if getattr(args, 'detail', False):
        print("\n[5/5] 상세페이지 전략 생성 중...")
        try:
            from detail_page_strategist import DetailPageStrategist
            strategist = DetailPageStrategist()

            product_summary = {
                "positioning_summary": results.get("content", {}).get("main_content", "")[:300],
                "usp_points": results.get("content", {}).get("variations", [])[:3],
                "target_customer": "건강/웰니스에 관심 있는 30~40대",
                "usage_scenarios": [],
                "differentiation_points": []
            }
            source_data = {
                "source_title": args.title or "상품",
                "source_url": args.url,
                "source_price_cny": args.price,
                "category": args.category or "general",
                "weight_kg": args.weight
            }

            detail_result = strategist.generate_detail_page_content(
                product_summary, source_data, args.category or "general"
            )
            results["detail_page"] = detail_result
            print(f"  ✅ 상세페이지 생성 완료")
            print(f"  ✅ 네이버 본문: {len(detail_result.get('naver_body', ''))}자")
            print(f"  ✅ 쿠팡 본문: {len(detail_result.get('coupang_body', ''))}자")
            print(f"  ✅ 후크 카피: {len(detail_result.get('hook_copies', []))}개")
            print(f"  ✅ FAQ: {len(detail_result.get('faq', []))}개")
            if detail_result.get("compliance_warnings"):
                print(f"  ⚠️  컴플라이언스 경고: {len(detail_result['compliance_warnings'])}건")
        except Exception as e:
            print(f"  ❌ 상세페이지 오류: {e}")
            results["detail_page"] = {"error": str(e)}

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"  FAST-TRACK 완료 ({elapsed:.1f}초)")
    print(f"{'='*60}\n")

    _save_results(results, args)
    _print_summary(results)
    return results


def run_content_only(args):
    """콘텐츠만 생성"""
    from content_agent import ContentAgent

    print("\n[콘텐츠 생성 모드]")
    content = ContentAgent()
    content_input = {
        "product_name": args.name,
        "product_description": args.desc or "",
        "content_type": args.content_type,
        "target_platform": args.platform,
        "compliance_mode": True
    }
    result = content.execute(content_input)

    if result.is_success():
        print(f"\n✅ 콘텐츠 생성 완료\n")
        print(result.output.get("main_content", ""))
        if result.output.get("variations"):
            print(f"\n--- 대안 버전 ---")
            for i, v in enumerate(result.output["variations"], 1):
                print(f"\n[버전 {i}] {v}")
    else:
        print(f"❌ 실패: {result.error}")


def _save_results(results, args):
    """결과를 JSON 파일로 저장"""
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reports/fast_track_{timestamp}.json"

    output = {
        "timestamp": datetime.now().isoformat(),
        "input": {
            "url": getattr(args, 'url', None),
            "price_cny": getattr(args, 'price', None),
            "title": getattr(args, 'title', None),
        },
        "results": results
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  📁 결과 저장: {filename}")


def _print_summary(results):
    """최종 요약 출력"""
    print("\n┌─────────────────────────────────────────┐")
    print("│          FAST-TRACK 결과 요약            │")
    print("├──────────┬──────────────────────────────┤")

    # 소싱
    s = results.get("sourcing", {})
    decision = s.get("sourcing_decision", "오류")
    print(f"│ 소싱     │ {decision:<28} │")

    # 마진
    p = results.get("pricing", {})
    price = p.get("final_price_krw", "?")
    margin = p.get("margin_rate", "?")
    if isinstance(price, (int, float)):
        print(f"│ 판매가   │ ₩{price:>25,} │")
    print(f"│ 마진율   │ {str(margin) + '%':<28} │")

    # 등록
    r = results.get("registration", {})
    status = r.get("registration_status", "?")
    print(f"│ 등록상태 │ {status:<28} │")

    # 콘텐츠
    c = results.get("content", {})
    comp = c.get("compliance_status", "?")
    print(f"│ 컴플라이 │ {comp:<28} │")

    print("└──────────┴──────────────────────────────┘")

    # 벤더 질문
    vendor_q = s.get("vendor_questions_ko", [])
    if vendor_q:
        print(f"\n📋 벤더 질문 (한국어):")
        for i, q in enumerate(vendor_q, 1):
            print(f"  {i}. {q}")

    vendor_zh = s.get("vendor_questions_zh", [])
    if vendor_zh:
        print(f"\n📋 벤더 질문 (중국어):")
        for i, q in enumerate(vendor_zh, 1):
            print(f"  {i}. {q}")


def main():
    parser = argparse.ArgumentParser(
        description="Fortimove Fast-Track CLI — 상품 소싱→등록 자동화",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 전체 파이프라인 (타오바오에서 제목/가격 복사 → 붙여넣기)
  python run_fast_track.py --title "无线充电牙刷 声波电动牙刷" --price 35 --weight 0.3

  # URL도 함께 기록 (참조용, 크롤링하지 않음)
  python run_fast_track.py --title "不锈钢保温杯 500ml" --price 28.5 --url "https://item.taobao.com/item.htm?id=123"

  # 빠른 검증 (소싱+마진만)
  python run_fast_track.py --quick --title "콜라겐 펩타이드 분말" --price 52 --category wellness

  # 상세페이지까지 생성
  python run_fast_track.py --detail --title "프리미엄 비타민C" --price 45 --category supplement

  # 콘텐츠만 생성
  python run_fast_track.py --content --name "프리미엄 텀블러" --desc "스테인리스 500ml" --platform coupang

참고: 타오바오/1688은 크롤링이 차단되므로, 브라우저에서 상품 제목/가격을 직접 복사하여 입력합니다.
        """
    )

    parser.add_argument("--url", type=str, help="타오바오/1688 상품 URL (참조용, 크롤링 안 함)")
    parser.add_argument("--price", type=float, help="매입가 (위안, CNY)")
    parser.add_argument("--title", type=str, default=None, help="상품 제목 (필수 — 리스크 분석의 핵심 입력)")
    parser.add_argument("--desc", type=str, default=None, help="상품 설명")
    parser.add_argument("--weight", type=float, default=0.5, help="무게 (kg, 기본: 0.5)")
    parser.add_argument("--shipping", type=float, default=0.0, help="배송비 (CNY, 기본: 0)")
    parser.add_argument("--category", type=str, default=None, help="카테고리 (wellness/beauty/general 등)")
    parser.add_argument("--quick", action="store_true", help="소싱+마진만 빠르게 검증")
    parser.add_argument("--detail", action="store_true", help="상세페이지 전략까지 생성 (네이버/쿠팡 본문)")
    parser.add_argument("--content", action="store_true", help="콘텐츠만 생성 모드")
    parser.add_argument("--name", type=str, help="상품명 (--content 모드용)")
    parser.add_argument("--platform", type=str, default="smartstore", help="타겟 플랫폼 (smartstore/coupang/instagram)")
    parser.add_argument("--content-type", type=str, default="product_page", help="콘텐츠 유형 (product_page/sns/ad)")

    args = parser.parse_args()

    # 환경변수 체크
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   export ANTHROPIC_API_KEY=sk-ant-api03-...")
        sys.exit(1)

    if args.content:
        if not args.name:
            parser.error("--content 모드에서는 --name이 필수입니다")
        run_content_only(args)
    else:
        if args.price is None or not args.title:
            parser.error("--price와 --title은 필수입니다 (타오바오에서 직접 복사)")
        if not args.url:
            args.url = ""  # URL은 참조용이므로 없어도 됨
        run_full_pipeline(args)


if __name__ == "__main__":
    main()
