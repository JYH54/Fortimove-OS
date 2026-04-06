"""
Celery 애플리케이션 및 비동기 태스크 정의
"""
import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

# Celery 앱 생성
celery = Celery(
    "fortimove_images",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)


@celery.task(bind=True, name="process_images_task", max_retries=2)
def process_images_task(self, job_id: str, file_paths: list, moodtone: str,
                        brand_type: str = "fortimove_global",
                        product_name: str = None,
                        generate_seo: bool = True,
                        auto_replace_risks: bool = True):
    """
    이미지 현지화 비동기 처리 태스크

    main.py의 동기 처리 로직을 Celery 워커에서 실행
    """
    from PIL import Image
    from app.core.config import settings
    from app.services.ocr_service import OCRService
    from app.services.translation_service import TranslationService
    from app.services.risk_detection_service import RiskDetectionService
    from app.services.image_processing_service import ImageProcessingService
    from app.services.seo_service import SEOService
    import asyncio

    logger.info(f"[{job_id}] 비동기 이미지 처리 시작 ({len(file_paths)}개)")

    ocr_svc = OCRService()
    translation_svc = TranslationService()
    risk_svc = RiskDetectionService()
    img_svc = ImageProcessingService()
    seo_svc = SEOService()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        results = []
        all_translations = []

        for file_path in file_paths:
            image = Image.open(file_path)

            # OCR
            ocr_results = loop.run_until_complete(ocr_svc.extract_text(image))

            # 번역
            translations = loop.run_until_complete(
                translation_svc.translate_texts(ocr_results, brand_type)
            )
            all_translations.extend(translations)

            # 리스크 탐지
            risks = loop.run_until_complete(risk_svc.detect_risks(image))

            # 이미지 재가공
            processed_image, risk_processings = loop.run_until_complete(
                img_svc.process_image(image, translations, risks, moodtone, auto_replace_risks)
            )

            # 저장
            output_filename = f"{job_id}_{os.path.basename(file_path)}"
            output_path = os.path.join(settings.LOCAL_STORAGE_PATH, output_filename)
            os.makedirs(settings.LOCAL_STORAGE_PATH, exist_ok=True)
            processed_image.save(output_path, format="JPEG", quality=settings.OUTPUT_IMAGE_QUALITY)

            results.append({
                "original_filename": os.path.basename(file_path),
                "processed_filename": output_filename,
                "width": processed_image.width,
                "height": processed_image.height,
                "file_size_bytes": os.path.getsize(output_path),
            })

        # SEO 생성
        seo_metadata = None
        if generate_seo and all_translations:
            seo_metadata = loop.run_until_complete(
                seo_svc.generate_seo_metadata(all_translations, product_name, brand_type)
            )

        logger.info(f"[{job_id}] 비동기 이미지 처리 완료")
        return {
            "job_id": job_id,
            "status": "completed",
            "processed_images": results,
            "seo_metadata": seo_metadata,
        }

    except Exception as e:
        logger.error(f"[{job_id}] 처리 실패: {e}")
        self.retry(exc=e, countdown=30)

    finally:
        loop.close()
