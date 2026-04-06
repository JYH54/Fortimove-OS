"""
B3: 썸네일 품질 체커

구매대행 상품 등록용 이미지의 품질을 자동 평가한다.
- 네이버 스마트스토어: 640x640 이상 권장, 정사각형 권장, 10MB 이하
- 쿠팡: 500x500 이상, 정사각형, 5MB 이하
- 공통: 배경 단색/흰색, 텍스트 과잉 없음, 선명도

출력: 0~100 점수 + 경고 리스트 + 메타데이터
"""
from __future__ import annotations

import io
import logging
from typing import Dict, List, Any, Optional, Tuple

from PIL import Image, ImageStat

logger = logging.getLogger(__name__)

# 플랫폼 최소 요건 (엄격한 쪽에 맞춤)
MIN_WIDTH = 640
MIN_HEIGHT = 640
RECOMMENDED_WIDTH = 1000
RECOMMENDED_HEIGHT = 1000
MAX_FILE_SIZE_MB = 5
ACCEPTED_FORMATS = {"JPEG", "JPG", "PNG"}
ASPECT_TOLERANCE = 0.08  # 1:1에서 ±8% 허용


def _sample_border_color(img: Image.Image, border_ratio: float = 0.05) -> Tuple[float, float, float, float]:
    """이미지 테두리 4면의 픽셀로 작은 캔버스를 만들어 평균 RGB/표준편차 산출.
    배경이 단색에 가까울수록 std가 낮다."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    bw = max(1, int(w * border_ratio))
    bh = max(1, int(h * border_ratio))
    # 4면 크롭 (전부 정확히 border 두께만큼)
    top = rgb.crop((0, 0, w, bh))
    bottom = rgb.crop((0, h - bh, w, h))
    left = rgb.crop((0, 0, bw, h))
    right = rgb.crop((w - bw, 0, w, h))
    # 정확한 크기의 캔버스 (상+하: w x (bh*2), 좌+우: (bw*2) x h)
    canvas_w = max(w, bw * 2)
    canvas_h = bh * 2 + h
    canvas = Image.new("RGB", (canvas_w, canvas_h), (128, 128, 128))
    canvas.paste(top, (0, 0))
    canvas.paste(bottom, (0, bh))
    canvas.paste(left, (0, bh * 2))
    canvas.paste(right, (bw, bh * 2))
    # 실제 샘플 영역만 crop (회색 패딩 제거)
    sampled = canvas.crop((0, 0, max(w, bw * 2), bh * 2 + h))
    # 샘플링 — 테두리 픽셀만 수집 직접
    pixels = []
    for x in range(w):
        pixels.append(rgb.getpixel((x, 0)))
        pixels.append(rgb.getpixel((x, h - 1)))
    for y in range(h):
        pixels.append(rgb.getpixel((0, y)))
        pixels.append(rgb.getpixel((w - 1, y)))
    # 평균·표준편차 계산
    n = len(pixels)
    sum_r = sum(p[0] for p in pixels) / n
    sum_g = sum(p[1] for p in pixels) / n
    sum_b = sum(p[2] for p in pixels) / n
    var_r = sum((p[0] - sum_r) ** 2 for p in pixels) / n
    var_g = sum((p[1] - sum_g) ** 2 for p in pixels) / n
    var_b = sum((p[2] - sum_b) ** 2 for p in pixels) / n
    std_avg = ((var_r + var_g + var_b) / 3) ** 0.5
    return sum_r, sum_g, sum_b, std_avg


def check_image_quality(
    image_bytes: bytes,
    *,
    require_white_bg: bool = True,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    image_bytes: 원본 이미지 바이트
    require_white_bg: 대표이미지용 = True (흰 배경 필수)
    """
    warnings: List[str] = []
    meta: Dict[str, Any] = {}
    score = 100

    # 1) 파일 크기
    size_mb = len(image_bytes) / (1024 * 1024)
    meta["file_size_mb"] = round(size_mb, 2)
    if size_mb > MAX_FILE_SIZE_MB:
        warnings.append(f"파일 크기 초과: {size_mb:.1f}MB (상한 {MAX_FILE_SIZE_MB}MB)")
        score -= 10

    # 2) 이미지 로드
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as e:
        return {
            "score": 0,
            "pass": False,
            "warnings": [f"이미지 로드 실패: {e}"],
            "meta": {"file_size_mb": meta["file_size_mb"]},
            "label": label,
        }

    w, h = img.size
    fmt = (img.format or "").upper()
    meta.update({"width": w, "height": h, "format": fmt})

    # 3) 포맷
    if fmt not in ACCEPTED_FORMATS:
        warnings.append(f"포맷 비권장: {fmt} (JPG/PNG 권장)")
        score -= 10

    # 4) 치수
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        warnings.append(f"해상도 부족: {w}x{h} (최소 {MIN_WIDTH}x{MIN_HEIGHT})")
        score -= 25
    elif w < RECOMMENDED_WIDTH or h < RECOMMENDED_HEIGHT:
        warnings.append(f"해상도 권장 미달: {w}x{h} (권장 {RECOMMENDED_WIDTH}x{RECOMMENDED_HEIGHT})")
        score -= 8

    # 5) 비율 (정사각형 권장)
    if w > 0 and h > 0:
        ratio = min(w, h) / max(w, h)
        meta["aspect_ratio"] = round(ratio, 3)
        if ratio < 1 - ASPECT_TOLERANCE:
            warnings.append(f"정사각형 아님: 비율 {ratio:.2f} (1.0 권장)")
            score -= 12

    # 6) 배경 단색/흰색 (대표이미지 한정)
    if require_white_bg:
        try:
            mr, mg, mb, std = _sample_border_color(img)
            meta["border_rgb"] = [round(mr), round(mg), round(mb)]
            meta["border_std"] = round(std, 1)
            brightness = (mr + mg + mb) / 3
            # 배경 복잡도 (std 높을수록 복잡 = 배경 있음)
            if std > 18:
                warnings.append(f"배경 복잡함: 테두리 편차 {std:.0f} (단색 배경 권장)")
                score -= 15
            # 밝기 체크 (흰 배경이면 240+ 근방)
            if brightness < 220:
                warnings.append(f"배경이 어둡거나 유색: 밝기 {brightness:.0f}/255 (흰 배경 권장)")
                score -= 12
        except Exception as e:
            logger.debug(f"border sampling failed: {e}")

    # 점수 하한
    score = max(0, score)
    return {
        "score": score,
        "pass": score >= 70 and not any("부족" in w for w in warnings),
        "warnings": warnings,
        "meta": meta,
        "label": label,
    }


async def check_image_url(url: str, **kwargs) -> Dict[str, Any]:
    """URL에서 이미지 받아 품질 체크"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {"url": url, **check_image_quality(resp.content, **kwargs)}
    except Exception as e:
        return {
            "url": url,
            "score": 0,
            "pass": False,
            "warnings": [f"다운로드 실패: {e}"],
            "meta": {},
        }


async def check_image_urls_batch(urls: List[str], require_white_bg: bool = False) -> Dict[str, Any]:
    """여러 URL 병렬 품질 체크"""
    import asyncio
    results = await asyncio.gather(
        *[check_image_url(u, require_white_bg=require_white_bg) for u in urls],
        return_exceptions=False,
    )
    passed = sum(1 for r in results if r.get("pass"))
    avg = round(sum(r.get("score", 0) for r in results) / max(len(results), 1))
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "avg_score": avg,
        "results": results,
    }
