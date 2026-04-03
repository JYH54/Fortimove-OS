"""
이미지 재가공 서비스
"""
import logging
from typing import List, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2
from rembg import remove

from app.core.config import settings
from app.models.schemas import TranslationResult, RiskDetection, RiskProcessing, RiskType

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """이미지 재가공 및 편집 서비스"""

    def __init__(self):
        """폰트 로드"""
        # 무료 폰트 경로 (프로덕션에서는 실제 경로 사용)
        self.font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
        try:
            self.font = ImageFont.truetype(self.font_path, 32)
        except:
            logger.warning("폰트 로드 실패, 기본 폰트 사용")
            self.font = ImageFont.load_default()

    async def process_image(
        self,
        image: Image.Image,
        translations: List[TranslationResult],
        risks: List[RiskDetection],
        moodtone: str,
        auto_replace_risks: bool
    ) -> Tuple[Image.Image, List[RiskProcessing]]:
        """
        이미지 재가공

        Args:
            image: 원본 이미지
            translations: 번역 결과
            risks: 탐지된 리스크
            moodtone: 무드톤 (premium, value, minimal, trendy)
            auto_replace_risks: 리스크 자동 대체 여부

        Returns:
            (재가공 이미지, 리스크 처리 내역)
        """
        processed_image = image.copy()
        risk_processings = []

        # 1. 리스크 처리
        if auto_replace_risks:
            processed_image, risk_processings = await self._process_risks(
                processed_image,
                risks
            )

        # 2. 무드톤 조정
        processed_image = await self._adjust_moodtone(processed_image, moodtone)

        # 3. 텍스트 오버레이
        processed_image = await self._overlay_translations(
            processed_image,
            translations
        )

        # 4. 리사이즈 (네이버/쿠팡 최적화)
        processed_image = await self._resize_image(processed_image)

        return processed_image, risk_processings

    async def _process_risks(
        self,
        image: Image.Image,
        risks: List[RiskDetection]
    ) -> Tuple[Image.Image, List[RiskProcessing]]:
        """리스크 요소 처리"""
        processed_image = image.copy()
        processings = []

        for risk in risks:
            if risk.risk_type == RiskType.INFANT:
                # 유아 이미지 → 전체 삭제 (흰색으로 대체)
                processed_image = Image.new('RGB', image.size, 'white')
                processings.append(RiskProcessing(
                    risk_type=RiskType.INFANT,
                    action="deleted",
                    details="유아 이미지 전체 삭제 (플랫폼 정책 준수)"
                ))

            elif risk.risk_type == RiskType.PERSON and risk.position:
                # 얼굴 영역 → 블러 처리
                processed_image = self._blur_region(
                    processed_image,
                    risk.position
                )
                processings.append(RiskProcessing(
                    risk_type=RiskType.PERSON,
                    action="masked",
                    details=f"인물 얼굴 블러 처리 (위치: {risk.position})"
                ))

        return processed_image, processings

    def _blur_region(
        self,
        image: Image.Image,
        position: dict
    ) -> Image.Image:
        """특정 영역 블러 처리"""
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        x, y, w, h = position['x'], position['y'], position['width'], position['height']

        # 해당 영역만 가우시안 블러
        roi = img_cv[y:y+h, x:x+w]
        blurred_roi = cv2.GaussianBlur(roi, (99, 99), 30)
        img_cv[y:y+h, x:x+w] = blurred_roi

        # OpenCV -> PIL 변환
        img_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        return img_pil

    async def _adjust_moodtone(
        self,
        image: Image.Image,
        moodtone: str
    ) -> Image.Image:
        """무드톤 색감 조정"""
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        img_hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV).astype(np.float32)

        if moodtone == "premium":
            # 채도 -30%, 명도 +20%
            img_hsv[:, :, 1] *= 0.7
            img_hsv[:, :, 2] *= 1.2

        elif moodtone == "value":
            # 채도 +30%, 대비 강조
            img_hsv[:, :, 1] *= 1.3
            img_hsv[:, :, 2] *= 1.1

        elif moodtone == "minimal":
            # 채도 -50% (그레이스케일 느낌)
            img_hsv[:, :, 1] *= 0.5

        elif moodtone == "trendy":
            # 채도 +10%, 명도 +15%
            img_hsv[:, :, 1] *= 1.1
            img_hsv[:, :, 2] *= 1.15

        # 범위 제한
        img_hsv[:, :, 1] = np.clip(img_hsv[:, :, 1], 0, 255)
        img_hsv[:, :, 2] = np.clip(img_hsv[:, :, 2], 0, 255)

        img_hsv = img_hsv.astype(np.uint8)
        img_bgr = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        return Image.fromarray(img_rgb)

    async def _overlay_translations(
        self,
        image: Image.Image,
        translations: List[TranslationResult]
    ) -> Image.Image:
        """번역된 한국어 텍스트 오버레이"""
        draw = ImageDraw.Draw(image)

        for trans in translations:
            pos = trans.position
            x, y, w, h = pos['x'], pos['y'], pos['width'], pos['height']

            # 기존 텍스트 영역을 흰색으로 덮기
            draw.rectangle([x, y, x+w, y+h], fill='white')

            # 한국어 텍스트 삽입
            draw.text(
                (x, y),
                trans.translated,
                font=self.font,
                fill='black'
            )

        return image

    async def _resize_image(self, image: Image.Image) -> Image.Image:
        """이미지 리사이즈 (네이버/쿠팡 최적화)"""
        target_width = settings.OUTPUT_IMAGE_WIDTH

        # 가로가 target_width가 되도록 비율 유지하며 리사이즈
        ratio = target_width / image.width
        target_height = int(image.height * ratio)

        resized = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return resized
