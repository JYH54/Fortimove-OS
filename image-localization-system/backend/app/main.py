"""
FastAPI 메인 애플리케이션
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import uuid
from datetime import datetime

from app.core.config import settings
from app.models.schemas import (
    ImageProcessingRequest,
    JobResponse,
    JobStatus,
    HealthCheckResponse
)
from app.services.ocr_service import OCRService
from app.services.translation_service import TranslationService
from app.services.risk_detection_service import RiskDetectionService
from app.services.image_processing_service import ImageProcessingService
from app.services.seo_service import SEOService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 서비스 인스턴스 (싱글톤)
ocr_service = None
translation_service = None
risk_detection_service = None
image_processing_service = None
seo_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 이벤트"""
    global ocr_service, translation_service, risk_detection_service
    global image_processing_service, seo_service

    # 시작 시 서비스 초기화
    logger.info("서비스 초기화 중...")
    ocr_service = OCRService()
    translation_service = TranslationService()
    risk_detection_service = RiskDetectionService()
    image_processing_service = ImageProcessingService()
    seo_service = SEOService()
    logger.info("서비스 초기화 완료")

    yield

    # 종료 시 정리
    logger.info("애플리케이션 종료")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "Fortimove Image Localization API", "version": settings.APP_VERSION}


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """헬스체크"""
    return HealthCheckResponse(
        status="healthy",
        version=settings.APP_VERSION,
        timestamp=datetime.utcnow(),
        services={
            "ocr": "ready" if ocr_service else "not_initialized",
            "translation": "ready" if translation_service else "not_initialized",
            "risk_detection": "ready" if risk_detection_service else "not_initialized",
            "image_processing": "ready" if image_processing_service else "not_initialized",
            "seo": "ready" if seo_service else "not_initialized",
        }
    )


@app.post(f"{settings.API_V1_PREFIX}/process", response_model=JobResponse)
async def process_images(
    files: List[UploadFile] = File(..., description="이미지 파일 (최대 20개)"),
    moodtone: str = Form(..., description="무드톤 (premium/value/minimal/trendy)"),
    brand_type: str = Form(default="fortimove_global", description="브랜드 타입"),
    product_name: str = Form(default=None, description="원본 상품명 (중국어, 선택)"),
    generate_seo: bool = Form(default=True, description="SEO 메타데이터 생성 여부"),
    auto_replace_risks: bool = Form(default=True, description="리스크 자동 대체 여부"),
):
    """
    이미지 현지화 처리

    **처리 과정**:
    1. OCR로 중국어 텍스트 추출
    2. AI 번역 (Claude)
    3. 리스크 탐지 (유아/인물/로고)
    4. 리스크 자동 처리
    5. 무드톤 조정
    6. 한국어 텍스트 오버레이
    7. SEO 메타데이터 생성
    """
    # 파일 개수 제한
    if len(files) > settings.MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"최대 {settings.MAX_UPLOAD_FILES}개 파일만 업로드 가능합니다."
        )

    # Job ID 생성
    job_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    try:
        # 동기 처리 (프로덕션에서는 Celery 비동기 사용)
        from PIL import Image
        import io

        processed_images_list = []
        all_ocr_results = []
        all_translations = []
        all_risks = []
        all_risk_processings = []

        for file in files:
            # 이미지 로드
            content = await file.read()
            image = Image.open(io.BytesIO(content))

            # 1. OCR
            ocr_results = await ocr_service.extract_text(image)
            all_ocr_results.extend(ocr_results)

            # 2. 번역
            translations = await translation_service.translate_texts(ocr_results, brand_type)
            all_translations.extend(translations)

            # 3. 리스크 탐지
            risks = await risk_detection_service.detect_risks(image)
            all_risks.extend(risks)

            # 4. 이미지 재가공
            processed_image, risk_processings = await image_processing_service.process_image(
                image,
                translations,
                risks,
                moodtone,
                auto_replace_risks
            )
            all_risk_processings.extend(risk_processings)

            # 5. 이미지 저장 (임시, 프로덕션에서는 S3)
            output_filename = f"{job_id}_{file.filename}"
            # TODO: S3 업로드

            processed_images_list.append({
                "original_filename": file.filename,
                "processed_filename": output_filename,
                "download_url": f"http://localhost:8000/downloads/{output_filename}",
                "width": processed_image.width,
                "height": processed_image.height,
                "file_size_bytes": 0  # TODO
            })

        # 6. SEO 생성
        seo_metadata = None
        if generate_seo and all_translations:
            seo_metadata = await seo_service.generate_seo_metadata(
                all_translations,
                product_name,
                brand_type
            )

        # 처리 시간 계산
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        # 응답 생성
        from app.models.schemas import ProcessedImage, ImageAnalysisReport

        return JobResponse(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            created_at=start_time,
            updated_at=end_time,
            processed_images=[ProcessedImage(**img) for img in processed_images_list],
            analysis_report=ImageAnalysisReport(
                ocr_results=all_ocr_results,
                translations=all_translations,
                risks_detected=all_risks,
                risks_processed=all_risk_processings
            ),
            seo_metadata=seo_metadata,
            processing_time_seconds=processing_time
        )

    except Exception as e:
        logger.error(f"이미지 처리 실패: {str(e)}")
        return JobResponse(
            job_id=job_id,
            status=JobStatus.FAILED,
            created_at=start_time,
            updated_at=datetime.utcnow(),
            error_message=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
