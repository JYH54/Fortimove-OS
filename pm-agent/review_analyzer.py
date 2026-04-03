#!/usr/bin/env python3
"""
고객 리뷰 분석기
=================
고객 리뷰 텍스트에서 상품/상세페이지 개선점을 추출

기능:
  - 긍정/부정 포인트 분류
  - 반복되는 불만 패턴 감지
  - 상세페이지 개선 제안
  - 경쟁 상품 대비 차별화 포인트 발견
  - 키워드 추출 (SEO 반영용)

사용법:
  python review_analyzer.py --reviews "리뷰1" "리뷰2" "리뷰3"
  python review_analyzer.py --file reviews.txt
  python review_analyzer.py --file reviews.txt --product "콜라겐 분말"
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from anthropic import Anthropic

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


class ReviewAnalyzer:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 필요")
        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    def analyze(self, reviews: List[str], product_name: str = "") -> Dict:
        """리뷰 목록을 분석하여 인사이트 추출"""

        reviews_text = "\n".join(f"[리뷰 {i+1}] {r}" for i, r in enumerate(reviews))

        prompt = f"""당신은 이커머스 리뷰 분석 전문가입니다.

아래 고객 리뷰들을 분석하여 상품 및 상세페이지 개선에 필요한 인사이트를 추출하세요.

상품명: {product_name or "미지정"}
리뷰 수: {len(reviews)}개

═══════ 리뷰 데이터 ═══════
{reviews_text}
═══════════════════════════

분석 요구사항:

1. **만족 포인트** (3~5개) — 고객이 좋아하는 점, 상세페이지에서 강조할 내용
2. **불만 포인트** (3~5개) — 반복되는 불만, 개선 필요 사항
3. **상세페이지 개선 제안** (3~5개) — 리뷰 기반으로 추가/수정해야 할 내용
4. **FAQ 추가 제안** (2~3개) — 리뷰에서 자주 나오는 질문을 FAQ에 추가
5. **SEO 키워드** (5~10개) — 고객이 실제로 사용하는 단어 (상품명/태그에 반영)
6. **전체 평가** — 이 상품을 계속 판매할지 판단

JSON으로만 응답하세요:
{{
  "satisfaction_points": ["포인트1", "포인트2", ...],
  "pain_points": ["불만1", "불만2", ...],
  "detail_page_improvements": ["개선1", "개선2", ...],
  "faq_suggestions": [
    {{"q": "질문", "a": "리뷰 기반 답변"}}
  ],
  "seo_keywords_from_reviews": ["키워드1", "키워드2", ...],
  "overall_sentiment": "긍정/혼합/부정",
  "continue_selling": true,
  "summary": "전체 분석 요약 2줄"
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "JSON 파싱 실패", "raw": content[:1000]}


def print_analysis(result: Dict, product_name: str = ""):
    """분석 결과 출력"""
    if "error" in result:
        print(f"  오류: {result['error']}")
        return

    print(f"\n{'='*55}")
    print(f"  리뷰 분석 결과{' — ' + product_name if product_name else ''}")
    print(f"  감성: {result.get('overall_sentiment', '?')}  |  판매 지속: {'O' if result.get('continue_selling') else 'X'}")
    print(f"{'='*55}\n")

    print(result.get("summary", ""))
    print()

    sat = result.get("satisfaction_points", [])
    if sat:
        print(f"  [만족 포인트] — 상세페이지에서 강조하세요")
        for s in sat:
            print(f"    + {s}")
        print()

    pain = result.get("pain_points", [])
    if pain:
        print(f"  [불만 포인트] — 개선하거나 상세페이지에서 사전 안내")
        for p in pain:
            print(f"    - {p}")
        print()

    improve = result.get("detail_page_improvements", [])
    if improve:
        print(f"  [상세페이지 개선 제안]")
        for i, imp in enumerate(improve, 1):
            print(f"    {i}. {imp}")
        print()

    faq = result.get("faq_suggestions", [])
    if faq:
        print(f"  [FAQ 추가 제안]")
        for item in faq:
            print(f"    Q. {item.get('q', '')}")
            print(f"    A. {item.get('a', '')}")
            print()

    keywords = result.get("seo_keywords_from_reviews", [])
    if keywords:
        print(f"  [SEO 키워드 (고객 실사용 단어)]")
        print(f"    {', '.join(keywords)}")


def main():
    parser = argparse.ArgumentParser(description="고객 리뷰 분석기")
    parser.add_argument("--reviews", nargs="+", default=None, help="리뷰 텍스트 (여러 개)")
    parser.add_argument("--file", "-f", default=None, help="리뷰 파일 (줄 단위)")
    parser.add_argument("--product", "-p", default="", help="상품명")
    parser.add_argument("--save", action="store_true", help="결과 JSON 저장")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY 필요")
        sys.exit(1)

    reviews = []
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            reviews = [line.strip() for line in f if line.strip()]
    elif args.reviews:
        reviews = args.reviews
    else:
        parser.error("--reviews 또는 --file 중 하나를 지정하세요")

    if not reviews:
        print("  분석할 리뷰가 없습니다")
        return

    print(f"  {len(reviews)}개 리뷰 분석 중...")

    analyzer = ReviewAnalyzer()
    result = analyzer.analyze(reviews, args.product)

    print_analysis(result, args.product)

    if args.save or "error" not in result:
        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"reports/review_analysis_{timestamp}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n  저장: {path}")


if __name__ == "__main__":
    main()
