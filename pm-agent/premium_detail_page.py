"""
초퀄리티 상세페이지 생성기
==========================
1개 상품 → 바로 판매 가능한 수준의 상세페이지 + 광고 전략

기존 detail_page_strategist.py 대비 개선:
- 단일 LLM 호출로 전체 맥락 유지 (6~7회 → 1~2회)
- 경쟁 분석 관점 포함
- 네이버 SEO 키워드 전략 내장
- 이미지 배치 가이드 포함
- 컴플라이언스 자동 치환 강화
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class ComplianceFilter:
    """컴플라이언스 자동 치환 — 상세페이지 전용"""

    REPLACEMENTS = {
        # 의료 효능 → 안전한 표현
        "치료": "케어", "완치": "관리", "진단": "체크",
        "개선": "도움", "회복": "서포트", "예방": "관리",
        "효과": "서포트", "약효": "특징",
        "질병": "일상적 불편함", "증상": "상태",
        # 과장 → 절제된 표현
        "100%": "높은 수준의", "완벽": "우수한",
        "최고": "프리미엄", "반드시": "권장",
        "기적": "주목받는", "혁명": "혁신적인",
        "절대": "매우", "무조건": "대부분",
        # 의약품 오인
        "처방": "추천", "복용": "섭취", "투약": "사용",
    }

    BLOCKED = [
        "의료기기", "치료기", "의약품", "질병 치료",
        "효과 보장", "부작용 없는", "FDA 승인"
    ]

    @classmethod
    def clean(cls, text: str) -> tuple:
        if not text:
            return text, []
        warnings = []
        cleaned = text

        for blocked in cls.BLOCKED:
            if blocked in cleaned:
                warnings.append(f"차단: '{blocked}' 제거됨")
                cleaned = cleaned.replace(blocked, "")

        for old, new in cls.REPLACEMENTS.items():
            if old in cleaned:
                warnings.append(f"치환: '{old}' → '{new}'")
                cleaned = cleaned.replace(old, new)

        return cleaned, warnings


class PremiumDetailPageGenerator:
    """
    단일 상품에 대한 초퀄리티 상세페이지 생성

    출력:
    - 네이버 스마트스토어 상세페이지 (HTML-ready)
    - 쿠팡 상세페이지
    - SEO 키워드 + 태그
    - 이미지 배치 가이드
    - 네이버 쇼핑 검색광고 키워드 + 카피
    """

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 필요")
        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        self.compliance = ComplianceFilter()

        # LLM 캐시
        try:
            from cache_manager import LLMCache
            self.cache = LLMCache()
        except Exception:
            self.cache = None

    def generate(
        self,
        title: str,
        price_krw: int,
        category: str = "general",
        description: str = "",
        target_customer: str = "",
        key_features: List[str] = None,
        competitors: List[str] = None,
        margin_rate: float = 0,
        source_country: str = "CN",
    ) -> Dict:
        """
        전체 상세페이지 + 광고 전략 한 번에 생성

        Args:
            title: 상품명 (중국어/영어/일본어/한국어)
            price_krw: 판매가 (원)
            category: 카테고리
            description: 상품 설명
            target_customer: 타겟 고객 (예: "30대 직장인 여성")
            key_features: 주요 특징 리스트
            competitors: 경쟁 상품명 (있으면 차별화 전략 포함)
            margin_rate: 마진율 (광고비 책정에 사용)
        """

        from country_config import get_country
        country = get_country(source_country)
        country_name = country.name_ko if country else "중국"
        origin_label = country.origin_trust_label if country else ""

        # 캐시 조회
        if self.cache:
            cached = self.cache.get("premium", title, category=category, country=source_country)
            if cached:
                logger.info(f"캐시 히트: {title[:30]} — API 호출 생략")
                return cached

        features_text = "\n".join(f"- {f}" for f in (key_features or []))
        competitors_text = ", ".join(competitors) if competitors else "정보 없음"

        prompt = f"""당신은 한국 이커머스 매출 1위를 만들어내는 전문 상세페이지 기획자 + 광고 전략가입니다.

아래 상품 정보를 바탕으로, **바로 판매 가능한 수준**의 초퀄리티 상세페이지와 광고 전략을 생성하세요.

═══════════════════════════════════════════
상품 정보
═══════════════════════════════════════════
- 상품명: {title}
- 판매가: ₩{price_krw:,}
- 카테고리: {category}
- 소싱 국가: {country_name}
- 원산지 신뢰 표기: "{origin_label}"
- 설명: {description or "미제공"}
- 타겟 고객: {target_customer or "건강/웰니스에 관심 있는 30~40대"}
- 주요 특징:
{features_text or "- 미제공"}
- 경쟁 상품: {competitors_text}
- 마진율: {margin_rate:.1f}%

중요: 상세페이지에 원산지({country_name}) 신뢰 포인트를 자연스럽게 녹여내세요.
- 미국산: "FDA 등록 시설", "미국 GMP 인증" 등 프리미엄 신뢰감
- 일본산: "일본 후생노동성 기준", "Made in Japan 품질" 등
- 중국산: "Fortimove 전문가 직접 검수", "품질 보증" 으로 신뢰 보완
- 베트남산: "현지 직거래 공정 가격", "신선한 원료" 등

