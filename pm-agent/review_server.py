#!/usr/bin/env python3
"""
상세페이지 검토 서버
=====================
생성된 상세페이지 이미지 + 카피를 브라우저에서 미리보고 검토

기능:
  - 상세페이지 이미지 섹션별 미리보기
  - 카피 텍스트 확인
  - 광고 전략 확인
  - 승인/수정 메모

사용법:
  python review_server.py reports/premium_20260403_103000.json
  → 브라우저에서 http://localhost:8888 접속
"""

import os
import sys
import json
import argparse
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
import threading


def generate_review_html(json_path: str) -> str:
    """검토용 HTML 페이지 생성"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = data.get("results", data)
    input_data = data.get("input", {})
    detail = results.get("detail_page", {})
    pricing = results.get("pricing", {})
    sourcing = results.get("sourcing", {})
    score = results.get("score", {})

    titles = detail.get("product_titles", {})
    hooks = detail.get("hook_copies", [])
    sections = detail.get("naver_detail_page", {}).get("sections", [])
    faq = detail.get("faq", [])
    ad = detail.get("ad_strategy", {})
    seo = detail.get("seo_strategy", {})
    edge = detail.get("competitive_edge", {})

    # 이미지 디렉토리 찾기
    base = Path(json_path).stem
    img_dir = Path(json_path).parent / f"{base}_images"
    images = sorted(img_dir.glob("*.png")) if img_dir.exists() else []

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fortimove 상세페이지 검토</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Noto Sans KR',sans-serif; background:#f0f2f5; color:#333; }}
  .container {{ max-width:1200px; margin:0 auto; padding:20px; display:grid; grid-template-columns:1fr 380px; gap:20px; }}
  .main {{ background:#fff; border-radius:12px; padding:0; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08); }}
  .sidebar {{ position:sticky; top:20px; height:fit-content; }}
  .card {{ background:#fff; border-radius:12px; padding:20px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.08); }}
  h1 {{ font-size:20px; padding:20px 24px; background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; }}
  h2 {{ font-size:16px; color:#6c5ce7; margin-bottom:12px; border-bottom:2px solid #6c5ce7; padding-bottom:6px; }}
  h3 {{ font-size:14px; color:#2d3436; margin:12px 0 6px; }}
  .section-img {{ width:100%; display:block; border-bottom:1px solid #eee; }}
  .section-text {{ padding:16px 24px; border-bottom:1px solid #f0f0f0; }}
  .section-text .guide {{ background:#fff3cd; padding:8px 12px; border-radius:6px; font-size:12px; color:#856404; margin-top:8px; }}
  .tag {{ display:inline-block; background:#e8e8ff; color:#6c5ce7; padding:3px 10px; border-radius:12px; font-size:12px; margin:2px; }}
  .metric {{ display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #f5f5f5; }}
  .metric-label {{ color:#999; font-size:13px; }}
  .metric-value {{ font-weight:600; font-size:14px; }}
  .grade {{ display:inline-block; padding:4px 12px; border-radius:6px; font-weight:700; font-size:14px; }}
  .grade-A {{ background:#00b894; color:#fff; }}
  .grade-B {{ background:#0984e3; color:#fff; }}
  .grade-C {{ background:#fdcb6e; color:#333; }}
  .grade-D {{ background:#d63031; color:#fff; }}
  .hook {{ font-size:18px; font-weight:600; color:#6c5ce7; margin:8px 0; }}
  .ad-kw {{ padding:6px 0; border-bottom:1px solid #f5f5f5; font-size:13px; }}
  .btn {{ display:block; width:100%; padding:12px; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; margin-top:8px; text-align:center; }}
  .btn-approve {{ background:#00b894; color:#fff; }}
  .btn-edit {{ background:#fdcb6e; color:#333; }}
  textarea {{ width:100%; padding:10px; border:1px solid #ddd; border-radius:6px; font-size:13px; resize:vertical; }}
</style>
</head>
<body>
<div class="container">
  <div class="main">
    <h1>상세페이지 검토 — {input_data.get('title', '')[:40]}</h1>
"""

    # 이미지 섹션 + 텍스트 교차 배치
    if images:
        for img_path in images:
            # 상대 경로로 변환
            rel = os.path.relpath(img_path, Path(json_path).parent)
            html += f'    <img src="{rel}" class="section-img" alt="{img_path.stem}">\n'

    # 섹션 텍스트
    for section in sections:
        name = section.get("section_name", "")
        content = section.get("content", "")
        guide = section.get("image_guide", "")
        html += f"""
    <div class="section-text">
      <h3>{name}</h3>
      <p style="font-size:14px; line-height:1.7; white-space:pre-wrap;">{content}</p>
      {'<div class="guide">📷 ' + guide + '</div>' if guide else ''}
    </div>"""

    html += """
  </div>
  <div class="sidebar">
"""

    # 점수 카드
    g = score.get("grade", "?")
    grade_class = f"grade-{g}" if g in "ABCD" else ""
    html += f"""
    <div class="card">
      <h2>등록 가치 점수</h2>
      <div style="text-align:center; margin:12px 0;">
        <span class="grade {grade_class}">{g}등급 ({score.get('total', 0):.0f}점)</span>
      </div>
      <p style="text-align:center; font-size:13px; color:#666;">{score.get('decision', '')}</p>
    </div>"""

    # 가격 카드
    html += f"""
    <div class="card">
      <h2>가격/마진</h2>
      <div class="metric"><span class="metric-label">판매가</span><span class="metric-value">₩{pricing.get('final_price', 0):,.0f}</span></div>
      <div class="metric"><span class="metric-label">순마진율</span><span class="metric-value">{pricing.get('margin_rate', 0):.1f}%</span></div>
      <div class="metric"><span class="metric-label">손익분기</span><span class="metric-value">{pricing.get('breakeven_qty', '?')}개</span></div>
      <div class="metric"><span class="metric-label">판정</span><span class="metric-value">{pricing.get('pricing_decision', '')}</span></div>
    </div>"""

    # 상품명
    html += f"""
    <div class="card">
      <h2>상품명</h2>
      <h3>스마트스토어</h3>
      <p style="font-size:13px; margin-bottom:8px;">{titles.get('smartstore', '')}</p>
      <h3>쿠팡</h3>
      <p style="font-size:13px;">{titles.get('coupang', '')}</p>
    </div>"""

    # 후크 카피
    if hooks:
        html += '<div class="card"><h2>후크 카피</h2>'
        for h in hooks:
            html += f'<p class="hook">▸ {h}</p>'
        html += '</div>'

    # SEO 태그
    tags = seo.get("shopping_tags", [])
    if tags:
        html += '<div class="card"><h2>SEO 태그</h2>'
        for t in tags:
            html += f'<span class="tag">{t}</span>'
        html += '</div>'

    # 광고 전략
    if ad.get("keywords"):
        html += f"""
    <div class="card">
      <h2>검색광고 전략</h2>
      <div class="metric"><span class="metric-label">일 예산</span><span class="metric-value">₩{ad.get('daily_budget_krw', 0):,}</span></div>"""
        for kw in ad.get("keywords", [])[:5]:
            html += f'<div class="ad-kw">{kw.get("keyword","")} — CPC ₩{kw.get("estimated_cpc",0):,} ({kw.get("competition","")})</div>'
        html += '</div>'

    # 검토 액션
    html += """
    <div class="card">
      <h2>검토</h2>
      <textarea rows="4" placeholder="수정 메모를 작성하세요..."></textarea>
      <button class="btn btn-approve" onclick="alert('승인 — 스마트스토어에 등록하세요')">✅ 승인 — 등록 진행</button>
      <button class="btn btn-edit" onclick="alert('수정 필요 — 메모를 확인하세요')">✏️ 수정 필요</button>
    </div>"""

    html += """
  </div>
</div>
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="상세페이지 검토 서버")
    parser.add_argument("json_file", help="premium 결과 JSON 파일")
    parser.add_argument("--port", type=int, default=8888, help="서버 포트 (기본: 8888)")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 비활성화")
    args = parser.parse_args()

    if not os.path.exists(args.json_file):
        print(f"파일 없음: {args.json_file}")
        sys.exit(1)

    # HTML 생성
    review_html = generate_review_html(args.json_file)
    html_dir = os.path.dirname(os.path.abspath(args.json_file))
    html_path = os.path.join(html_dir, "_review.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(review_html)

    # 간단한 HTTP 서버
    os.chdir(html_dir)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *a):
            pass  # 로그 숨김

    server = HTTPServer(("127.0.0.1", args.port), QuietHandler)

    url = f"http://localhost:{args.port}/_review.html"
    print(f"\n  검토 서버 시작: {url}")
    print(f"  Ctrl+C로 종료\n")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  서버 종료")
        server.shutdown()
        # 임시 HTML 정리
        if os.path.exists(html_path):
            os.remove(html_path)


if __name__ == "__main__":
    main()
