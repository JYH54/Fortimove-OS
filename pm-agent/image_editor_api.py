"""
Image Editor API — 상세페이지 이미지 편집 엔드포인트 (8개 기능)

1. 이미지 일괄번역 (OCR + 번역 + 오버레이)
2. 크기 변형 (리사이즈)
3. 자르기 (Crop)
4. AI 지우개 (inpainting)
5. 영역 AI 지우개 (mask-based inpainting)
6. 배경 제거
7. 텍스트 제거 (OCR 감지 → inpainting)
8. 텍스트 추가 (폰트/글꼴 선택)
"""

import io
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/editor", tags=["image-editor"])

FONTS_DIR = Path(__file__).parent / "fonts"
TEMP_DIR = Path(__file__).parent / "data" / "editor_temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")


def _pil_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=92)
    return buf.getvalue()


def _load_image(file: UploadFile) -> Image.Image:
    return Image.open(io.BytesIO(file.file.read())).convert("RGBA")


def _image_response(img: Image.Image, fmt: str = "PNG") -> Response:
    media = "image/png" if fmt == "PNG" else "image/jpeg"
    if fmt == "JPEG":
        img = img.convert("RGB")
    return Response(content=_pil_to_bytes(img, fmt), media_type=media)


# ── 1. 이미지 일괄번역 ───────────────────────────────────

@router.post("/translate")
async def translate_image(
    file: UploadFile = File(...),
    moodtone: str = Form("premium"),
    brand_type: str = Form("fortimove_global"),
):
    """이미지 내 중국어 텍스트를 한국어로 번역 (Image Localization API 호출)"""
    import httpx

    localization_url = os.getenv("IMAGE_LOCALIZATION_URL", "http://localhost:8000/api/v1/process")
    content = await file.read()

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            localization_url,
            files=[("files", (file.filename or "img.jpg", content, "image/jpeg"))],
            data={
                "moodtone": moodtone,
                "brand_type": brand_type,
                "generate_seo": "false",
                "auto_replace_risks": "true",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(500, f"번역 API 오류: {resp.status_code}")

    result = resp.json()
    processed = result.get("processed_images", [])
    if not processed:
        raise HTTPException(400, "번역할 텍스트가 없습니다")

    # 처리된 이미지 다운로드
    download_url = processed[0].get("download_url", "")
    async with httpx.AsyncClient(timeout=30.0) as client:
        img_resp = await client.get(download_url)

    return Response(content=img_resp.content, media_type="image/jpeg")


# ── 2. 크기 변형 ─────────────────────────────────────────

@router.post("/resize")
async def resize_image(
    file: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
):
    """이미지 리사이즈"""
    img = _load_image(file)
    resized = img.resize((width, height), Image.LANCZOS)
    return _image_response(resized)


# ── 3. 자르기 (Crop) ─────────────────────────────────────

@router.post("/crop")
async def crop_image(
    file: UploadFile = File(...),
    x: int = Form(0),
    y: int = Form(0),
    w: int = Form(...),
    h: int = Form(...),
):
    """이미지 자르기 (x, y, w, h)"""
    img = _load_image(file)
    cropped = img.crop((x, y, x + w, y + h))
    return _image_response(cropped)


# ── 4. AI 지우개 (브러시 inpainting) ──────────────────────

@router.post("/ai-erase")
async def ai_erase(
    file: UploadFile = File(...),
    mask: UploadFile = File(...),
):
    """AI 지우개 — 마스크 영역을 깨끗하게 제거 (Gemini inpainting)"""
    img_bytes = await file.read()
    mask_bytes = await mask.read()

    result = await _gemini_inpaint(
        img_bytes, mask_bytes,
        prompt="Clean background, remove the masked object completely, seamless natural fill"
    )
    return Response(content=result, media_type="image/png")


# ── 5. 영역 AI 지우개 (사각형 영역) ──────────────────────

@router.post("/area-erase")
async def area_erase(
    file: UploadFile = File(...),
    x: int = Form(0),
    y: int = Form(0),
    w: int = Form(...),
    h: int = Form(...),
):
    """영역 AI 지우개 — 사각형 영역을 AI로 깨끗하게 제거"""
    img = _load_image(file)

    # 사각형 영역을 마스크로 변환
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle([x, y, x + w, y + h], fill=255)

    img_bytes = _pil_to_bytes(img.convert("RGB"), "PNG")
    mask_bytes = _pil_to_bytes(mask.convert("RGB"), "PNG")

    result = await _gemini_inpaint(
        img_bytes, mask_bytes,
        prompt="Clean seamless background fill, remove everything in the masked area naturally"
    )
    return Response(content=result, media_type="image/png")


# ── 6. 배경 제거 ─────────────────────────────────────────

@router.post("/remove-bg")
async def remove_background(
    file: UploadFile = File(...),
    bg_color: str = Form("white"),  # white, transparent
):
    """배경 제거 — 상품만 남기고 배경 삭제"""
    img_bytes = await file.read()

    try:
        from rembg import remove
        result_bytes = remove(img_bytes)
        result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")

        if bg_color == "white":
            bg = Image.new("RGBA", result.size, (255, 255, 255, 255))
            bg.paste(result, mask=result.split()[3])
            return _image_response(bg.convert("RGB"), "JPEG")
        else:
            return _image_response(result, "PNG")

    except ImportError:
        logger.warning("rembg 미설치 — Gemini 폴백")
        # Gemini로 배경 제거 시도
        result = await _gemini_edit(
            img_bytes,
            prompt="Remove the background completely, keep only the product. White background."
        )
        return Response(content=result, media_type="image/png")


# ── 7. 텍스트 제거 ───────────────────────────────────────

@router.post("/remove-text")
async def remove_text(
    file: UploadFile = File(...),
):
    """이미지 내 모든 텍스트 제거"""
    img_bytes = await file.read()

    result = await _gemini_edit(
        img_bytes,
        prompt="Remove ALL text, letters, words, numbers, watermarks from this image. Keep the product and design elements intact. Fill removed areas with matching background seamlessly."
    )
    return Response(content=result, media_type="image/png")


# ── 8. 텍스트 추가 ───────────────────────────────────────

@router.post("/add-text")
async def add_text(
    file: UploadFile = File(...),
    text: str = Form(...),
    x: int = Form(60),
    y: int = Form(60),
    font_size: int = Form(36),
    font_weight: str = Form("bold"),  # bold, regular
    color: str = Form("#000000"),
    bg_color: Optional[str] = Form(None),  # 배경색 (null이면 없음)
    max_width: Optional[int] = Form(None),
):
    """텍스트 추가 — 폰트/글꼴/색상 선택 가능"""
    img = _load_image(file)
    draw = ImageDraw.Draw(img)

    # 폰트 선택
    font_file = "NanumGothic-Bold.ttf" if font_weight == "bold" else "NanumGothic-Regular.ttf"
    font_path = FONTS_DIR / font_file
    if not font_path.exists():
        raise HTTPException(400, f"폰트 없음: {font_file}")
    font = ImageFont.truetype(str(font_path), font_size)

    # 색상 파싱
    text_color = _hex_to_rgba(color)

    # 줄바꿈 처리
    effective_max = max_width or (img.width - x - 60)
    lines = _wrap_text_pil(draw, text, font, effective_max)

    # 배경색
    if bg_color:
        bg_rgba = _hex_to_rgba(bg_color)
        line_height = font_size + 10
        total_h = len(lines) * line_height + 20
        max_line_w = max(draw.textbbox((0, 0), line, font=font)[2] for line in lines) if lines else 0
        draw.rounded_rectangle(
            [x - 10, y - 10, x + max_line_w + 10, y + total_h],
            radius=8, fill=bg_rgba
        )

    # 텍스트 렌더링
    current_y = y
    for line in lines:
        draw.text((x, current_y), line, font=font, fill=text_color)
        current_y += font_size + 10

    return _image_response(img)


# ── Gemini 이미지 편집 헬퍼 ───────────────────────────────

async def _gemini_edit(img_bytes: bytes, prompt: str) -> bytes:
    """Gemini 이미지 편집 (단일 이미지 + 프롬프트)"""
    from google import genai
    from google.genai import types
    import logging as _log

    client = genai.Client(api_key=GOOGLE_API_KEY)

    img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt, img_part],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
    except Exception as e:
        _log.warning(f"Gemini API 호출 실패: {e} — 원본 반환")
        return img_bytes

    # 이미지 응답 추출
    try:
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts or []:
                if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    return part.inline_data.data
    except (AttributeError, IndexError, TypeError) as e:
        _log.warning(f"Gemini 응답 파싱 실패: {e}")

    # 결과 없음 — 안전 필터 또는 모델 거부. 원본 반환하고 로그만 남김
    _log.warning("Gemini가 이미지 편집을 거부함 — 원본 이미지 반환")
    return img_bytes


