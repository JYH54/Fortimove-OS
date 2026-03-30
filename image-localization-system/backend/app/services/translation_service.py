"""
AI 번역 서비스
"""
import logging
from typing import List
from anthropic import Anthropic

from app.core.config import settings
from app.models.schemas import OCRResult, TranslationResult

logger = logging.getLogger(__name__)


class TranslationService:
    """AI 기반 이커머스 번역 서비스"""

    def __init__(self):
        """Anthropic Claude 클라이언트 초기화"""
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.TRANSLATION_MODEL

    async def translate_texts(
        self,
        ocr_results: List[OCRResult],
        brand_type: str
    ) -> List[TranslationResult]:
        """
        OCR 추출 텍스트를 한국어로 번역

        Args:
            ocr_results: OCR 결과 리스트
            brand_type: 브랜드 타입 (fortimove_global, fortimove)

        Returns:
            번역 결과 리스트
        """
        if not ocr_results:
            return []

        try:
            # 중국어 텍스트만 필터링
            chinese_texts = [
                ocr for ocr in ocr_results
                if ocr.language in ["zh", "mixed"]
            ]

            if not chinese_texts:
                logger.info("번역할 중국어 텍스트 없음")
                return []

            # 번역 프롬프트 생성
            prompt = self._build_translation_prompt(chinese_texts, brand_type)

            # Claude API 호출
            message = self.client.messages.create(
                model=self.model,
                max_tokens=settings.TRANSLATION_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            # 응답 파싱
            response_text = message.content[0].text
            translations = self._parse_translation_response(
                response_text,
                chinese_texts
            )

            logger.info(f"번역 완료: {len(translations)}개")
            return translations

        except Exception as e:
            logger.error(f"번역 실패: {str(e)}")
            raise

    def _build_translation_prompt(
        self,
        ocr_results: List[OCRResult],
        brand_type: str
    ) -> str:
        """번역 프롬프트 생성"""

        # 브랜드별 톤 설정
        tone = "프리미엄하고 세련된" if brand_type == "fortimove" else "실용적이고 명확한"

        texts_list = "\n".join([
            f"{i+1}. {ocr.text}"
            for i, ocr in enumerate(ocr_results)
        ])

        prompt = f"""다음 중국어 이커머스 상품 문구를 한국 네이버 스마트스토어/쿠팡에 최적화된 판매 문구로 번역하세요.

**번역 원칙**:
1. 과장 광고 배제 ("세계 최고" → "고품질")
2. 의료기기 오인 표방 차단 ("혈압 강하" → "일상 편안함", "치료" → "케어")
3. {tone} 어조로 작성
4. 자연스러운 한국어 어순 및 띄어쓰기
5. 유아/아기 관련 표현 → 중립적 표현으로 변환

**금지 단어**: 치료, 완치, 예방, 재생, 혈압, 혈당, 혈액순환, 관절염, 염증완화, 항암, 항균, 살균, 소독, 면역력, 치유, 회복, 개선효과, 질병, 증상완화, 宝宝专用, 婴儿, 幼儿

**번역할 텍스트**:
{texts_list}

**출력 형식** (각 줄마다):
1. [번역된 한국어 문구]
2. [번역된 한국어 문구]
...

번역된 문구만 출력하세요. 설명이나 부연 없이."""

        return prompt

    def _parse_translation_response(
        self,
        response: str,
        ocr_results: List[OCRResult]
    ) -> List[TranslationResult]:
        """번역 응답 파싱"""

        lines = [line.strip() for line in response.split('\n') if line.strip()]
        translations = []

        for i, ocr in enumerate(ocr_results):
            if i < len(lines):
                # 번호 제거 (예: "1. " 제거)
                translated = lines[i]
                if '. ' in translated:
                    translated = translated.split('. ', 1)[1]

                translation = TranslationResult(
                    original=ocr.text,
                    translated=translated,
                    position=ocr.position
                )
                translations.append(translation)

        return translations