═══════════════════════════════════════════
생성 요구사항
═══════════════════════════════════════════

1. **상품명 (SEO 최적화, 3안)**
   - 네이버 스마트스토어용 (50자 이내, 핵심 키워드 앞배치)
   - 쿠팡용 (100자 이내, [오늘출발] 태그 포함)
   - 검색 키워드 밀도 최적화

2. **후크 카피 (5개)**
   - 상세페이지 상단, 3초 안에 시선을 붙잡는 문구
   - 15~25자, 타겟 고객의 문제를 건드리는 표현
   - 의료 효능 표현 절대 금지

3. **상세페이지 본문 (네이버용)**
   구조:
   - [섹션1] 후크 카피 + 히어로 이미지 설명
   - [섹션2] "이런 분들께 추천합니다" (문제 공감 3가지)
   - [섹션3] 핵심 혜택 5가지 (아이콘 + 설명)
   - [섹션4] 제품 스토리 (문제→해결→결과, 200~300자)
   - [섹션5] 상세 스펙 / 성분표 / 제품 구성
   - [섹션6] 사용법 + 주의사항
   - [섹션7] FAQ (5개, 구매 장벽 제거)
   - [섹션8] 리뷰 유도 문구 + 구매 CTA
   각 섹션에 [이미지 가이드: 어떤 이미지를 넣어야 하는지] 포함

4. **상세페이지 본문 (쿠팡용)**
   - 네이버보다 간결하게 (모바일 최적화)
   - 핵심 혜택 3개 + 스토리 + 사용법

5. **SEO 전략**
   - 메인 키워드 3개 (검색량 높은 순)
   - 서브 키워드 7개 (롱테일)
   - 네이버 쇼핑 태그 10개
   - 제목에 포함해야 할 필수 키워드

6. **네이버 쇼핑 검색광고 전략**
   - 추천 키워드 10개 (예상 CPC 포함)
   - 광고 제목 3안 (25자 이내)
   - 광고 설명 3안 (45자 이내)
   - 일 예산 추천 (마진율 기반)
   - 추천 입찰가 범위

7. **경쟁 차별화 포인트**
   - 경쟁 상품 대비 강점 3가지
   - 가격 포지셔닝 전략 (프리미엄/가성비/중간)

═══════════════════════════════════════════
절대 준수 규칙
═══════════════════════════════════════════
- 의료 효능 표현 금지 (치료, 완치, 개선, 예방 → 케어, 서포트, 도움)
- 과장 금지 (100%, 최고, 기적, 혁명 → 프리미엄, 우수한, 검증된)
- 허위 보장 금지 (반드시, 무조건, 확실 → 권장, 대부분)
- "본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다" 반드시 포함

