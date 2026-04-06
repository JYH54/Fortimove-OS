"""
Redesign API — 상세페이지 리디자인 파이프라인 엔드포인트
"""

import json
import logging
import os
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional
from zipfile import ZipFile

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from redesign_queue_manager import RedesignQueueManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/redesign", tags=["redesign"])

UPLOAD_DIR = Path(__file__).parent / "data" / "redesign_uploads"
OUTPUT_DIR = Path(__file__).parent / "data" / "redesign_output"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _get_manager() -> RedesignQueueManager:
    return RedesignQueueManager()


# ── 업로드 / 큐 등록 ─────────────────────────────────────

@router.post("/upload")
async def upload_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    source_title: str = Form(...),
    moodtone: str = Form("premium"),
    category: str = Form("general"),
    source_type: str = Form("manual_upload"),
):
    """이미지 수동 업로드 → 큐 등록"""
    if not files:
        raise HTTPException(400, "이미지를 1개 이상 업로드하세요.")

    manager = _get_manager()

    # 이미지 저장
    saved_paths: List[str] = []
    import uuid
    batch_id = uuid.uuid4().hex[:8]

    for f in files:
        ext = Path(f.filename or "img.jpg").suffix or ".jpg"
        filename = f"{batch_id}_{len(saved_paths):02d}{ext}"
        dest = UPLOAD_DIR / filename
        content = await f.read()
        dest.write_bytes(content)
        saved_paths.append(str(dest))

    redesign_id = manager.add_to_queue(
        source_title=source_title,
        source_images=saved_paths,
        source_type=source_type,
        moodtone=moodtone,
        category=category,
    )

    return {"redesign_id": redesign_id, "image_count": len(saved_paths), "status": "waiting"}


@router.post("/from-review/{review_id}")
async def create_from_review(
    review_id: str,
    moodtone: str = Form("premium"),
):
    """기존 리뷰 아이템에서 리디자인 작업 생성
    - 이미지 URL을 로컬 파일로 다운로드
    - 로고/배너 자동 필터링
    - 실제 상품 사진만 리디자인 파이프라인에 전달
    """
    from approval_queue import ApprovalQueueManager

    aq = ApprovalQueueManager()
    item = aq.get_item(review_id)

    if not item:
        raise HTTPException(404, f"리뷰 아이템 없음: {review_id}")

    # source_data에서 이미지 URL 추출
    source_data_raw = item.get("source_data_json") or item.get("source_data") or "{}"
    if isinstance(source_data_raw, str):
        try:
            source_data = json.loads(source_data_raw)
        except json.JSONDecodeError:
            source_data = {}
    elif isinstance(source_data_raw, dict):
        source_data = source_data_raw
    else:
        source_data = {}

    image_urls = source_data.get("images", [])

    if not image_urls:
        raise HTTPException(400, "리뷰 아이템에 이미지가 없습니다.")

    # 로고/배너/UI 이미지 필터링
    EXCLUDE_PATTERNS = [
        '/brand/logo/', '/cms/banners/', '/cms/my-account/',
        '/cms/logos/', '/icon/', '/badge/', '/flag/', '/ui/',
        'sprite', 'placeholder', 'loading', 'rewards',
        'logo', 'social-', 'footer', 'header', 'qr-code',
        '/static/i/', 'my-account',
    ]
    product_urls = [
        u for u in image_urls
        if isinstance(u, str) and not any(pat in u.lower() for pat in EXCLUDE_PATTERNS)
    ]
    if not product_urls:
        product_urls = image_urls[:5]  # 폴백: 앞 5개 사용

    # 이미지 URL → 로컬 파일 다운로드 (고해상도 변환)
    import httpx
    download_dir = UPLOAD_DIR / review_id
    download_dir.mkdir(parents=True, exist_ok=True)
    local_paths = []

    def _to_hires(url: str) -> str:
        """CDN URL을 고해상도 버전으로 변환 (원본 포맷 유지 + 고품질)"""
        # iHerb Cloudinary: 원본 포맷 유지(f_auto) + 고품질(q_95) + 고해상도(w_1200)
        if "cloudinary.images-iherb.com" in url:
            url = url.replace("f_auto,q_auto:eco", "f_auto,q_95,w_1200")
            url = url.replace("f_auto,q_auto", "f_auto,q_95,w_1200")
        # Amazon: 작은 이미지 → 큰 이미지
        if "images-amazon.com" in url or "media-amazon.com" in url:
            import re
            url = re.sub(r'\._[A-Z]{2}\d+_', '', url)  # _SL200_ 등 제거
            url = re.sub(r'\._[A-Z]+\d+,\d+_', '', url)
        return url

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for idx, url in enumerate(product_urls[:10]):
            try:
                hires_url = _to_hires(url)
                resp = await client.get(hires_url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "image/jpeg,image/png,image/webp,image/*,*/*",
                })
                if resp.status_code == 200 and len(resp.content) > 5000:
                    # 확장자 추출
                    ct = resp.headers.get("content-type", "")
                    ext = ".jpg"
                    if "png" in ct:
                        ext = ".png"
                    elif "webp" in ct:
                        ext = ".webp"
                    filename = f"product_{idx + 1:02d}{ext}"
                    filepath = download_dir / filename
                    filepath.write_bytes(resp.content)
                    local_paths.append(str(filepath))
                    logger.info(f"[{review_id}] 이미지 다운로드: {filename} ({len(resp.content)//1024}KB)")
            except Exception as e:
                logger.warning(f"[{review_id}] 이미지 다운로드 실패: {url[:60]}... — {e}")

    if not local_paths:
        raise HTTPException(400, f"상품 이미지를 다운로드할 수 없습니다 (시도: {len(product_urls)}건)")

    manager = _get_manager()
    redesign_id = manager.add_to_queue(
        source_title=item.get("source_title", "제목 없음"),
        source_images=local_paths,  # 로컬 파일 경로 전달 (URL 아님!)
        source_type="sourcing_agent",
        moodtone=moodtone,
        category=source_data.get("category", "general"),
        review_id=review_id,
    )

    return {
        "redesign_id": redesign_id,
        "image_count": len(local_paths),
        "filtered_out": len(image_urls) - len(product_urls),
        "status": "waiting",
    }


