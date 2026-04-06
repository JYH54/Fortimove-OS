#!/usr/bin/env python3
"""
Fortimove CLI — 전체 도구 통합 진입점
======================================

사용법:
  python fortimove.py premium --title "콜라겐 분말" --price 52 --category wellness
  python fortimove.py keyword "비타민C"
  python fortimove.py daily
  python fortimove.py sales add --name "콜라겐" --orders 10 --revenue 299000
  python fortimove.py sales report
  python fortimove.py lifecycle status
  python fortimove.py review --file reviews.txt
  python fortimove.py scout
  python fortimove.py image product.jpg
  python fortimove.py country US
  python fortimove.py quick --title "텀블러" --price 28.5
"""

import os
import sys
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


COMMANDS = {
    "premium":   {"script": "run_premium.py",        "desc": "1개 상품 초퀄리티 분석 (상세페이지+광고)"},
    "quick":     {"script": "run_fast_track.py",      "desc": "빠른 소싱+마진 검증"},
    "keyword":   {"script": "keyword_research.py",    "desc": "네이버 쇼핑 키워드 리서치"},
    "daily":     {"script": "daily_workflow.py",       "desc": "일일 자동 워크플로우 (Scout→추천→알림)"},
    "scout":     {"script": "scout_recommend.py",      "desc": "Scout 수집 상품 A/B등급 추천"},
    "sales":     {"script": "sales_tracker.py",        "desc": "판매 성과 추적 (add/list/report/replace)"},
    "lifecycle": {"script": "product_lifecycle.py",    "desc": "상품 라이프사이클 (status/check/promote)"},
    "review":    {"script": "review_analyzer.py",      "desc": "고객 리뷰 분석 → 개선점 추출"},
    "image":     {"script": "image_processor.py",      "desc": "이미지 현지화 (중국어→한국어)"},
    "batch":     {"script": "run_batch.py",            "desc": "CSV 배치 처리"},
    "export":    {"script": "export_channels.py",      "desc": "네이버/쿠팡 등록용 CSV 내보내기"},
    "report":    {"script": "report_generator.py",     "desc": "Markdown 보고서 생성"},
    "country":   {"script": "country_config.py",       "desc": "국가별 소싱 가이드 (CN/US/JP/VN)"},
    "detail-img":{"script": "detail_image_generator.py",  "desc": "상세페이지 이미지 생성 (Pillow 템플릿, 오프라인용)"},
    "gemini-img":{"script": "gemini_image.py",           "desc": "Gemini AI 이미지 (상세페이지 생성/번역/리디자인)"},
    "redesign":  {"script": "image_redesign.py",         "desc": "이미지 번역 + 리디자인 (OCR 기반, 오프라인용)"},
    "review-page":{"script": "review_server.py",         "desc": "상세페이지 검토 서버 (브라우저에서 미리보기+검토)"},
    "html":      {"script": "html_renderer.py",         "desc": "상세페이지 HTML 변환 (참고용)"},
    "ai-status": {"script": "ai_providers.py",          "desc": "AI 제공자 상태 + 작업 라우팅 + 비용 테이블"},
    "score":     {"script": "product_score.py",        "desc": "상품 등록 가치 점수 테스트"},
}


def print_help():
    print("""
  Fortimove CLI — 이커머스 자동화 도구 모음

  사용법: python fortimove.py <명령어> [옵션]

  ━━━ 핵심 도구 (매일 사용) ━━━
  premium    1개 상품 초퀄리티 분석 (소싱→마진→상세페이지→광고)
  keyword    네이버 쇼핑 키워드 리서치 + 광고 전략
  daily      일일 자동 워크플로우 (Scout→추천→Slack 알림)
  scout      Scout 수집 상품 중 A/B등급 자동 추천

  ━━━ 성과 관리 ━━━
  sales      판매 성과 추적 (add/list/report/replace)
  lifecycle  상품 라이프사이클 (테스트→반복→PB 전환)
  review     고객 리뷰 분석 → 상세페이지 개선

  ━━━ 도구 ━━━
  quick      빠른 소싱+마진 검증
  image      이미지 현지화 (중국어→한국어 변환)
  gemini-img Gemini AI 이미지 (상세페이지 생성/번역/리디자인) ★추천
  detail-img 상세페이지 이미지 생성 (Pillow, 오프라인 fallback)
  redesign   이미지 번역+리디자인 (OCR 기반, 오프라인 fallback)
  review-page 상세페이지 검토 서버 (브라우저 미리보기+승인)
  country    국가별 소싱 가이드 (CN/US/JP/VN)
  batch      CSV 배치 처리
  export     네이버/쿠팡 등록용 CSV
  report     Markdown 보고서 생성

  ━━━ 예시 ━━━
  python fortimove.py premium --title "콜라겐 분말" --price 52 --country US --category wellness
  python fortimove.py keyword "비타민C" --budget 20000
  python fortimove.py daily --auto-premium 1
  python fortimove.py sales add --name "콜라겐" --orders 10 --revenue 299000
  python fortimove.py lifecycle status
  python fortimove.py review --reviews "좋아요" "배송 느림" "품질 좋음"
""")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd not in COMMANDS:
        print(f"\n  알 수 없는 명령어: {cmd}")
        print(f"  python fortimove.py --help 로 전체 명령어를 확인하세요\n")
        sys.exit(1)

    script = COMMANDS[cmd]["script"]
    script_path = Path(__file__).parent / script

    if not script_path.exists():
        print(f"\n  스크립트를 찾을 수 없습니다: {script}")
        sys.exit(1)

    # 나머지 인수를 그대로 전달
    remaining_args = sys.argv[2:]
    cmd_line = f'{sys.executable} "{script_path}" {" ".join(remaining_args)}'
    exit_code = os.system(cmd_line)
    sys.exit(exit_code >> 8)  # os.system returns shifted exit code


if __name__ == "__main__":
    main()
