"""
API 스키마 정의
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MoodTone(str, Enum):
    """무드톤 타입"""
    PREMIUM = "premium"
    VALUE = "value"
    MINIMAL = "minimal"
    TRENDY = "trendy"


class BrandType(str, Enum):
    """브랜드 타입"""
    FORTIMOVE_GLOBAL = "fortimove_global"
    FORTIMOVE = "fortimove"


class JobStatus(str, Enum):
    """작업 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskType(str, Enum):
    """리스크 타입"""
    INFANT = "infant"
    PERSON = "person"
    BRAND_LOGO = "brand_logo"
    MEDICAL_CLAIM = "medical_claim"


# === 요청 스키마 ===

class ImageProcessingRequest(BaseModel):
    """이미지 처리 요청"""
    moodtone: MoodTone = Field(..., description="무드톤 (프리미엄/가성비/미니멀/트렌디)")
    brand_type: BrandType = Field(default=BrandType.FORTIMOVE_GLOBAL, description="브랜드 타입")
    product_name: Optional[str] = Field(None, description="원본 상품명 (중국어)")
    generate_seo: bool = Field(default=True, description="SEO 메타데이터 자동 생성 여부")
    auto_replace_risks: bool = Field(default=True, description="리스크 이미지 자동 대체 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "moodtone": "premium",
                "brand_type": "fortimove_global",
                "product_name": "超强吸水速干毛巾",
                "generate_seo": True,
                "auto_replace_risks": True
            }
        }


# === 응답 스키마 ===

class OCRResult(BaseModel):
    """OCR 추출 결과"""
    text: str
    confidence: float
    position: dict[str, int]  # {x, y, width, height}
    language: str


class TranslationResult(BaseModel):
    """번역 결과"""
    original: str
    translated: str
    position: dict[str, int]


class RiskDetection(BaseModel):
    """리스크 탐지 결과"""
    risk_type: RiskType
    confidence: float
    position: Optional[dict[str, int]] = None
    description: str


class RiskProcessing(BaseModel):
    """리스크 처리 결과"""
    risk_type: RiskType
    action: str  # deleted, replaced, masked
    details: str


class SEOMetadata(BaseModel):
    """SEO 메타데이터"""
    product_names: List[str] = Field(..., description="상품명 3안")
    search_tags: List[str] = Field(..., description="검색 태그 10개")
    options: List[dict[str, str]] = Field(..., description="옵션명 정규화")
    keywords: List[str] = Field(..., description="핵심 키워드 5개")


class ProcessedImage(BaseModel):
    """재가공된 이미지 정보"""
    original_filename: str
    processed_filename: str
    download_url: HttpUrl
    width: int
    height: int
    file_size_bytes: int


class ImageAnalysisReport(BaseModel):
    """이미지 분석 리포트"""
    ocr_results: List[OCRResult]
    translations: List[TranslationResult]
    risks_detected: List[RiskDetection]
    risks_processed: List[RiskProcessing]


class JobResponse(BaseModel):
    """작업 응답"""
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime

    # 처리 완료 시 포함
    processed_images: Optional[List[ProcessedImage]] = None
    analysis_report: Optional[ImageAnalysisReport] = None
    seo_metadata: Optional[SEOMetadata] = None
    error_message: Optional[str] = None

    processing_time_seconds: Optional[float] = None


class JobListResponse(BaseModel):
    """작업 목록 응답"""
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


# === 데이터베이스 모델 ===

class JobCreate(BaseModel):
    """작업 생성"""
    moodtone: MoodTone
    brand_type: BrandType
    product_name: Optional[str]
    generate_seo: bool
    auto_replace_risks: bool
    user_id: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """헬스체크 응답"""
    status: str
    version: str
    timestamp: datetime
    services: dict[str, str]  # {service_name: status}
