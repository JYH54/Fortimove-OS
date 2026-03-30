"""
리스크 탐지 서비스 (유아, 인물, 로고)
"""
import logging
from typing import List
import numpy as np
from PIL import Image
import cv2
from transformers import CLIPProcessor, CLIPModel
import torch

from app.core.config import settings
from app.models.schemas import RiskDetection, RiskType

logger = logging.getLogger(__name__)


class RiskDetectionService:
    """이미지 리스크 탐지 서비스"""

    def __init__(self):
        """CLIP 모델 및 Face Detection 초기화"""
        # CLIP 모델 로드
        self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

        # Face Detection (OpenCV Haar Cascade)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    async def detect_risks(
        self,
        image: Image.Image
    ) -> List[RiskDetection]:
        """
        이미지에서 리스크 요소 탐지

        Args:
            image: PIL Image 객체

        Returns:
            리스크 탐지 결과 리스트
        """
        risks = []

        # 1. 유아 이미지 탐지
        infant_risks = await self._detect_infant(image)
        risks.extend(infant_risks)

        # 2. 인물 얼굴 탐지
        face_risks = await self._detect_faces(image)
        risks.extend(face_risks)

        # 3. 브랜드 로고 탐지 (간단한 OCR 기반)
        logo_risks = await self._detect_brand_logos(image)
        risks.extend(logo_risks)

        logger.info(f"리스크 탐지 완료: {len(risks)}개")
        return risks

    async def _detect_infant(self, image: Image.Image) -> List[RiskDetection]:
        """CLIP 모델로 유아 이미지 탐지"""
        try:
            # CLIP 입력 준비
            inputs = self.clip_processor(
                text=["a baby", "an infant", "a toddler", "a child under 3 years old"],
                images=image,
                return_tensors="pt",
                padding=True
            )

            # CLIP 모델 실행
            with torch.no_grad():
                outputs = self.clip_model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1)

            # 최대 확률 확인
            max_prob = probs.max().item()

            if max_prob > settings.INFANT_DETECTION_THRESHOLD:
                return [RiskDetection(
                    risk_type=RiskType.INFANT,
                    confidence=round(max_prob, 3),
                    position=None,  # 전체 이미지
                    description=f"유아 이미지 감지됨 (신뢰도: {max_prob:.1%})"
                )]

            return []

        except Exception as e:
            logger.error(f"유아 탐지 실패: {str(e)}")
            return []

    async def _detect_faces(self, image: Image.Image) -> List[RiskDetection]:
        """OpenCV로 얼굴 탐지"""
        try:
            # PIL -> OpenCV 변환
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

            # 얼굴 탐지
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )

            risks = []
            for (x, y, w, h) in faces:
                risk = RiskDetection(
                    risk_type=RiskType.PERSON,
                    confidence=0.9,  # OpenCV는 신뢰도 제공 안 함
                    position={"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                    description=f"인물 얼굴 감지됨 (위치: x={x}, y={y})"
                )
                risks.append(risk)

            return risks

        except Exception as e:
            logger.error(f"얼굴 탐지 실패: {str(e)}")
            return []

    async def _detect_brand_logos(self, image: Image.Image) -> List[RiskDetection]:
        """간단한 텍스트 기반 브랜드 로고 탐지"""
        # TODO: 실제로는 OCR + 브랜드 DB 매칭 필요
        # 현재는 placeholder
        return []
