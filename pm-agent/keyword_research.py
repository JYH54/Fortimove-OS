#!/usr/bin/env python3
"""
네이버 쇼핑 키워드 리서치 도구
===============================
상품 키워드에 대한 경쟁 강도, 추천 키워드, 광고 전략을 분석

기능:
  - 메인/서브/롱테일 키워드 도출
  - 키워드별 경쟁 강도 + CPC 추정
  - 네이버 쇼핑 태그 최적화
  - 상품명 SEO 최적화 (스마트스토어 50자 / 쿠팡 100자)
  - 시즌성 분석
  - 일 예산 + 입찰가 추천

사용법:
  python keyword_research.py "콜라겐"
  python keyword_research.py "비타민C" --category supplement
  python keyword_research.py "텀블러" --budget 30000
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
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
logger = logging.getLogger(__name__)


class KeywordResearcher:
    """네이버 쇼핑 키워드 리서치 전문가"""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 필요")
        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

        try:
            from cache_manager import LLMCache
            self.cache = LLMCache()
        except Exception:
            self.cache = None

    def research(
        self,
        keyword: str,
        category: str = "general",
        price_range: str = "",
        daily_budget: int = 0,
        target_customer: str = "",
    ) -> Dict:
        """
        키워드 기반 전체 리서치

        Returns:
            main_keywords, sub_keywords, longtail_keywords,
            keyword_analysis (with CPC, competition),
            title_suggestions, tag_suggestions,
            ad_strategy, seasonal_notes
        """

        # 캐시 조회
        if self.cache:
            cached = self.cache.get("keyword", keyword, category=category)
            if cached:
                return cached

        prompt = f"""당신은 네이버 쇼핑 검색광고 10년 경력의 키워드 전략가입니다.

아래 키워드에 대해 네이버 쇼핑 관점에서 철저한 키워드 리서치를 수행하세요.

═══════════════════════════════════════════
입력 정보
═══════════════════════════════════════════
- 검색 키워드: {keyword}
- 카테고리: {category}
- 가격대: {price_range or "미정"}
- 일 광고 예산: {"₩" + f"{daily_budget:,}" if daily_budget else "미정"}
- 타겟 고객: {target_customer or "미정"}
- 현재 날짜: {datetime.now().strftime("%Y-%m-%d")}

═══════════════════════════════════════════
분석 요구사항
═══════════════════════════════════════════

1. **메인 키워드 (3개)**
   - 검색량이 가장 높은 핵심 키워드
   - 예상 월간 검색량, 경쟁 강도(높음/중간/낮음), 예상 CPC

2. **서브 키워드 (7개)**
   - 메인보다 구체적, 구매 의도가 높은 키워드
   - "브랜드+카테고리", "기능+카테고리" 조합

3. **롱테일 키워드 (10개)**
   - 검색량은 적지만 전환율이 높은 3~4단어 조합
   - "가성비 OO 추천", "OO 효능 순위", "OO 먹는법" 등

4. **네이버 쇼핑 태그 (15개)**
   - 스마트스토어 등록 시 사용할 태그
   - 검색 노출 극대화 목적

5. **상품명 SEO 최적화**
   - 스마트스토어용 (50자 이내, 핵심 키워드 앞배치)
   - 쿠팡용 (100자 이내, [오늘출발] 포함)
   - 키워드 구조: [브랜드] [핵심키워드] [세부특징] [용량/수량]

6. **네이버 쇼핑 검색광고 전략**
   - 추천 광고 키워드 10개 (CPC, 경쟁도 포함)
   - 광고 제목 3안 (25자 이내)
   - 광고 설명 3안 (45자 이내)
   - 일 예산 추천
   - 시간대별 입찰 전략 (언제 높이고 언제 낮출지)

7. **시즌성 분석**
   - 이 키워드의 계절별 검색량 패턴
   - 현재 시점이 진입 적기인지

8. **경쟁 환경**
   - 상위 노출 상품들의 공통 특징
   - 신규 진입자의 차별화 포인트
   - 리뷰 수 기준 (몇 개부터 경쟁력 있는지)

