#!/usr/bin/env python3
"""
Fortimove 배치 처리 CLI
========================
CSV/JSON 파일로 여러 상품을 한꺼번에 Fast-Track 처리

사용법:
  python run_batch.py products.csv                    # CSV 파일 배치 처리
  python run_batch.py products.json                   # JSON 파일 배치 처리
  python run_batch.py products.csv --quick             # 소싱+마진만 빠르게
  python run_batch.py products.csv --output result.csv # 결과 CSV 저장

CSV 형식 (필수: url, price):
  url,price,title,weight,category
  https://item.taobao.com/...,35,무선 칫솔,0.3,general
  https://detail.1688.com/...,28.5,텀블러,0.5,wellness

JSON 형식:
  [{"url": "...", "price": 35, "title": "...", "weight": 0.3}]
"""

import os
import sys
import csv
import json
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

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
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_products(filepath: str) -> List[Dict[str, Any]]:
    """CSV 또는 JSON에서 상품 목록 로드"""
    path = Path(filepath)
    if not path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {filepath}")
        sys.exit(1)

    if path.suffix.lower() == '.csv':
        products = []
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append({
                    "url": row.get("url", "").strip(),
                    "price": float(row.get("price", 0)),
                    "title": row.get("title", "").strip() or None,
                    "weight": float(row.get("weight", 0.5)),
                    "category": row.get("category", "general").strip(),
                    "shipping": float(row.get("shipping", 0)),
                })
        return products

    elif path.suffix.lower() == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return [data]

    else:
        print(f"❌ 지원하지 않는 파일 형식: {path.suffix} (csv 또는 json만 가능)")
        sys.exit(1)


def process_single(product: dict, idx: int, total: int, quick: bool = False) -> Dict[str, Any]:
    """단일 상품 처리"""
    from agent_framework import AgentRegistry
    from real_agents import register_real_agents
    from product_registration_agent import register_product_registration_agent

    registry = register_real_agents()
    register_product_registration_agent(registry)

    url = product.get("url", "")
    price = product.get("price", 0)
    title = product.get("title", "") or ""
    weight = product.get("weight", 0.5)
    category = product.get("category", "general")

    result = {
        "idx": idx,
        "url": url,
        "title": title,
        "price_cny": price,
        "category": category,
    }

    # 1. 소싱 리스크
    sourcing = registry.get("sourcing")
    if sourcing:
        try:
            sr = sourcing.execute({
                "source_url": url,
                "source_title": title,
                "source_price_cny": price,
                "market": "korea"
            })
            if sr.is_success():
                result["sourcing_decision"] = sr.output.get("sourcing_decision", "?")
                result["risk_flags"] = sr.output.get("risk_flags", [])
                result["vendor_questions_ko"] = sr.output.get("vendor_questions_ko", [])
                result["classification"] = sr.output.get("product_classification", "?")
            else:
                result["sourcing_decision"] = "오류"
                result["sourcing_error"] = sr.error
        except Exception as e:
            result["sourcing_decision"] = "오류"
            result["sourcing_error"] = str(e)

    # 제외 판정이면 스킵
    if result.get("sourcing_decision") == "제외":
        result["final_status"] = "제외"
        return result

    # 2. 마진 계산
    pricing = registry.get("pricing")
    if pricing:
        try:
            pr = pricing.execute({
                "source_price_cny": price,
                "category": category,
                "weight_kg": weight,
                "product_name": title,
            })
            if pr.is_success():
                result["final_price_krw"] = pr.output.get("final_price", 0)
                result["margin_rate"] = pr.output.get("margin_rate", 0)
                result["cost_breakdown"] = pr.output.get("cost_breakdown", {})
            else:
                result["pricing_error"] = pr.error
        except Exception as e:
            result["pricing_error"] = str(e)

    if quick:
        result["final_status"] = result.get("sourcing_decision", "?")
        return result

    # 3. 상품 등록 초안
    reg = registry.get("product_registration")
    if reg:
        try:
            rr = reg.execute({
                "source_title": title or "상품",
                "market": "korea"
            })
            if rr.is_success():
                result["registration_title"] = rr.output.get("registration_title_ko", "")
                result["registration_status"] = rr.output.get("registration_status", "?")
            else:
                result["registration_error"] = rr.error
        except Exception as e:
            result["registration_error"] = str(e)

    # 4. 콘텐츠
    content = registry.get("content")
    if content:
        try:
            cr = content.execute({
                "product_name": result.get("registration_title", title or "상품"),
                "content_type": "product_page",
                "compliance_mode": True
            })
            if cr.is_success():
                result["content_main"] = cr.output.get("main_content", "")[:200]
                result["compliance_status"] = cr.output.get("compliance_status", "?")
                result["seo_title"] = cr.output.get("seo_title", "")
            else:
                result["content_error"] = cr.error
        except Exception as e:
            result["content_error"] = str(e)

    result["final_status"] = result.get("sourcing_decision", "?")
    return result