# ── 큐 조회 ──────────────────────────────────────────────

@router.get("/queue")
async def list_queue(
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    limit: int = 50,
):
    """대기열 목록"""
    manager = _get_manager()
    items = manager.list_queue(status=status, source_type=source_type, limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/{redesign_id}")
async def get_redesign_detail(redesign_id: str):
    """리디자인 상세 정보"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404, f"리디자인 아이템 없음: {redesign_id}")

    # JSON 필드 파싱
    for field in ("source_images_json", "localized_images_json", "text_content_json", "composed_images_json", "edit_overrides_json"):
        if item.get(field) and isinstance(item[field], str):
            try:
                item[field] = json.loads(item[field])
            except json.JSONDecodeError:
                pass

    return item


# ── 파이프라인 트리거 ─────────────────────────────────────

@router.post("/{redesign_id}/start")
async def start_pipeline(redesign_id: str, background_tasks: BackgroundTasks):
    """파이프라인 수동 트리거"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404, f"리디자인 아이템 없음: {redesign_id}")

    if item["status"] not in ("waiting", "failed"):
        raise HTTPException(400, f"현재 상태({item['status']})에서는 시작할 수 없습니다.")

    manager.update_status(redesign_id, "processing")

    # 백그라운드에서 파이프라인 실행
    from detail_page_pipeline import run_pipeline
    background_tasks.add_task(run_pipeline, redesign_id)

    return {"redesign_id": redesign_id, "status": "processing"}


# ── 결과 조회 / 이미지 서빙 ───────────────────────────────

@router.get("/{redesign_id}/result")
async def get_result(redesign_id: str):
    """합성 이미지 목록"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404)

    if item["status"] != "completed":
        return {"status": item["status"], "images": []}

    composed = json.loads(item["composed_images_json"]) if item.get("composed_images_json") else []
    return {"status": "completed", "images": composed}


@router.get("/{redesign_id}/image/{filename}")
async def serve_image(redesign_id: str, filename: str):
    """합성된 개별 이미지 서빙"""
    # 경로 탐색 방지
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "잘못된 파일명")

    output_dir = OUTPUT_DIR / redesign_id
    file_path = output_dir / filename

    if not file_path.exists():
        raise HTTPException(404, f"이미지 없음: {filename}")

    media_type = "image/png" if filename.endswith(".png") else "image/jpeg"
    return FileResponse(str(file_path), media_type=media_type)


# ── 이미지 관리 (순서/삭제/추가) ────────────────────────────

@router.post("/{redesign_id}/images/reorder")
async def reorder_images(
    redesign_id: str,
    order: str = Form(...),  # JSON array string: '["file1.png","file2.png"]'
):
    """이미지 순서 변경 (Form 방식)"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404)

    composed = json.loads(item.get("composed_images_json") or "[]")
    if not composed:
        raise HTTPException(400, "이미지 없음")

    new_order = json.loads(order)
    filename_map = {img["filename"]: img for img in composed}
    reordered = [filename_map[fn] for fn in new_order if fn in filename_map]

    # 순서에 없는 이미지도 뒤에 추가
    remaining = [img for img in composed if img["filename"] not in new_order]
    reordered.extend(remaining)

    manager.save_pipeline_results(redesign_id, composed_images=reordered)
    return {"status": "ok", "images": reordered}


@router.delete("/{redesign_id}/images/{filename}")
async def delete_image(redesign_id: str, filename: str):
    """이미지 삭제"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "잘못된 파일명")

    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404)

    composed = json.loads(item.get("composed_images_json") or "[]")
    new_composed = [img for img in composed if img["filename"] != filename]

    if len(new_composed) == len(composed):
        raise HTTPException(404, f"이미지 없음: {filename}")

    manager.save_pipeline_results(redesign_id, composed_images=new_composed)

    # 파일도 삭제
    file_path = OUTPUT_DIR / redesign_id / filename
    if file_path.exists():
        file_path.unlink()

    return {"status": "ok", "remaining": len(new_composed)}


@router.post("/{redesign_id}/images/upload")
async def upload_additional_image(
    redesign_id: str,
    file: UploadFile = File(...),
    section_type: str = Form("custom"),
):
    """이미지 추가 업로드"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404)

    composed = json.loads(item.get("composed_images_json") or "[]")

    # 파일 저장
    output_dir = OUTPUT_DIR / redesign_id
    output_dir.mkdir(parents=True, exist_ok=True)

    import uuid
    ext = Path(file.filename or "img.png").suffix or ".png"
    new_filename = f"custom_{uuid.uuid4().hex[:8]}{ext}"
    file_path = output_dir / new_filename
    content = await file.read()
    file_path.write_bytes(content)

    new_entry = {
        "filename": new_filename,
        "section_type": section_type,
        "source": "manual_upload",
    }
    composed.append(new_entry)
    manager.save_pipeline_results(redesign_id, composed_images=composed)

    return {"status": "ok", "image": new_entry, "total": len(composed)}


# ── 편집 ──────────────────────────────────────────────────

@router.post("/{redesign_id}/edit-section")
async def edit_section(
    redesign_id: str,
    background_tasks: BackgroundTasks,
    section: str = Form(...),
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
):
    """섹션별 텍스트/이미지 수정 → 해당 섹션만 재렌더"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404)

    # 수정 사항 저장
    overrides = json.loads(item.get("edit_overrides_json") or "{}") if isinstance(item.get("edit_overrides_json"), str) else (item.get("edit_overrides_json") or {})

    override_entry: dict = {}
    if text is not None:
        override_entry["text"] = text
    if image:
        img_path = UPLOAD_DIR / f"{redesign_id}_{section}{Path(image.filename or '.jpg').suffix}"
        img_path.write_bytes(await image.read())
        override_entry["image_path"] = str(img_path)

    overrides[section] = override_entry
    manager.save_edit_overrides(redesign_id, overrides)

    # 해당 섹션만 재렌더
    from detail_page_pipeline import recompose_section
    background_tasks.add_task(recompose_section, redesign_id, section)

    return {"status": "recomposing", "section": section}


@router.post("/{redesign_id}/regenerate")
async def regenerate_all(redesign_id: str, background_tasks: BackgroundTasks):
    """전체 재생성"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item:
        raise HTTPException(404)

    manager.update_status(redesign_id, "processing")
    from detail_page_pipeline import run_pipeline
    background_tasks.add_task(run_pipeline, redesign_id)

    return {"status": "processing"}


# ── 다운로드 ──────────────────────────────────────────────

@router.get("/{redesign_id}/export-pick2sell")
async def export_pick2sell(redesign_id: str):
    """pick2sell 형식 내보내기 (기본정보CSV + 판매가CSV + 상세이미지)"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item or item["status"] != "completed":
        raise HTTPException(400, "완료된 리디자인만 내보내기 가능합니다.")

    from pick2sell_exporter import Pick2SellExporter
    exporter = Pick2SellExporter()

    review_id = item.get("review_id", redesign_id)
    zip_path = exporter.export_from_review(review_id) if review_id != redesign_id else None

    if not zip_path:
        # review_id 없으면 직접 내보내기
        output_dir = item.get("output_directory", "")
        detail_images = sorted([str(f) for f in Path(output_dir).glob("*.jpg")]) if output_dir and Path(output_dir).exists() else []

        text_content = json.loads(item.get("text_content_json", "{}")) if isinstance(item.get("text_content_json"), str) else (item.get("text_content_json") or {})

        product_data = {
            "title": item.get("source_title", ""),
            "tags": [],
            "category": item.get("category", "general"),
            "options": [],
            "source_price": 0,
            "selling_price": 0,
            "margin_rate": 0,
            "source_country": "CN",
            "weight_kg": 0.5,
            "description": text_content.get("main_title", ""),
        }
        zip_path = exporter.export_product(redesign_id, product_data, detail_images)

    return FileResponse(zip_path, media_type="application/zip", filename=Path(zip_path).name)


@router.get("/{redesign_id}/download")
async def download_zip(redesign_id: str):
    """최종 이미지 ZIP 다운로드"""
    manager = _get_manager()
    item = manager.get_item(redesign_id)
    if not item or item["status"] != "completed":
        raise HTTPException(400, "완료된 리디자인만 다운로드 가능합니다.")

    output_dir = OUTPUT_DIR / redesign_id
    if not output_dir.exists():
        raise HTTPException(404, "출력 디렉토리 없음")

    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        for img_file in sorted(output_dir.iterdir()):
            if img_file.suffix.lower() in (".jpg", ".jpeg", ".png"):
                zf.write(img_file, img_file.name)

    buf.seek(0)
    safe_title = item.get("source_title", "redesign")[:30].replace(" ", "_")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}_{redesign_id}.zip"'},
    )