async def _gemini_inpaint(img_bytes: bytes, mask_bytes: bytes, prompt: str) -> bytes:
    """Gemini inpainting (이미지 + 마스크)"""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_API_KEY)

    img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
    mask_part = types.Part.from_bytes(data=mask_bytes, mime_type="image/png")

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[
            f"Edit this image using the mask. Mask shows area to modify. {prompt}",
            img_part,
            mask_part,
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    import logging as _log
    try:
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts or []:
                if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    return part.inline_data.data
    except (AttributeError, IndexError, TypeError) as e:
        _log.warning(f"Gemini inpaint 응답 파싱 실패: {e}")

    _log.warning("Gemini inpainting 거부 — 원본 반환")
    return img_bytes


# ── 유틸 ──────────────────────────────────────────────────

def _hex_to_rgba(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (255,)
    elif len(h) == 8:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4, 6))
    return (0, 0, 0, 255)


def _wrap_text_pil(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] > max_width and current:
                lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
    return lines


# ── 폰트 목록 ────────────────────────────────────────────

@router.get("/fonts")
async def list_fonts():
    """사용 가능한 폰트 목록"""
    fonts = []
    if FONTS_DIR.exists():
        for f in sorted(FONTS_DIR.glob("*.ttf")):
            fonts.append({
                "filename": f.name,
                "name": f.stem.replace("-", " "),
            })
    return {"fonts": fonts}
