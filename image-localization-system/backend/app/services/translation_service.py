"""
AI 번역 서비스 (멀티 API: Gemini Flash 우선, Claude 폴백)
"""
import logging
import os
from typing import List, Optional

from app.core.config import settings
from app.models.schemas import OCRResult, TranslationResult

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyD6chNQ-Nb8CcX1fqaegdv2Z-sKEnRhWfE")
LLM_PROVIDER = os.getenv("TRANSLATION_LLM_PROVIDER", "gemini")  # gemini 또는 claude


class TranslationService:
    """AI 기반 이커머스 번역 서비스 (Gemini Flash 우선)"""

    def __init__(self):
        self.provider = LLM_PROVIDER
        self._gemini_client = None
        self._claude_client = None

        if self.provider == "gemini" and GOOGLE_API_KEY:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
                self.model = "gemini-2.5-flash"
                logger.info(f"번역 서비스: Gemini Flash 사용")
            except Exception as e:
                logger.warning(f"Gemini 초기화 실패: {e}, Claude로 폴백")
                self.provider = "claude"

        if self.provider == "claude" or self._gemini_client is None:
            try:
                from anthropic import Anthropic
                self._claude_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                self.model = settings.TRANSLATION_MODEL
                self.provider = "claude"
                logger.info(f"번역 서비스: Claude 사용")
            except Exception:
                logger.warning("Claude 초기화 실패")

    def _call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """Gemini 또는 Claude로 LLM 호출"""
        if self._gemini_client:
            try:
                from google.genai import types
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.3,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                return response.text or ""
            except Exception as e:
                logger.warning(f"Gemini 호출 실패: {e}, Claude 폴백")

        if self._claude_client:
            message = self._claude_client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        raise RuntimeError("사용 가능한 LLM 없음")

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

            # LLM 호출 (Gemini Flash 또는 Claude)
            response_text = self._call_llm(prompt, max_tokens=settings.TRANSLATION_MAX_TOKENS)
            translations = self._parse_translation_response(
                response_text,
                chinese_texts
            )

            logger.info(f"번역 완료: {len(translations)}개")
            return translations

        except Exception as e:
            logger.error(f"번역 실패: {str(e)}")
            # API 오류 시 모의 번역 반환 (임시)
            logger.warning("⚠️ AI 번역 실패 - 기본 번역으로 대체")
            return self._create_fallback_translations(ocr_results)

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

    def _create_fallback_translations(
        self,
        ocr_results: List[OCRResult]
    ) -> List[TranslationResult]:
        """AI 번역 실패 시 기본 번역 반환"""

        # 간단한 키워드 매핑 (실제로는 더 정교한 번역 필요)
        keyword_map = {
            "优质": "고품질",
            "天然": "천연",
            "健康": "건강",
            "环保": "친환경",
            "安全": "안전",
            "舒适": "편안한",
            "时尚": "트렌디",
            "实惠": "가성비 좋은",
            "品质": "품질",
            "保证": "보장",
        }

        translations = []
        for ocr in ocr_results:
            # 키워드 매칭 시도
            translated = ocr.text
            for cn, kr in keyword_map.items():
                if cn in ocr.text:
                    translated = kr
                    break

            # 매칭 실패 시 원문에 [번역필요] 태그
            if translated == ocr.text:
                translated = f"[상품 설명] {ocr.text[:20]}..."

            translation = TranslationResult(
                original=ocr.text,
                translated=translated,
                position=ocr.position
            )
            translations.append(translation)

        logger.info(f"기본 번역 생성: {len(translations)}개")
        return translations
