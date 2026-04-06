#!/usr/bin/env python3
"""
상세페이지 HTML 렌더러
=======================
premium_detail_page 결과를 스마트스토어/쿠팡에 바로 붙여넣을 수 있는 HTML로 변환

사용법:
  python html_renderer.py reports/premium_20260403_103000.json
  python html_renderer.py reports/premium_*.json --template minimal
"""

import os
import sys
import json
import argparse
import glob
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def render_naver_html(result: Dict) -> str:
    """네이버 스마트스토어 상세페이지 HTML"""
    titles = result.get("product_titles", {})
    hooks = result.get("hook_copies", [])
    sections = result.get("naver_detail_page", {}).get("sections", [])
    faq = result.get("faq", [])
    seo = result.get("seo_strategy", {})
    edge = result.get("competitive_edge", {})

    html = []
    html.append("""<div style="max-width:860px; margin:0 auto; font-family:'Noto Sans KR',sans-serif; color:#333; line-height:1.8;">""")

    # 후크 카피 (상단 배너)
    if hooks:
        html.append('<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); padding:40px 30px; border-radius:12px; margin-bottom:30px; text-align:center;">')
        for h in hooks[:3]:
            html.append(f'<p style="color:#fff; font-size:22px; font-weight:700; margin:8px 0;">{h}</p>')
        html.append('</div>')

    # 섹션별 렌더링
    for i, section in enumerate(sections):
        name = section.get("section_name", "")
        content = section.get("content", "")
        image_guide = section.get("image_guide", "")

        # 배경색 교차
        bg = "#fff" if i % 2 == 0 else "#f8f9fa"

        html.append(f'<div style="background:{bg}; padding:30px; margin-bottom:20px; border-radius:8px;">')

        # 섹션 제목
        html.append(f'<h2 style="font-size:20px; color:#2d3436; border-bottom:3px solid #6c5ce7; padding-bottom:10px; margin-bottom:20px;">{name}</h2>')

        # 이미지 가이드 (주석으로)
        if image_guide:
            html.append(f'<!-- 이미지 가이드: {image_guide} -->')
            html.append(f'<div style="background:#fff3cd; border:1px dashed #ffc107; padding:12px; border-radius:6px; margin-bottom:15px; font-size:13px; color:#856404;">')
            html.append(f'📷 이미지: {image_guide}')
            html.append('</div>')

        # 본문 — 줄바꿈을 <br>로, 글머리 기호를 스타일링
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("✓") or line.startswith("•") or line.startswith("-"):
                html.append(f'<p style="padding-left:20px; margin:6px 0;">✓ {line.lstrip("✓•- ")}</p>')
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                text = line.lstrip("# ")
                size = max(16, 24 - level * 2)
                html.append(f'<h3 style="font-size:{size}px; color:#2d3436; margin:15px 0 8px;">{text}</h3>')
            else:
                html.append(f'<p style="margin:8px 0; font-size:15px;">{line}</p>')

        html.append('</div>')

    # FAQ 아코디언 스타일
    if faq:
        html.append('<div style="padding:30px; margin-bottom:20px;">')
        html.append('<h2 style="font-size:20px; color:#2d3436; border-bottom:3px solid #6c5ce7; padding-bottom:10px; margin-bottom:20px;">자주 묻는 질문</h2>')
        for item in faq:
            q = item.get("q", "") if isinstance(item, dict) else ""
            a = item.get("a", "") if isinstance(item, dict) else ""
            html.append(f'''
<div style="border:1px solid #ddd; border-radius:8px; margin-bottom:10px; overflow:hidden;">
  <div style="background:#f1f2f6; padding:12px 16px; font-weight:600; font-size:15px;">Q. {q}</div>
  <div style="padding:12px 16px; font-size:14px; color:#555;">A. {a}</div>
</div>''')
        html.append('</div>')

    # 차별화 포인트
    if edge:
        strengths = edge.get("strengths", [])
        if strengths:
            html.append('<div style="background:#dfe6e9; padding:25px; border-radius:8px; margin-bottom:20px;">')
            html.append('<h3 style="font-size:18px; margin-bottom:12px;">왜 이 제품인가요?</h3>')
            for s in strengths:
                html.append(f'<p style="margin:6px 0;">✓ {s}</p>')
            html.append('</div>')

    # 법적 고지
    html.append('''
<div style="background:#f8f9fa; padding:20px; border-radius:8px; margin-top:20px; font-size:12px; color:#999; text-align:center;">
  <p>※ 본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다.</p>
  <p>※ 개인에 따라 차이가 있을 수 있습니다.</p>
</div>''')

    html.append('</div>')
    return "\n".join(html)


def render_coupang_html(result: Dict) -> str:
    """쿠팡 상세페이지 HTML (더 간결, 모바일 최적화)"""
    hooks = result.get("hook_copies", [])
    coupang_text = result.get("coupang_detail_page", "")
    faq = result.get("faq", [])

    html = []
    html.append('<div style="max-width:680px; margin:0 auto; font-family:sans-serif; color:#333; line-height:1.7;">')

    # 후크
    if hooks:
        html.append(f'<div style="background:#ff6b35; padding:25px; text-align:center; border-radius:8px; margin-bottom:20px;">')
        html.append(f'<p style="color:#fff; font-size:20px; font-weight:700;">{hooks[0]}</p>')
        html.append('</div>')

    # 본문
    if coupang_text:
        lines = coupang_text.split("\n")
        html.append('<div style="padding:20px;">')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("•") or line.startswith("-"):
                html.append(f'<p style="padding-left:15px; margin:5px 0;">• {line.lstrip("•- ")}</p>')
            else:
                html.append(f'<p style="margin:8px 0; font-size:15px;">{line}</p>')
        html.append('</div>')

    # FAQ (간결)
    if faq:
        html.append('<div style="padding:20px;">')
        for item in faq[:3]:
            q = item.get("q", "") if isinstance(item, dict) else ""
            a = item.get("a", "") if isinstance(item, dict) else ""
            html.append(f'<p style="font-weight:600;">Q. {q}</p>')
            html.append(f'<p style="color:#555; margin-bottom:12px;">A. {a}</p>')
        html.append('</div>')

    html.append('''
<p style="font-size:11px; color:#aaa; text-align:center; margin-top:20px;">
※ 본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다.
</p>''')
    html.append('</div>')
    return "\n".join(html)


def main():
    parser = argparse.ArgumentParser(description="상세페이지 HTML 렌더러")
    parser.add_argument("input_files", nargs="+", help="premium 결과 JSON 파일")
    parser.add_argument("--platform", default="both", choices=["naver", "coupang", "both"])
    args = parser.parse_args()

    files = []
    for pattern in args.input_files:
        files.extend(glob.glob(pattern))

    if not files:
        print("파일을 찾을 수 없습니다")
        sys.exit(1)

    for filepath in files:
        print(f"처리: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # premium JSON에서 detail_page 추출
        detail = data.get("results", {}).get("detail_page", data.get("detail_page", data))

        if "error" in detail:
            print(f"  오류: {detail['error']}")
            continue

        base = filepath.replace('.json', '')

        if args.platform in ("naver", "both"):
            naver_html = render_naver_html(detail)
            out = f"{base}_naver.html"
            with open(out, 'w', encoding='utf-8') as f:
                f.write(naver_html)
            print(f"  네이버: {out}")

        if args.platform in ("coupang", "both"):
            coupang_html = render_coupang_html(detail)
            out = f"{base}_coupang.html"
            with open(out, 'w', encoding='utf-8') as f:
                f.write(coupang_html)
            print(f"  쿠팡: {out}")


if __name__ == "__main__":
    main()
