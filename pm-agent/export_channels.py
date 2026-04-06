#!/usr/bin/env python3
"""
채널별 등록용 CSV 내보내기
===========================
승인된 상품 데이터를 네이버 스마트스토어 / 쿠팡 대량 등록 형식으로 변환

사용법:
  python export_channels.py --platform smartstore       # 네이버 스마트스토어 CSV
  python export_channels.py --platform coupang           # 쿠팡 CSV
  python export_channels.py --platform all               # 둘 다 생성
  python export_channels.py --input batch_result.json    # 배치 결과에서 직접 변환
"""

import os
import sys
import csv
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# .env 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

logger = logging.getLogger(__name__)


def get_approved_items() -> List[Dict]:
    """승인 큐에서 approved 상품 가져오기"""
    from approval_queue import ApprovalQueueManager
    aq = ApprovalQueueManager()
    items = aq.list_items("approved")
    return items


def load_from_json(filepath: str) -> List[Dict]:
    """배치 결과 JSON에서 통과 상품 로드"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = data.get("results", data if isinstance(data, list) else [])
    return [r for r in results if r.get("final_status") == "통과" or r.get("sourcing_decision") == "통과"]


def _round_price(price: float) -> int:
    """가격을 100원 단위로 반올림 (이커머스 관행)"""
    return int(round(price / 100) * 100)


def export_smartstore(items: List[Dict], output_path: str):
    """
    네이버 스마트스토어 대량등록 CSV 형식
    참고: 스마트스토어 셀러센터 > 상품관리 > 대량등록 양식
    """
    fields = [
        "상품명",
        "판매가",
        "재고수량",
        "카테고리",
        "상품상태",
        "A/S 전화번호",
        "A/S 안내",
        "상품 주요정보",
        "상세설명",
        "원산지",
        "배송비 종류",
        "기본 배송비",
        "택배사",
        "반품배송비",
        "교환배송비",
        "판매자 특이사항",
        "SEO 태그",
    ]

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for item in items:
            # 데이터 추출 (배치 결과 or 승인 큐)
            title = (
                item.get("registration_title")
                or item.get("registration_title_ko")
                or item.get("title", "상품명 미정")
            )
            price = item.get("final_price_krw", 0)
            if isinstance(price, dict):
                price = price.get("final_price_krw", 0)
            price = _round_price(float(price)) if price else 19900

            desc = (
                item.get("content_main")
                or item.get("short_description_ko")
                or ""
            )
            seo = item.get("seo_title", "")
            category = item.get("category", "")

            # 50자 제한 (스마트스토어)
            if len(title) > 50:
                title = title[:47] + "..."

            writer.writerow({
                "상품명": title,
                "판매가": price,
                "재고수량": 999,
                "카테고리": category,
                "상품상태": "새상품",
                "A/S 전화번호": "",
                "A/S 안내": "구매 후 7일 이내 교환/반품 가능",
                "상품 주요정보": desc[:200] if desc else "",
                "상세설명": desc,
                "원산지": "중국",
                "배송비 종류": "무료",
                "기본 배송비": 0,
                "택배사": "CJ대한통운",
                "반품배송비": 3000,
                "교환배송비": 6000,
                "판매자 특이사항": "해외 소싱 상품 / 배송 3~7일 소요",
                "SEO 태그": seo,
            })

    print(f"  ✅ 스마트스토어 CSV: {output_path} ({len(items)}개 상품)")


def export_coupang(items: List[Dict], output_path: str):
    """
    쿠팡 대량등록 CSV 형식
    참고: 쿠팡 WING > 상품관리 > 대량등록
    """
    fields = [
        "노출상품명",
        "등록상품명",
        "판매가격",
        "재고수량",
        "배송방법",
        "배송비",
        "출고지",
        "반품/교환지",
        "브랜드",
        "제조사",
        "원산지",
        "상품상세설명(텍스트)",
        "A/S 전화번호",
        "검색태그",
        "인증정보",
        "최대구매수량",
    ]

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for item in items:
            title = (
                item.get("registration_title")
                or item.get("registration_title_ko")
                or item.get("title", "상품명 미정")
            )
            price = item.get("final_price_krw", 0)
            if isinstance(price, dict):
                price = price.get("final_price_krw", 0)
            price = _round_price(float(price)) if price else 19900

            desc = (
                item.get("content_main")
                or item.get("short_description_ko")
                or ""
            )
            seo = item.get("seo_title", "")

            # 쿠팡 100자 제한
            display_title = title
            if len(display_title) > 100:
                display_title = display_title[:97] + "..."

            # [오늘출발] 태그 추가 (쿠팡 노출 우선)
            if not display_title.startswith("["):
                display_title = f"[오늘출발] {display_title}"
                if len(display_title) > 100:
                    display_title = display_title[:97] + "..."

            writer.writerow({
                "노출상품명": display_title,
                "등록상품명": title,
                "판매가격": price,
                "재고수량": 999,
                "배송방법": "로켓배송 외",
                "배송비": 0,
                "출고지": "",
                "반품/교환지": "",
                "브랜드": "Fortimove",
                "제조사": "",
                "원산지": "중국",
                "상품상세설명(텍스트)": desc,
                "A/S 전화번호": "",
                "검색태그": seo,
                "인증정보": "",
                "최대구매수량": 10,
            })

    print(f"  ✅ 쿠팡 CSV: {output_path} ({len(items)}개 상품)")


def main():
    parser = argparse.ArgumentParser(description="채널별 등록용 CSV 내보내기")
    parser.add_argument("--platform", "-p", type=str, default="all",
                       choices=["smartstore", "coupang", "all"],
                       help="출력 플랫폼 (기본: all)")
    parser.add_argument("--input", "-i", type=str, default=None,
                       help="배치 결과 JSON 파일 (없으면 승인 큐에서 가져옴)")
    parser.add_argument("--output-dir", "-d", type=str, default="exports",
                       help="출력 디렉토리 (기본: exports/)")
    args = parser.parse_args()

    # 데이터 로드
    if args.input:
        print(f"  📂 배치 결과 로드: {args.input}")
        items = load_from_json(args.input)
    else:
        print(f"  📂 승인 큐에서 approved 상품 로드")
        items = get_approved_items()

    if not items:
        print("  ℹ️  내보낼 상품이 없습니다")
        return

    print(f"  📊 {len(items)}개 상품 발견\n")

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.platform in ("smartstore", "all"):
        export_smartstore(items, f"{args.output_dir}/smartstore_{timestamp}.csv")

    if args.platform in ("coupang", "all"):
        export_coupang(items, f"{args.output_dir}/coupang_{timestamp}.csv")

    print(f"\n  📁 출력 디렉토리: {args.output_dir}/")


if __name__ == "__main__":
    main()
