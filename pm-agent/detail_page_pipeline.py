"""
Detail Page Pipeline — 상세페이지 리디자인 파이프라인 오케스트레이터

흐름:
1. 원본 이미지 → Image Localization API (OCR/번역/리스크제거/무드톤)
2. 텍스트 생성 → DetailPageStrategist (hook/혜택/FAQ/본문)
3. 이미지 전처리 → 빈 이미지 필터 / 중복 제거 / 배경 제거 / 텍스트 제거
4. 이미지 합성 → DetailPageComposer (PIL로 최종 이미지 세트)
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
from PIL import Image

from redesign_queue_manager import RedesignQueueManager
from detail_page_composer import DetailPageComposer

logger = logging.getLogger(__name__)

IMAGE_LOCALIZATION_URL = os.getenv("IMAGE_LOCALIZATION_URL", "http://localhost:8000/api/v1/process")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OUTPUT_DIR = Path(__file__).parent / "data" / "redesign_output"


# ── Image Preprocessing Helpers ─────────────────────────────


def _is_blank_image(path: str, threshold: float = 0.90) -> bool:
    """이미지가 대부분 흰색(빈 플레이스홀더)인지 확인"""
    try:
        img = Image.open(path).convert("RGB")
        arr = np.array(img)
        white_pixels = np.all(arr > 240, axis=2).sum()
        total_pixels = arr.shape[0] * arr.shape[1]
        return (white_pixels / total_pixels) > threshold
    except Exception as e:
        logger.warning(f"빈 이미지 확인 실패 {path}: {e}")
        return False


def _image_hash(path: str) -> str:
    """이미지 콘텐츠 기반 해시 (64x64 축소 후 MD5)로 중복 감지"""
    try:
        img = Image.open(path).convert("RGB").resize((64, 64))
        return hashlib.md5(img.tobytes()).hexdigest()
    except Exception as e:
        logger.warning(f"이미지 해시 생성 실패 {path}: {e}")
        return hashlib.md5(path.encode()).hexdigest()


def _remove_background_sync(img_bytes: bytes) -> Optional[bytes]:
    """rembg를 이용하여 이미지 배경 제거 → 흰색 배경 합성 (동기, CPU-intensive)."""
    try:
        from rembg import remove
        import io
        from PIL import Image as _PILImage

        # 배경 제거 (투명 PNG)
        removed = remove(img_bytes)

        # 투명 배경 → 흰색 배경 합성
        rgba = _PILImage.open(io.BytesIO(removed)).convert("RGBA")
        white_bg = _PILImage.new("RGBA", rgba.size, (255, 255, 255, 255))
        white_bg.paste(rgba, mask=rgba.split()[3])
        result = white_bg.convert("RGB")

        buf = io.BytesIO()
        result.save(buf, format="PNG", quality=95)
        return buf.getvalue()
    except ImportError:
        logger.info("rembg 미설치 — 배경 제거 스킵")
        return None
    except Exception as e:
        logger.warning(f"배경 제거 실패: {e}")
        return None


async def _remove_background(img_bytes: bytes) -> Optional[bytes]:
    """rembg 배경 제거를 스레드풀에서 실행 (이벤트 루프 차단 방지)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _remove_background_sync, img_bytes)


