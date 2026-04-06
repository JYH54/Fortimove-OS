#!/usr/bin/env python3
"""
결과 리포트 생성기
==================
배치 처리 결과 JSON을 보기 좋은 Markdown 보고서로 변환

사용법:
  python report_generator.py reports/batch_20260402_103000.json
  python report_generator.py reports/fast_track_20260402_103000.json
  python report_generator.py reports/batch_*.json --merge   # 여러 결과 병합
"""

import os
import sys
import json
import glob
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def generate_batch_report(data: Dict, source_file: str = "") -> str:
    """배치 처리 결과 Markdown 보고서 생성"""
    results = data.get("results", [])
    timestamp = data.get("timestamp", datetime.now().isoformat())

    passed = [r for r in results if r.get("final_status") == "통과"]
    held = [r for r in results if r.get("final_status") == "보류"]
    excluded = [r for r in results if r.get("final_status") == "제외"]
    errors = [r for r in results if r.get("final_status") == "오류"]

    md = []
    md.append(f"# Fortimove 배치 처리 보고서")
    md.append(f"")
    md.append(f"**생성일시**: {timestamp[:19]}")
    md.append(f"**소스 파일**: {source_file}")
    md.append(f"**전체 상품**: {len(results)}개")
    md.append(f"")

    # 요약
    md.append(f"## 1. 처리 요약")
    md.append(f"")
    md.append(f"| 상태 | 수량 | 비율 |")
    md.append(f"|------|------|------|")
    total = len(results) or 1
    md.append(f"| ✅ 통과 | {len(passed)}개 | {len(passed)/total*100:.0f}% |")
    md.append(f"| ⚠️ 보류 | {len(held)}개 | {len(held)/total*100:.0f}% |")
    md.append(f"| ❌ 제외 | {len(excluded)}개 | {len(excluded)/total*100:.0f}% |")
    md.append(f"| 💥 오류 | {len(errors)}개 | {len(errors)/total*100:.0f}% |")
    md.append(f"")

    # 통과 상품 상세
    if passed:
        md.append(f"## 2. 통과 상품 ({len(passed)}개)")
        md.append(f"")
        md.append(f"| # | 상품명 | 판매가 | 마진율 | 등록 제목 | 컴플라이언스 |")
        md.append(f"|---|--------|--------|--------|----------|------------|")
        for i, r in enumerate(passed, 1):
            title = (r.get("title") or "")[:25]
            price = r.get("final_price_krw", 0)
            price_str = f"₩{price:,.0f}" if price else "-"
            margin = r.get("margin_rate", 0)
            margin_str = f"{margin:.1f}%" if margin else "-"
            reg_title = (r.get("registration_title") or "")[:25]
            comp = r.get("compliance_status", "-")
            md.append(f"| {i} | {title} | {price_str} | {margin_str} | {reg_title} | {comp} |")
        md.append(f"")

        # 총 예상 매출
        total_revenue = sum(r.get("final_price_krw", 0) for r in passed if r.get("final_price_krw"))
        total_margin = sum(
            r.get("final_price_krw", 0) * r.get("margin_rate", 0) / 100
            for r in passed if r.get("final_price_krw") and r.get("margin_rate")
        )
        if total_revenue:
            md.append(f"**예상 총 매출 (각 1개 판매 시)**: ₩{total_revenue:,.0f}")
            md.append(f"**예상 총 마진**: ₩{total_margin:,.0f}")
            md.append(f"")

    # 보류 상품
    if held:
        md.append(f"## 3. 보류 상품 ({len(held)}개)")
        md.append(f"")
        md.append(f"| # | 상품명 | 리스크 | 비고 |")
        md.append(f"|---|--------|--------|------|")
        for i, r in enumerate(held, 1):
            title = (r.get("title") or "")[:30]
            flags = r.get("risk_flags", [])
            flags_str = ", ".join(flags[:3]) if flags else "-"
            md.append(f"| {i} | {title} | {flags_str} | 수동 검토 필요 |")
        md.append(f"")

    # 제외 상품
    if excluded:
        md.append(f"## 4. 제외 상품 ({len(excluded)}개)")
        md.append(f"")
        for r in excluded:
            title = r.get("title") or "?"
            flags = r.get("risk_flags", [])
            md.append(f"- **{title}**: {', '.join(flags) if flags else '리스크 판정'}")
        md.append(f"")

    # 벤더 질문 요약
    all_vendor_q = []
    for r in passed + held:
        vq = r.get("vendor_questions_ko", [])
        if vq:
            all_vendor_q.append((r.get("title", "?"), vq))

    if all_vendor_q:
        md.append(f"## 5. 벤더 질문 모음")
        md.append(f"")
        for title, questions in all_vendor_q:
            md.append(f"### {title[:40]}")
            for q in questions:
                md.append(f"- {q}")
            md.append(f"")

    md.append(f"---")
    md.append(f"*Fortimove-OS 자동 생성 보고서*")

    return "\n".join(md)


