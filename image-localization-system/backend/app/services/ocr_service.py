"""
OCR 서비스 (텍스트 추출)
"""
import logging
from typing import List, Tuple
import numpy as np
from PIL import Image
import easyocr

from app.core.config import settings
from app.models.schemas import OCRResult

logger = logging.getLogger(__name__)


class OCRService:
    """OCR 텍스트 추출 서비스"""

    def __init__(self):
        """EasyOCR 리더 초기화"""
        self.reader = easyocr.Reader(
            settings.OCR_LANGUAGES,
            gpu=False,  # CPU 모드 (프로덕션에서는 GPU 권장)
            verbose=False
        )

    async def extract_text(
        self,
        image: Image.Image
    ) -> List[OCRResult]:
        """
        이미지에서 텍스트 추출

        Args:
            image: PIL Image 객체

        Returns:
            OCR 결과 리스트
        """
        try:
            # PIL Image를 numpy array로 변환
            image_array = np.array(image)

            # EasyOCR 실행
            results = self.reader.readtext(
                image_array,
                detail=1,
                paragraph=False
            )

            # 결과 변환
            ocr_results = []
            for bbox, text, confidence in results:
                # 신뢰도 필터링
                if confidence < settings.OCR_CONFIDENCE_THRESHOLD:
                    continue

                # Bounding box 좌표 추출
                (top_left, top_right, bottom_right, bottom_left) = bbox
                x = int(top_left[0])
                y = int(top_left[1])
                width = int(top_right[0] - top_left[0])
                height = int(bottom_left[1] - top_left[1])

                # 언어 감지 (간단한 휴리스틱)
                language = self._detect_language(text)

                ocr_result = OCRResult(
                    text=text.strip(),
                    confidence=round(confidence, 3),
                    position={"x": x, "y": y, "width": width, "height": height},
                    language=language
                )

                ocr_results.append(ocr_result)

            logger.info(f"OCR 추출 완료: {len(ocr_results)}개 텍스트 블록")
            return ocr_results

        except Exception as e:
            logger.error(f"OCR 추출 실패: {str(e)}")
            raise

    def _detect_language(self, text: str) -> str:
        """
        텍스트 언어 감지

        Args:
            text: 텍스트

        Returns:
            언어 코드 (zh, en, mixed)
        """
        # 중국어 문자 범위
        chinese_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_count = sum(1 for char in text if char.isascii() and char.isalpha())

        total = chinese_count + english_count
        if total == 0:
            return "unknown"

        chinese_ratio = chinese_count / total

        if chinese_ratio > 0.7:
            return "zh"
        elif chinese_ratio < 0.3:
            return "en"
        else:
            return "mixed"