def save_results_csv(results: List[Dict], output_path: str):
    """결과를 CSV로 저장"""
    if not results:
        return

    fields = [
        "idx", "url", "title", "price_cny", "category",
        "sourcing_decision", "risk_flags", "classification",
        "final_price_krw", "margin_rate",
        "registration_title", "registration_status",
        "compliance_status", "seo_title",
        "final_status"
    ]

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for r in results:
            row = dict(r)
            if "risk_flags" in row and isinstance(row["risk_flags"], list):
                row["risk_flags"] = "; ".join(row["risk_flags"])
            writer.writerow(row)

    print(f"  📁 CSV 저장: {output_path}")


def save_results_json(results: List[Dict], output_path: str):
    """결과를 JSON으로 저장"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "passed": len([r for r in results if r.get("final_status") == "통과"]),
            "held": len([r for r in results if r.get("final_status") == "보류"]),
            "excluded": len([r for r in results if r.get("final_status") == "제외"]),
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"  📁 JSON 저장: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Fortimove 배치 처리 — CSV/JSON으로 여러 상품 한꺼번에 처리",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_file", help="상품 목록 파일 (CSV 또는 JSON)")
    parser.add_argument("--quick", action="store_true", help="소싱+마진만 빠르게")
    parser.add_argument("--output", "-o", type=str, default=None, help="결과 파일 경로 (.csv 또는 .json)")
    parser.add_argument("--delay", type=float, default=2.0, help="상품 간 대기 시간 (초, 기본: 2)")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY 환경변수가 필요합니다")
        sys.exit(1)

    products = load_products(args.input_file)
    total = len(products)

    print(f"\n{'='*60}")
    print(f"  FORTIMOVE 배치 처리")
    print(f"  파일: {args.input_file} ({total}개 상품)")
    print(f"  모드: {'빠른 검증 (소싱+마진)' if args.quick else '전체 파이프라인'}")
    print(f"{'='*60}\n")

    results = []
    passed = held = excluded = errors = 0
    start_time = time.time()

    for i, product in enumerate(products, 1):
        name = product.get("title", product.get("url", "?"))[:45]
        print(f"[{i}/{total}] {name}...", end=" ", flush=True)

        try:
            result = process_single(product, i, total, args.quick)
            results.append(result)

            status = result.get("final_status", "?")
            price_str = ""
            if result.get("final_price_krw"):
                price_str = f" ₩{result['final_price_krw']:,.0f}"

            if status == "통과":
                print(f"✅ 통과{price_str} ({result.get('margin_rate', 0):.1f}%)")
                passed += 1
            elif status == "보류":
                flags = result.get("risk_flags", [])
                print(f"⚠️  보류 ({', '.join(flags[:2])}){price_str}")
                held += 1
            elif status == "제외":
                print(f"❌ 제외")
                excluded += 1
            else:
                print(f"❓ {status}")
                errors += 1

        except Exception as e:
            print(f"💥 오류: {e}")
            results.append({"idx": i, "url": product.get("url"), "final_status": "오류", "error": str(e)})
            errors += 1

        if i < total:
            time.sleep(args.delay)

    elapsed = time.time() - start_time

    # 결과 저장
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.output:
        out = args.output
    else:
        out = f"reports/batch_{timestamp}.csv"

    if out.endswith('.json'):
        save_results_json(results, out)
    else:
        save_results_csv(results, out)

    # JSON도 항상 저장
    json_path = f"reports/batch_{timestamp}.json"
    save_results_json(results, json_path)

    # 요약
    print(f"\n{'='*60}")
    print(f"  배치 처리 완료 ({elapsed:.0f}초)")
    print(f"  ✅ 통과: {passed}  ⚠️ 보류: {held}  ❌ 제외: {excluded}  💥 오류: {errors}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