def generate_fast_track_report(data: Dict) -> str:
    """Fast-Track 단건 결과 Markdown 보고서"""
    results = data.get("results", {})
    input_data = data.get("input", {})
    timestamp = data.get("timestamp", "")

    md = []
    md.append(f"# Fast-Track 상품 분석 보고서")
    md.append(f"")
    md.append(f"**생성일시**: {timestamp[:19]}")
    md.append(f"**상품 URL**: {input_data.get('url', '-')}")
    md.append(f"**매입가**: ¥{input_data.get('price_cny', '-')}")
    md.append(f"")

    # 소싱 판정
    s = results.get("sourcing", {})
    md.append(f"## 1. 소싱 리스크 분석")
    md.append(f"- **판정**: {s.get('sourcing_decision', '?')}")
    md.append(f"- **분류**: {s.get('product_classification', '?')}")
    flags = s.get("risk_flags", [])
    if flags:
        md.append(f"- **리스크**: {', '.join(flags)}")
    else:
        md.append(f"- **리스크**: 없음")
    md.append(f"")

    # 마진
    p = results.get("pricing", {})
    if p and not p.get("error"):
        md.append(f"## 2. 가격/마진 분석")
        cb = p.get("cost_breakdown", {})
        md.append(f"| 항목 | 금액 |")
        md.append(f"|------|------|")
        for k, v in cb.items():
            label = k.replace("_krw", "").replace("_", " ").title()
            md.append(f"| {label} | ₩{v:,.0f} |")
        md.append(f"")
        md.append(f"**최종 판매가**: ₩{p.get('final_price', 0):,.0f}")
        md.append(f"**마진율**: {p.get('margin_rate', 0):.1f}%")
        md.append(f"")

    # 등록
    r = results.get("registration", {})
    if r and not r.get("error"):
        md.append(f"## 3. 상품 등록 초안")
        md.append(f"- **등록 제목**: {r.get('registration_title_ko', '-')}")
        md.append(f"- **상태**: {r.get('registration_status', '-')}")
        md.append(f"- **설명**: {r.get('short_description_ko', '-')}")
        md.append(f"")

    # 콘텐츠
    c = results.get("content", {})
    if c and not c.get("error"):
        md.append(f"## 4. 콘텐츠")
        md.append(f"- **컴플라이언스**: {c.get('compliance_status', '-')}")
        if c.get("seo_title"):
            md.append(f"- **SEO 제목**: {c['seo_title']}")
        md.append(f"")
        md.append(f"### 메인 콘텐츠")
        md.append(f"```")
        md.append(c.get("main_content", "")[:500])
        md.append(f"```")
        md.append(f"")

    # 상세페이지
    d = results.get("detail_page", {})
    if d and not d.get("error"):
        md.append(f"## 5. 상세페이지 전략")
        if d.get("hook_copies"):
            md.append(f"### 후크 카피")
            for i, h in enumerate(d["hook_copies"], 1):
                md.append(f"{i}. {h}")
            md.append(f"")
        if d.get("faq"):
            md.append(f"### FAQ")
            for faq in d["faq"][:5]:
                if isinstance(faq, dict):
                    md.append(f"**Q**: {faq.get('q', '')}")
                    md.append(f"**A**: {faq.get('a', '')}")
                    md.append(f"")

    # 벤더 질문
    vq_ko = s.get("vendor_questions_ko", [])
    vq_zh = s.get("vendor_questions_zh", [])
    if vq_ko or vq_zh:
        md.append(f"## 벤더 질문")
        if vq_ko:
            md.append(f"### 한국어")
            for q in vq_ko:
                md.append(f"- {q}")
        if vq_zh:
            md.append(f"### 중국어")
            for q in vq_zh:
                md.append(f"- {q}")
        md.append(f"")

    md.append(f"---")
    md.append(f"*Fortimove-OS 자동 생성 보고서*")
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="결과 리포트 생성기")
    parser.add_argument("input_files", nargs="+", help="결과 JSON 파일(들)")
    parser.add_argument("--output", "-o", type=str, default=None, help="출력 파일 경로")
    args = parser.parse_args()

    # 글로브 패턴 확장
    files = []
    for pattern in args.input_files:
        files.extend(glob.glob(pattern))

    if not files:
        print("❌ 입력 파일을 찾을 수 없습니다")
        sys.exit(1)

    for filepath in files:
        print(f"📄 처리: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 타입 감지 (배치 vs 단건)
        if "results" in data and isinstance(data["results"], list):
            report = generate_batch_report(data, filepath)
        elif "results" in data and isinstance(data["results"], dict):
            report = generate_fast_track_report(data)
        else:
            print(f"  ⚠️  알 수 없는 형식, 스킵")
            continue

        # 출력
        if args.output:
            out_path = args.output
        else:
            out_path = filepath.replace('.json', '.md')

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"  ✅ 보고서 생성: {out_path}")


if __name__ == "__main__":
    main()