JSON으로만 응답하세요:
{{
  "product_titles": {{
    "smartstore": "네이버 제목",
    "coupang": "쿠팡 제목",
    "seo_optimized": "SEO 최적화 제목"
  }},
  "hook_copies": ["카피1", "카피2", "카피3", "카피4", "카피5"],
  "naver_detail_page": {{
    "sections": [
      {{
        "section_name": "섹션명",
        "content": "본문 내용",
        "image_guide": "어떤 이미지를 넣어야 하는지 설명"
      }}
    ]
  }},
  "coupang_detail_page": "쿠팡 상세페이지 전체 텍스트",
  "seo_strategy": {{
    "main_keywords": ["키워드1", "키워드2", "키워드3"],
    "sub_keywords": ["서브1", "서브2", ...],
    "shopping_tags": ["태그1", "태그2", ...],
    "title_must_include": ["필수키워드1", "필수키워드2"]
  }},
  "ad_strategy": {{
    "keywords": [
      {{"keyword": "키워드", "estimated_cpc": 500, "competition": "높음/중간/낮음"}}
    ],
    "ad_titles": ["광고제목1", "광고제목2", "광고제목3"],
    "ad_descriptions": ["광고설명1", "광고설명2", "광고설명3"],
    "daily_budget_krw": 10000,
    "bid_range_krw": [200, 800]
  }},
  "competitive_edge": {{
    "strengths": ["강점1", "강점2", "강점3"],
    "price_positioning": "프리미엄/가성비/중간",
    "differentiation_summary": "차별화 요약 2줄"
  }},
  "faq": [
    {{"q": "질문", "a": "답변"}}
  ]
}}"""

        logger.info(f"초퀄리티 상세페이지 생성 시작: {title}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        # JSON 추출
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패, raw 응답 반환")
            return {"error": "JSON 파싱 실패", "raw_response": content[:2000]}

        # 컴플라이언스 필터 적용
        warnings = []

        # 네이버 상세페이지 필터
        if "naver_detail_page" in result and "sections" in result["naver_detail_page"]:
            for section in result["naver_detail_page"]["sections"]:
                cleaned, w = self.compliance.clean(section.get("content", ""))
                section["content"] = cleaned
                warnings.extend(w)

        # 쿠팡 상세페이지 필터
        if "coupang_detail_page" in result:
            cleaned, w = self.compliance.clean(result["coupang_detail_page"])
            result["coupang_detail_page"] = cleaned
            warnings.extend(w)

        result["compliance_warnings"] = list(set(warnings))
        result["generated_at"] = datetime.now().isoformat()

        # 캐시 저장
        if self.cache and "error" not in result:
            self.cache.set("premium", title, result, tokens_used=8000, category=category, country=source_country)

        logger.info(f"초퀄리티 상세페이지 생성 완료 (경고 {len(warnings)}건)")
        return result

    def render_naver_text(self, result: Dict) -> str:
        """네이버 상세페이지를 텍스트로 렌더링 (복사 붙여넣기용)"""
        if "error" in result:
            return f"오류: {result['error']}"

        lines = []
        titles = result.get("product_titles", {})
        lines.append(f"━━━ 상품명 ━━━")
        lines.append(f"스마트스토어: {titles.get('smartstore', '')}")
        lines.append(f"쿠팡: {titles.get('coupang', '')}")
        lines.append(f"")

        hooks = result.get("hook_copies", [])
        if hooks:
            lines.append(f"━━━ 후크 카피 ━━━")
            for h in hooks:
                lines.append(f"▸ {h}")
            lines.append(f"")

        naver = result.get("naver_detail_page", {})
        for section in naver.get("sections", []):
            lines.append(f"━━━ {section.get('section_name', '')} ━━━")
            lines.append(section.get("content", ""))
            if section.get("image_guide"):
                lines.append(f"  📷 이미지: {section['image_guide']}")
            lines.append(f"")

        faq = result.get("faq", [])
        if faq:
            lines.append(f"━━━ FAQ ━━━")
            for item in faq:
                lines.append(f"Q. {item.get('q', '')}")
                lines.append(f"A. {item.get('a', '')}")
                lines.append(f"")

        return "\n".join(lines)

    def render_ad_strategy(self, result: Dict) -> str:
        """광고 전략을 텍스트로 렌더링"""
        if "error" in result:
            return f"오류: {result['error']}"

        lines = []
        ad = result.get("ad_strategy", {})

        lines.append(f"━━━ 네이버 쇼핑 검색광고 전략 ━━━")
        lines.append(f"")
        lines.append(f"일 예산: ₩{ad.get('daily_budget_krw', 0):,}")
        bid = ad.get("bid_range_krw", [0, 0])
        lines.append(f"입찰가: ₩{bid[0]:,} ~ ₩{bid[1]:,}")
        lines.append(f"")

        lines.append(f"추천 키워드:")
        for kw in ad.get("keywords", []):
            lines.append(f"  • {kw.get('keyword', '')} — CPC ₩{kw.get('estimated_cpc', 0):,} ({kw.get('competition', '')})")
        lines.append(f"")

        lines.append(f"광고 제목:")
        for t in ad.get("ad_titles", []):
            lines.append(f"  ▸ {t}")
        lines.append(f"")

        lines.append(f"광고 설명:")
        for d in ad.get("ad_descriptions", []):
            lines.append(f"  ▸ {d}")

        seo = result.get("seo_strategy", {})
        lines.append(f"")
        lines.append(f"━━━ SEO 전략 ━━━")
        lines.append(f"메인 키워드: {', '.join(seo.get('main_keywords', []))}")
        lines.append(f"서브 키워드: {', '.join(seo.get('sub_keywords', []))}")
        lines.append(f"쇼핑 태그: {', '.join(seo.get('shopping_tags', []))}")

        edge = result.get("competitive_edge", {})
        if edge:
            lines.append(f"")
            lines.append(f"━━━ 경쟁 차별화 ━━━")
            lines.append(f"포지셔닝: {edge.get('price_positioning', '')}")
            for s in edge.get("strengths", []):
                lines.append(f"  ✓ {s}")
            lines.append(f"{edge.get('differentiation_summary', '')}")

        return "\n".join(lines)


if __name__ == "__main__":
    gen = PremiumDetailPageGenerator()
    result = gen.generate(
        title="콜라겐 펩타이드 분말 100g 저분자 피쉬콜라겐",
        price_krw=29900,
        category="wellness",
        description="어류 추출 저분자 콜라겐 펩타이드, 흡수율 높은 분말 타입",
        target_customer="피부 탄력이 신경 쓰이는 30~40대 여성",
        key_features=[
            "저분자 피쉬 콜라겐 (1000 달톤 이하)",
            "무맛 무취 분말 — 음료에 타서 섭취",
            "100g 대용량 (약 2개월분)",
            "GMP 인증 시설 생산"
        ],
        competitors=["닥터린 콜라겐", "뉴트리디데이 콜라겐"],
        margin_rate=32.5
    )

    print(gen.render_naver_text(result))
    print("\n" + "="*60 + "\n")
    print(gen.render_ad_strategy(result))