async def _remove_text_gemini(img_bytes: bytes) -> bytes:
    """Gemini API로 이미지 내 텍스트(중국어/영어 등) 제거. 실패 시 원본 반환."""
    if not GOOGLE_API_KEY:
        return img_bytes

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.info("google-genai 미설치 — 텍스트 제거 스킵")
        return img_bytes

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[
                "Remove ALL text from this product image. "
                "Erase every Chinese, English, Japanese, and Korean character completely. "
                "Fill the removed areas naturally with surrounding background. "
                "Keep the product itself intact.",
                img_part,
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts or []:
                if (
                    hasattr(part, "inline_data")
                    and part.inline_data
                    and part.inline_data.mime_type.startswith("image/")
                ):
                    return part.inline_data.data

        logger.warning("Gemini 텍스트 제거 응답에 이미지 없음 — 원본 반환")
        return img_bytes

    except Exception as e:
        logger.warning(f"Gemini 텍스트 제거 실패: {e} — 원본 반환")
        return img_bytes


async def _preprocess_images(source_images: List[str], output_dir: Path) -> List[Dict]:
    """
    소스 이미지를 전처리하여 정리된 이미지 목록 반환.

    처리 순서:
    1. 빈 이미지(흰색 플레이스홀더) 필터링
    2. 콘텐츠 해시 기반 중복 제거
    3. 배경 제거 (rembg)
    4. 텍스트 제거 (Gemini API)

    Returns:
        List of dicts:
        {
            "original": str (원본 경로),
            "clean": str (전처리된 이미지 경로),
            "display_order": int,
        }
    """
    preprocessed_dir = output_dir / "preprocessed"
    preprocessed_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: 빈 이미지 필터링 (CPU-intensive → executor)
    loop = asyncio.get_event_loop()
    valid_images = []
    for path in source_images:
        if not Path(path).exists():
            logger.warning(f"이미지 경로 존재하지 않음: {path}")
            continue
        is_blank = await loop.run_in_executor(None, _is_blank_image, path)
        if is_blank:
            logger.info(f"빈 플레이스홀더 필터링: {path}")
            continue
        # Also filter tiny thumbnails (under 10KB = likely thumbnail/icon)
        file_size = Path(path).stat().st_size
        if file_size < 10240:
            logger.info(f"너무 작은 이미지 필터링 ({file_size//1024}KB): {path}")
            continue
        valid_images.append(path)

    if not valid_images:
        logger.warning("전처리 후 유효 이미지 없음 — 원본 이미지 사용")
        valid_images = [p for p in source_images if Path(p).exists()]

    # Phase 2: 중복 제거 (해시 계산 → executor)
    seen_hashes: Dict[str, str] = {}
    deduplicated = []
    for path in valid_images:
        h = await loop.run_in_executor(None, _image_hash, path)
        if h in seen_hashes:
            logger.info(f"중복 이미지 제거: {path} (중복 원본: {seen_hashes[h]})")
            continue
        seen_hashes[h] = path
        deduplicated.append(path)

    if not deduplicated:
        deduplicated = valid_images[:1] if valid_images else []

    # Phase 3 & 4: 배경 제거 + 텍스트 제거
    results: List[Dict] = []
    for idx, src_path in enumerate(deduplicated):
        order = idx + 1
        clean_name = f"{order:02d}_product_clean.png"
        clean_path = preprocessed_dir / clean_name

        try:
            src_bytes = Path(src_path).read_bytes()

            # 3-a. 배경 제거
            bg_removed = await _remove_background(src_bytes)
            working_bytes = bg_removed if bg_removed else src_bytes

            # 배경 제거 버전도 별도 저장 (투명 배경)
            if bg_removed:
                nobg_path = preprocessed_dir / f"{order:02d}_product_nobg.png"
                nobg_path.write_bytes(bg_removed)

            # 3-b. 텍스트 제거 (Gemini)
            cleaned_bytes = await _remove_text_gemini(working_bytes)

            # 최종 정리본 저장 (PNG)
            clean_path.write_bytes(cleaned_bytes)

            results.append({
                "original": src_path,
                "clean": str(clean_path),
                "display_order": order,
            })
            logger.info(f"[{order}] 전처리 완료: {Path(src_path).name} → {clean_name}")

        except Exception as e:
            logger.warning(f"이미지 전처리 실패 {src_path}: {e} — 원본 사용")
            # 실패 시 원본을 그대로 복사
            try:
                shutil.copy2(src_path, str(clean_path))
            except Exception:
                clean_path = Path(src_path)
            results.append({
                "original": src_path,
                "clean": str(clean_path),
                "display_order": order,
            })

    return results


async def _call_localization_api(image_paths: List[str], moodtone: str) -> Dict[str, Any]:
    """Image Localization API 호출"""
    files = []
    opened = []
    try:
        for path in image_paths:
            p = Path(path)
            if p.exists():
                f = open(p, "rb")
                opened.append(f)
                files.append(("files", (p.name, f, "image/jpeg")))

        if not files:
            logger.warning("현지화할 이미지 없음 — 스킵")
            return {}

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                IMAGE_LOCALIZATION_URL,
                files=files,
                data={
                    "moodtone": moodtone,
                    "brand_type": "fortimove_global",
                    "generate_seo": "true",
                    "auto_replace_risks": "true",
                },
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Image Localization API 호출 실패: {e}")
        return {"error": str(e)}
    finally:
        for f in opened:
            f.close()


def _generate_text_content(source_title: str, category: str) -> Dict[str, Any]:
    """DetailPageStrategist로 텍스트 콘텐츠 생성"""
    try:
        from detail_page_strategist import DetailPageStrategist

        strategist = DetailPageStrategist()
        product_summary = {
            "positioning_summary": source_title,
            "usp_points": [],
            "target_customer": "건강/웰니스에 관심 있는 30-50대",
            "usage_scenarios": [],
            "differentiation_points": [],
        }
        source_data = {
            "source_title": source_title,
            "category": category,
        }
        return strategist.generate_detail_page_content(product_summary, source_data, category)
    except Exception as e:
        logger.error(f"텍스트 생성 실패: {e}")
        # 폴백: 기본 텍스트
        return {
            "main_title": source_title,
            "hook_copies": [f"{source_title} — 지금 만나보세요"],
            "key_benefits": ["프리미엄 품질", "빠른 배송", "안심 검수 완료"],
            "problem_scenarios": [],
            "solution_narrative": "",
            "faq": [{"q": "배송은 얼마나 걸리나요?", "a": "주문 후 7-14일 내 도착합니다."}],
            "usage_guide": "",
            "cautions": "해외 구매대행 상품으로, 교환/반품 시 국제 배송비가 발생할 수 있습니다.",
            "naver_body": "",
            "coupang_body": "",
            "short_ad_copies": [],
            "compliance_warnings": [],
        }


async def _download_localized_images(localization_result: Dict, output_dir: Path) -> List[str]:
    """현지화된 이미지를 다운로드하여 로컬에 저장"""
    downloaded = []
    processed = localization_result.get("processed_images", [])

    async with httpx.AsyncClient(timeout=30.0) as client:
        for img in processed:
            url = img.get("download_url", "")
            if not url:
                continue
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                fname = img.get("processed_filename", f"localized_{len(downloaded)}.jpg")
                dest = output_dir / f"src_{fname}"
                dest.write_bytes(resp.content)
                downloaded.append(str(dest))
            except Exception as e:
                logger.warning(f"이미지 다운로드 실패: {url} — {e}")

    return downloaded


async def run_pipeline(redesign_id: str):
    """메인 파이프라인 실행 (BackgroundTask로 호출됨)"""
    manager = RedesignQueueManager()
    item = manager.get_item(redesign_id)
    if not item:
        logger.error(f"[{redesign_id}] 아이템 없음")
        return

    try:
        source_images = json.loads(item["source_images_json"]) if isinstance(item["source_images_json"], str) else item["source_images_json"]
        moodtone = item.get("moodtone", "premium")
        category = item.get("category", "general")
        source_title = item.get("source_title", "상품")

        # 출력 디렉토리 생성
        output_dir = OUTPUT_DIR / redesign_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Image Localization API (OCR/번역/리스크감지)
        # API로 분석만 하고, 이미지는 원본 고해상도를 사용
        logger.info(f"[{redesign_id}] Step 1: 이미지 분석 중 (OCR/리스크)...")
        localization_result = await _call_localization_api(source_images, moodtone)
        manager.save_pipeline_results(redesign_id, localized_images=localization_result)

        # 리스크 리포트는 저장하되, 이미지는 항상 원본 고해상도 사용
        # (현지화 API가 이미지를 과도하게 압축하므로 원본이 더 좋음)
        localized_paths = source_images
        if localization_result and not localization_result.get("error"):
            report = localization_result.get("analysis_report", {})
            risks = report.get("risks_detected", [])
            ocr = report.get("ocr_results", [])
            logger.info(f"[{redesign_id}] 분석 완료: OCR {len(ocr)}건, 리스크 {len(risks)}건 — 원본 이미지 사용")

        # Step 2: 텍스트 콘텐츠 생성
        logger.info(f"[{redesign_id}] Step 2: 텍스트 생성 중...")
        text_content = _generate_text_content(source_title, category)
        manager.save_pipeline_results(redesign_id, text_content=text_content)

        # Step 3: 이미지 전처리 (빈 이미지 필터 / 중복 제거 / 배경 제거 / 텍스트 제거)
        logger.info(f"[{redesign_id}] Step 3: 이미지 전처리 중...")
        preprocessed = await _preprocess_images(localized_paths, output_dir)
        logger.info(f"[{redesign_id}] 전처리 완료: {len(localized_paths)}장 → {len(preprocessed)}장")

        # Step 4: Visual Composition
        logger.info(f"[{redesign_id}] Step 4: 이미지 합성 중...")

        composed = []

        # 4-A. 전처리된 상품 이미지를 출력에 포함
        for pp in preprocessed:
            try:
                clean_src = Path(pp["clean"])
                if not clean_src.exists():
                    continue
                order = pp["display_order"]
                dst_name = f"{order:02d}_product_clean.png"
                dst = output_dir / dst_name
                if str(clean_src.resolve()) != str(dst.resolve()):
                    shutil.copy2(str(clean_src), str(dst))
                try:
                    with Image.open(str(dst)) as _img:
                        w, h = _img.size
                except Exception:
                    w, h = 0, 0
                composed.append({
                    "filename": dst_name,
                    "section_type": "product",
                    "display_order": order,
                    "width": w,
                    "height": h,
                    "engine": "preprocessed",
                })
            except Exception as e:
                logger.warning(f"전처리 이미지 복사 실패 {pp.get('clean')}: {e}")

        # 4-B. 템플릿 섹션 (hero, faq, spec) 생성 — 전처리 이미지 뒤에 추가
        # DetailPageComposer에는 전처리된 이미지 + 원본 경로 모두 전달
        cleaned_image_paths = [pp["clean"] for pp in preprocessed if Path(pp["clean"]).exists()]
        composer_image_paths = cleaned_image_paths if cleaned_image_paths else localized_paths

        try:
            composer = DetailPageComposer(moodtone=moodtone)
            template_composed = composer.compose_detail_page(
                text_content=text_content,
                image_paths=composer_image_paths,
                output_dir=str(output_dir),
            )
            # display_order를 상품 이미지 뒤로 밀기
            base_order = len(composed)
            for item in template_composed:
                item["display_order"] = base_order + item.get("display_order", 1)
                # 템플릿 파일명 충돌 방지
                if item["filename"] in [c["filename"] for c in composed]:
                    continue
                composed.append(item)
        except Exception as e:
            logger.warning(f"템플릿 섹션 생성 실패: {e}")

        manager.save_pipeline_results(
            redesign_id,
            composed_images=composed,
            output_directory=str(output_dir),
        )
        manager.update_status(redesign_id, "completed")
        logger.info(f"[{redesign_id}] 파이프라인 완료: {len(composed)}개 이미지 (전처리 {len(preprocessed)} + 템플릿)")

    except Exception as e:
        logger.exception(f"[{redesign_id}] 파이프라인 실패")
        manager.update_status(redesign_id, "failed", error_message=str(e))


async def recompose_section(redesign_id: str, section: str):
    """단일 섹션 재합성"""
    manager = RedesignQueueManager()
    item = manager.get_item(redesign_id)
    if not item:
        return

    try:
        text_content = json.loads(item.get("text_content_json", "{}")) if isinstance(item.get("text_content_json"), str) else (item.get("text_content_json") or {})
        overrides = json.loads(item.get("edit_overrides_json", "{}")) if isinstance(item.get("edit_overrides_json"), str) else (item.get("edit_overrides_json") or {})
        composed = json.loads(item.get("composed_images_json", "[]")) if isinstance(item.get("composed_images_json"), str) else (item.get("composed_images_json") or [])

        # 오버라이드 텍스트 적용
        section_override = overrides.get(section, {})
        if section_override.get("text"):
            # 섹션 타입에 따라 텍스트 교체
            section_text_map = {
                "hero": "hook_copies",
                "benefits": "key_benefits",
                "problem_solution": "solution_narrative",
                "faq": "faq",
                "spec": "cautions",
            }
            key = section_text_map.get(section)
            if key and key in text_content:
                if isinstance(text_content[key], list):
                    text_content[key] = [section_override["text"]]
                else:
                    text_content[key] = section_override["text"]

        output_dir = Path(item.get("output_directory", str(OUTPUT_DIR / redesign_id)))
        source_images = json.loads(item["source_images_json"]) if isinstance(item["source_images_json"], str) else item["source_images_json"]
        moodtone = item.get("moodtone", "premium")

        composer = DetailPageComposer(moodtone=moodtone)

        # 오버라이드 이미지 경로
        override_image = section_override.get("image_path")

        new_image = composer.compose_single_section(
            section_type=section,
            text_content=text_content,
            image_path=override_image or (source_images[0] if source_images else None),
            output_dir=str(output_dir),
        )

        # composed_images 업데이트
        for i, c in enumerate(composed):
            if c.get("section_type") == section:
                composed[i] = new_image
                break

        manager.save_pipeline_results(redesign_id, composed_images=composed)
        logger.info(f"[{redesign_id}] 섹션 재합성 완료: {section}")

    except Exception as e:
        logger.exception(f"[{redesign_id}] 섹션 재합성 실패: {section}")
