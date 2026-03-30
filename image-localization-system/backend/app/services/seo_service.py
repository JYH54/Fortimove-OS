"""
SEO 메타데이터 생성 서비스
"""
import logging
from typing import List
from anthropic import Anthropic

from app.core.config import settings
from app.models.schemas import SEOMetadata, TranslationResult

logger = logging.getLogger(__name__)


class SEOService:
    """SEO 메타데이터 자동 생성 서비스"""

    def __init__(self):
        """Anthropic Claude 클라이언트 초기화"""
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def generate_seo_metadata(
        self,
        translations: List[TranslationResult],
        product_name: str | None,
        brand_type: str
    ) -> SEOMetadata:
        """
        SEO 메타데이터 생성

        Args:
            translations: 번역 결과 리스트
            product_name: 원본 상품명
            brand_type: 브랜드 타입

        Returns:
            SEO 메타데이터
        """
        try:
            # 번역된 텍스트 추출
            translated_texts = [t.translated for t in translations]

            # SEO 생성 프롬프트
            prompt = self._build_seo_prompt(
                translated_texts,
                product_name,
                brand_type
            )

            # Claude API 호출
            message = self.client.messages.create(
                model=settings.TRANSLATION_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            # 응답 파싱
            response_text = message.content[0].text
            seo_metadata = self._parse_seo_response(response_text)

            logger.info("SEO 메타데이터 생성 완료")
            return seo_metadata

        except Exception as e:
            logger.error(f"SEO 생성 실패: {str(e)}")
            # 실패 시 기본값 반환
            return SEOMetadata(
                product_names=["상품명 생성 실패"],
                search_tags=["태그1", "태그2"],
                options=[],
                keywords=["키워드1"]
            )

    def _build_seo_prompt(
        self,
        translated_texts: List[str],
        product_name: str | None,
        brand_type: str
    ) -> str:
        """SEO 생성 프롬프트"""

        tone = "프리미엄하고 세련된" if brand_type == "fortimove" else "실용적이고 명확한"

        texts_joined = ", ".join(translated_texts)
        product_info = f"원본 상품명: {product_name}\n" if product_name else ""

        prompt = f"""당신은 네이버 스마트스토어 SEO 전문가입니다.
다음 상품 정보를 바탕으로 최적화된 메타데이터를 생성하세요.

{product_info}추출된 키워드: {texts_joined}

**브랜드 톤**: {tone}

**출력 요구사항**:

1. SEO 상품명 3안 (40자 이내, 네이버 검색 최적화)
   - 안1: [카테고리] + [핵심 USP] + [세부 스펙]
   - 안2: [브랜드 톤] + [기능 강조] + [스펙]
   - 안3: [감성 키워드] + [실용성] + [구성]

2. 검색 태그 10개 (연관 키워드, 쉼표로 구분)

3. 옵션명 정규화 (색상/사이즈 한글 변환, JSON 형식)

4. 핵심 키워드 5개 (쿠팡 검색광고용, 쉼표로 구분)

**제약사항**:
- 타사 브랜드명 사용 금지
- 과장 광고 배제
- 의료기기 오인 문구 차단

**출력 형식** (정확히 이 형식으로):
상품명1: [텍스트]
상품명2: [텍스트]
상품명3: [텍스트]
태그: [태그1, 태그2, ...]
옵션: [{"원본": "蓝色", "정규화": "블루"}, ...]
키워드: [키워드1, 키워드2, ...]
"""
        return prompt

    def _parse_seo_response(self, response: str) -> SEOMetadata:
        """SEO 응답 파싱"""
        lines = response.strip().split('\n')

        product_names = []
        search_tags = []
        options = []
        keywords = []

        for line in lines:
            line = line.strip()

            if line.startswith('상품명'):
                # "상품명1: 텍스트" -> "텍스트"
                if ':' in line:
                    product_names.append(line.split(':', 1)[1].strip())

            elif line.startswith('태그:'):
                # "태그: 태그1, 태그2, ..." -> ["태그1", "태그2", ...]
                tags_str = line.split(':', 1)[1].strip()
                search_tags = [t.strip() for t in tags_str.split(',')]

            elif line.startswith('옵션:'):
                # 간단한 파싱 (실제로는 JSON 파싱)
                options = []  # TODO: JSON 파싱

            elif line.startswith('키워드:'):
                # "키워드: 키워드1, 키워드2, ..." -> ["키워드1", "키워드2", ...]
                keywords_str = line.split(':', 1)[1].strip()
                keywords = [k.strip() for k in keywords_str.split(',')]

        # 기본값 처리
        if not product_names:
            product_names = ["상품명 생성 실패"]
        if not search_tags:
            search_tags = ["태그생성실패"]
        if not keywords:
            keywords = ["키워드생성실패"]

        return SEOMetadata(
            product_names=product_names[:3],
            search_tags=search_tags[:10],
            options=options,
            keywords=keywords[:5]
        )