JSON으로만 응답하세요:
{{
  "main_keywords": [
    {{"keyword": "키워드", "monthly_searches": 50000, "competition": "높음", "cpc_krw": 800}}
  ],
  "sub_keywords": [
    {{"keyword": "키워드", "monthly_searches": 5000, "competition": "중간", "cpc_krw": 400}}
  ],
  "longtail_keywords": [
    {{"keyword": "롱테일 키워드", "monthly_searches": 500, "intent": "구매/정보/비교"}}
  ],
  "shopping_tags": ["태그1", "태그2", ...],
  "title_suggestions": {{
    "smartstore": "스마트스토어 제목 50자",
    "coupang": "쿠팡 제목 100자"
  }},
  "ad_strategy": {{
    "keywords": [
      {{"keyword": "광고키워드", "cpc_krw": 500, "competition": "중간", "recommendation": "필수/권장/선택"}}
    ],
    "ad_titles": ["제목1", "제목2", "제목3"],
    "ad_descriptions": ["설명1", "설명2", "설명3"],
    "daily_budget_krw": 20000,
    "bid_strategy": "시간대별 입찰 전략 설명",
    "peak_hours": ["09:00-11:00", "20:00-23:00"]
  }},
  "seasonal": {{
    "pattern": "연중무휴/봄여름강세/겨울강세/시즌한정",
    "current_timing": "적기/보통/비수기",
    "peak_months": [1, 2, 11, 12],
    "notes": "시즌성 분석 메모"
  }},
  "competition": {{
    "top_product_features": ["특징1", "특징2"],
    "review_threshold": 100,
    "entry_difficulty": "쉬움/보통/어려움",
    "differentiation_tips": ["차별화1", "차별화2"]
  }}
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=6000,
            temperature=0.5,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(content)
            # 캐시 저장
            if self.cache and "error" not in result:
                self.cache.set("keyword", keyword, result, tokens_used=5000, category=category)
            return result
        except json.JSONDecodeError:
            return {"error": "JSON 파싱 실패", "raw": content[:2000]}


def print_research(result: Dict, keyword: str):
    """리서치 결과 출력"""
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print(f"\n{'='*60}")
    print(f"  네이버 쇼핑 키워드 리서치: \"{keyword}\"")
    print(f"{'='*60}\n")

    # 메인 키워드
    main = result.get("main_keywords", [])
    if main:
        print(f"━━━ 메인 키워드 ━━━")
        for kw in main:
            print(f"  {kw['keyword']:<20} 월 {kw.get('monthly_searches', '?'):>8,}회  |  경쟁 {kw.get('competition', '?'):<4}  |  CPC ₩{kw.get('cpc_krw', 0):,}")
        print()

    # 서브 키워드
    sub = result.get("sub_keywords", [])
    if sub:
        print(f"━━━ 서브 키워드 ━━━")
        for kw in sub:
            print(f"  {kw['keyword']:<25} 월 {kw.get('monthly_searches', '?'):>6,}회  |  경쟁 {kw.get('competition', '?'):<4}  |  CPC ₩{kw.get('cpc_krw', 0):,}")
        print()

    # 롱테일
    longtail = result.get("longtail_keywords", [])
    if longtail:
        print(f"━━━ 롱테일 키워드 (전환율 높음) ━━━")
        for kw in longtail:
            intent = kw.get("intent", "")
            print(f"  {kw['keyword']:<30} [{intent}]  월 {kw.get('monthly_searches', '?'):>5,}회")
        print()

    # 태그
    tags = result.get("shopping_tags", [])
    if tags:
        print(f"━━━ 네이버 쇼핑 태그 ({len(tags)}개) ━━━")
        print(f"  {', '.join(tags)}")
        print()

    # 상품명
    titles = result.get("title_suggestions", {})
    if titles:
        print(f"━━━ 상품명 SEO 최적화 ━━━")
        print(f"  스마트스토어: {titles.get('smartstore', '')}")
        print(f"  쿠팡:        {titles.get('coupang', '')}")
        print()

    # 광고 전략
    ad = result.get("ad_strategy", {})
    if ad:
        print(f"━━━ 검색광고 전략 ━━━")
        print(f"  일 예산: ₩{ad.get('daily_budget_krw', 0):,}")
        print(f"  피크 시간: {', '.join(ad.get('peak_hours', []))}")
        print(f"  입찰 전략: {ad.get('bid_strategy', '')}")
        print()
        print(f"  광고 제목:")
        for t in ad.get("ad_titles", []):
            print(f"    ▸ {t}")
        print(f"  광고 설명:")
        for d in ad.get("ad_descriptions", []):
            print(f"    ▸ {d}")
        print()

    # 시즌성
    seasonal = result.get("seasonal", {})
    if seasonal:
        print(f"━━━ 시즌성 분석 ━━━")
        print(f"  패턴: {seasonal.get('pattern', '?')}")
        print(f"  현재 시점: {seasonal.get('current_timing', '?')}")
        months = seasonal.get("peak_months", [])
        if months:
            print(f"  피크 월: {', '.join(str(m) + '월' for m in months)}")
        print(f"  {seasonal.get('notes', '')}")
        print()

    # 경쟁
    comp = result.get("competition", {})
    if comp:
        print(f"━━━ 경쟁 환경 ━━━")
        print(f"  진입 난이도: {comp.get('entry_difficulty', '?')}")
        print(f"  리뷰 기준: {comp.get('review_threshold', '?')}개 이상이면 경쟁력")
        for tip in comp.get("differentiation_tips", []):
            print(f"  • {tip}")


def main():
    parser = argparse.ArgumentParser(description="네이버 쇼핑 키워드 리서치")
    parser.add_argument("keyword", help="리서치할 키워드 (예: '콜라겐', '비타민C')")
    parser.add_argument("--category", default="general", help="카테고리")
    parser.add_argument("--price-range", default="", help="가격대 (예: '2만~3만원')")
    parser.add_argument("--budget", type=int, default=0, help="일 광고 예산 (원)")
    parser.add_argument("--target", default="", help="타겟 고객")
    parser.add_argument("--save", action="store_true", help="결과를 JSON으로 저장")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY 필요")
        sys.exit(1)

    researcher = KeywordResearcher()
    result = researcher.research(
        keyword=args.keyword,
        category=args.category,
        price_range=args.price_range,
        daily_budget=args.budget,
        target_customer=args.target,
    )

    print_research(result, args.keyword)

    if args.save or "error" not in result:
        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"reports/keyword_{args.keyword}_{timestamp}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n  📁 저장: {path}")


if __name__ == "__main__":
    main()
