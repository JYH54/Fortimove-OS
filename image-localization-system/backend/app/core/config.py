"""
프로덕션 환경 설정
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # 앱 기본 설정
    APP_NAME: str = "Fortimove Image Localization API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API 설정
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "https://fortimove.com"]

    # 데이터베이스
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # Redis (캐시 및 Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # AI API Keys
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_CLOUD_VISION_API_KEY: Optional[str] = None

    # 스토리지
    STORAGE_PROVIDER: str = "s3"  # s3, gcs, local
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "ap-northeast-2"

    # Google Cloud Storage
    GCS_BUCKET: Optional[str] = None
    GCS_CREDENTIALS_PATH: Optional[str] = None

    # 로컬 스토리지
    LOCAL_STORAGE_PATH: str = "/tmp/fortimove-images"

    # 이미지 처리 설정
    MAX_IMAGE_SIZE_MB: int = 20
    SUPPORTED_IMAGE_FORMATS: list[str] = ["jpg", "jpeg", "png", "webp"]
    OUTPUT_IMAGE_WIDTH: int = 1200
    OUTPUT_IMAGE_QUALITY: int = 85

    # OCR 설정
    OCR_ENGINE: str = "easyocr"  # tesseract, easyocr, google_vision
    OCR_LANGUAGES: list[str] = ["ch_sim", "ch_tra", "en"]
    OCR_CONFIDENCE_THRESHOLD: float = 0.6

    # AI 번역 설정
    TRANSLATION_MODEL: str = "claude-3-5-sonnet-20241022"
    TRANSLATION_MAX_TOKENS: int = 2000

    # 리스크 탐지 설정
    RISK_DETECTION_MODEL: str = "clip"  # clip, custom
    INFANT_DETECTION_THRESHOLD: float = 0.7
    FACE_DETECTION_CONFIDENCE: float = 0.8

    # 이미지 생성 설정
    IMAGE_GENERATION_PROVIDER: str = "stability"  # stability, openai, replicate
    STABILITY_API_KEY: Optional[str] = None
    REPLICATE_API_TOKEN: Optional[str] = None

    # 작업 큐 설정
    MAX_CONCURRENT_JOBS: int = 5
    JOB_TIMEOUT_SECONDS: int = 600

    # 모니터링
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = True

    # 보안
    MAX_UPLOAD_FILES: int = 20
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
