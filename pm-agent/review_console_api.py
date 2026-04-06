"""
Review Console API - Phase 4
운영자가 자동 생성 결과물을 검수/수정/승인하는 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import sqlite3
import uuid
from pathlib import Path

from review_workflow import validate_status_transition, get_allowed_next_statuses
from export_service import ExportService
from image_review_manager import ImageReviewManager

router = APIRouter(prefix="/api/phase4/review", tags=["Phase4-Review"])

# Initialize services
export_service = ExportService()
image_manager = ImageReviewManager()

# DB path
DB_PATH = Path(__file__).parent / "data" / "approval_queue.db"


# ============================================================
# Pydantic Models
# ============================================================

class ReviewSaveRequest(BaseModel):
    """Draft 저장 요청"""
    reviewed_naver_title: Optional[str] = None
    reviewed_naver_description: Optional[str] = None
    reviewed_naver_tags: Optional[List[str]] = None

    reviewed_coupang_title: Optional[str] = None
    reviewed_coupang_description: Optional[str] = None
    reviewed_coupang_tags: Optional[List[str]] = None

    reviewed_options_json: Optional[List[str]] = None
    reviewed_price: Optional[float] = None
    reviewed_category: Optional[str] = None

    review_notes: Optional[str] = None

    # Phase 1 콘텐츠 필드
    product_summary: Optional[Dict[str, Any]] = None
    detail_content: Optional[Dict[str, Any]] = None
    image_design: Optional[Dict[str, Any]] = None
    sales_strategy: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None


class ReviewActionRequest(BaseModel):
    """Workflow 액션 요청"""
    review_notes: Optional[str] = None
    reviewed_by: str = "system"


# ============================================================
# Helper Functions
# ============================================================

def get_review_item(review_id: str) -> Optional[Dict[str, Any]]:
    """Review 항목 조회"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM approval_queue WHERE review_id = ?
        ''', (review_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def record_review_history(
    review_id: str,
    action: str,
    previous_state: Optional[Dict] = None,
    changed_fields: Optional[List[str]] = None,
    changes: Optional[Dict] = None,
    changed_by: str = "system",
    change_reason: Optional[str] = None
):
    """review_history에 기록"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        history_id = f"history-{uuid.uuid4().hex[:12]}"

        cursor.execute('''
            INSERT INTO review_history (
                history_id, review_id, action,
                previous_state_json, changed_fields, changes_json,
                changed_by, change_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            history_id,
            review_id,
            action,
            json.dumps(previous_state, ensure_ascii=False) if previous_state else None,
            json.dumps(changed_fields, ensure_ascii=False) if changed_fields else None,
            json.dumps(changes, ensure_ascii=False) if changes else None,
            changed_by,
            change_reason,
            datetime.now().isoformat()
        ))

        conn.commit()


def record_audit_log(
    entity_type: str,
    entity_id: str,
    action: str,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    actor: str = "system",
    reason: Optional[str] = None,
    metadata: Optional[Dict] = None
):
    """audit_log에 기록"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        log_id = f"log-{uuid.uuid4().hex[:12]}"

        cursor.execute('''
            INSERT INTO audit_log (
                log_id, entity_type, entity_id, action,
                old_status, new_status, actor, reason, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log_id,
            entity_type,
            entity_id,
            action,
            old_status,
            new_status,
            actor,
            reason,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            datetime.now().isoformat()
        ))

        conn.commit()


# ============================================================
# API Endpoints
# ============================================================

@router.get("/{review_id}")
def get_review_detail(review_id: str):
    """
    Review 상세 조회
    - generated_* fields (READ-ONLY)
    - reviewed_* fields (EDITABLE)
    - score, decision, validation 결과
    """
    item = get_review_item(review_id)

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    # Parse JSON fields
    if item.get('generated_naver_tags'):
        try:
            item['generated_naver_tags_parsed'] = json.loads(item['generated_naver_tags'])
        except:
            item['generated_naver_tags_parsed'] = []

    if item.get('reviewed_naver_tags'):
        try:
            item['reviewed_naver_tags_parsed'] = json.loads(item['reviewed_naver_tags'])
        except:
            item['reviewed_naver_tags_parsed'] = []

    if item.get('generated_options_json'):
        try:
            item['generated_options_parsed'] = json.loads(item['generated_options_json'])
        except:
            item['generated_options_parsed'] = []

    if item.get('reviewed_options_json'):
        try:
            item['reviewed_options_parsed'] = json.loads(item['reviewed_options_json'])
        except:
            item['reviewed_options_parsed'] = []

    if item.get('reasons_json'):
        try:
            item['reasons'] = json.loads(item['reasons_json'])
        except:
            item['reasons'] = []

    # Get review history
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM review_history
            WHERE review_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (review_id,))

        item['review_history'] = [dict(row) for row in cursor.fetchall()]

    return item


@router.post("/{review_id}/save")
def save_review_draft(review_id: str, request: ReviewSaveRequest):
    """
    Draft 저장 (reviewed_* 필드 업데이트)
    - review_status는 'draft' 또는 'under_review' 유지
    - 변경 사항은 review_history에 기록
    """
    # Get current item
    item = get_review_item(review_id)

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    # Build update dict
    updates = {}
    changed_fields = []

    if request.reviewed_naver_title is not None:
        updates['reviewed_naver_title'] = request.reviewed_naver_title
        changed_fields.append('reviewed_naver_title')

    if request.reviewed_naver_description is not None:
        updates['reviewed_naver_description'] = request.reviewed_naver_description
        changed_fields.append('reviewed_naver_description')

    if request.reviewed_naver_tags is not None:
        updates['reviewed_naver_tags'] = json.dumps(request.reviewed_naver_tags, ensure_ascii=False)
        changed_fields.append('reviewed_naver_tags')

    if request.reviewed_coupang_title is not None:
        updates['reviewed_coupang_title'] = request.reviewed_coupang_title
        changed_fields.append('reviewed_coupang_title')

    if request.reviewed_coupang_description is not None:
        updates['reviewed_coupang_description'] = request.reviewed_coupang_description
        changed_fields.append('reviewed_coupang_description')

    if request.reviewed_coupang_tags is not None:
        updates['reviewed_coupang_tags'] = json.dumps(request.reviewed_coupang_tags, ensure_ascii=False)
        changed_fields.append('reviewed_coupang_tags')

    if request.reviewed_options_json is not None:
        updates['reviewed_options_json'] = json.dumps(request.reviewed_options_json, ensure_ascii=False)
        changed_fields.append('reviewed_options_json')

    if request.reviewed_price is not None:
        updates['reviewed_price'] = request.reviewed_price
        changed_fields.append('reviewed_price')

    if request.reviewed_category is not None:
        updates['reviewed_category'] = request.reviewed_category
        changed_fields.append('reviewed_category')

    if request.review_notes is not None:
        updates['review_notes'] = request.review_notes

    # Phase 1 콘텐츠 필드 저장
    if request.product_summary is not None:
        updates['product_summary_json'] = json.dumps(request.product_summary, ensure_ascii=False)
        changed_fields.append('product_summary_json')

    if request.detail_content is not None:
        updates['detail_content_json'] = json.dumps(request.detail_content, ensure_ascii=False)
        changed_fields.append('detail_content_json')

    if request.image_design is not None:
        updates['image_design_json'] = json.dumps(request.image_design, ensure_ascii=False)
        changed_fields.append('image_design_json')

    if request.sales_strategy is not None:
        updates['sales_strategy_json'] = json.dumps(request.sales_strategy, ensure_ascii=False)
        changed_fields.append('sales_strategy_json')

    if request.risk_assessment is not None:
        updates['risk_assessment_json'] = json.dumps(request.risk_assessment, ensure_ascii=False)
        changed_fields.append('risk_assessment_json')

    if not updates:
        return {"message": "No changes"}

    updates['updated_at'] = datetime.now().isoformat()

    # 콘텐츠가 수정되었으면 content_reviewed_at 업데이트
    if any(field.endswith('_json') for field in changed_fields):
        updates['content_reviewed_at'] = datetime.now().isoformat()

    # If review_status is 'draft', keep it. Otherwise set to 'under_review'
    if item.get('review_status') != 'draft':
        updates['review_status'] = 'under_review'

    # Update database
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        set_parts = [f"{k} = ?" for k in updates.keys()]
        values = list(updates.values()) + [review_id]

        cursor.execute(f'''
            UPDATE approval_queue
            SET {', '.join(set_parts)}
            WHERE review_id = ?
        ''', values)

        conn.commit()

    # Record history
    record_review_history(
        review_id=review_id,
        action='edit',
        changed_fields=changed_fields,
        changed_by="system",
        change_reason=request.review_notes or "Draft saved"
    )

    # Record audit log
    record_audit_log(
        entity_type='approval',
        entity_id=review_id,
        action='draft_saved',
        actor='system',
        metadata={'changed_fields': changed_fields}
    )

    return {
        "message": "Draft saved successfully",
        "review_id": review_id,
        "changed_fields": changed_fields
    }


@router.post("/{review_id}/approve-export")
def approve_for_export(review_id: str, request: ReviewActionRequest):
    """
    Export 승인
    - review_status: any → 'approved_for_export'
    - Export 버튼 활성화
    """
    item = get_review_item(review_id)

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    old_status = item.get('review_status', 'draft')
    new_status = 'approved_for_export'

    # draft → approved_for_export 직접 전환 허용 (워크벤치 원클릭 승인)
    if old_status != 'draft':
        transition_result = validate_status_transition(old_status, new_status)
        if not transition_result.allowed:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid status transition",
                    "message": transition_result.error_message,
                    "current_status": old_status,
                    "requested_status": new_status,
                    "allowed_next_states": transition_result.allowed_next_states
                }
            )

    # Update status
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE approval_queue
            SET review_status = 'approved_for_export',
                reviewed_at = ?,
                reviewed_by = ?,
                review_notes = ?,
                updated_at = ?
            WHERE review_id = ?
        ''', (
            datetime.now().isoformat(),
            request.reviewed_by,
            request.review_notes or "Approved for export",
            datetime.now().isoformat(),
            review_id
        ))

        conn.commit()

    # Record history
    record_review_history(
        review_id=review_id,
        action='approve_export',
        changed_by=request.reviewed_by,
        change_reason=request.review_notes or "Approved for export"
    )

    # Record audit log
    record_audit_log(
        entity_type='approval',
        entity_id=review_id,
        action='approved_for_export',
        old_status=old_status,
        new_status='approved_for_export',
        actor=request.reviewed_by,
        reason=request.review_notes
    )

    return {
        "message": "Approved for export",
        "review_id": review_id,
        "old_status": old_status,
        "new_status": "approved_for_export"
    }


@router.post("/{review_id}/reject")
def reject_review(review_id: str, request: ReviewActionRequest):
    """
    거부
    - review_status: any → 'rejected'
    - Export/Upload 불가
    """
    item = get_review_item(review_id)

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    old_status = item.get('review_status', 'draft')
    new_status = 'rejected'

    # Validate state transition
    transition_result = validate_status_transition(old_status, new_status)
    if not transition_result.allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid status transition",
                "message": transition_result.error_message,
                "current_status": old_status,
                "requested_status": new_status,
                "allowed_next_states": transition_result.allowed_next_states
            }
        )

    # Update status
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE approval_queue
            SET review_status = 'rejected',
                reviewed_at = ?,
                reviewed_by = ?,
                review_notes = ?,
                updated_at = ?
            WHERE review_id = ?
        ''', (
            datetime.now().isoformat(),
            request.reviewed_by,
            request.review_notes or "Rejected",
            datetime.now().isoformat(),
            review_id
        ))

        conn.commit()

    # Record history
    record_review_history(
        review_id=review_id,
        action='reject',
        changed_by=request.reviewed_by,
        change_reason=request.review_notes or "Rejected"
    )

    # Record audit log
    record_audit_log(
        entity_type='approval',
        entity_id=review_id,
        action='rejected',
        old_status=old_status,
        new_status='rejected',
        actor=request.reviewed_by,
        reason=request.review_notes
    )

    return {
        "message": "Rejected",
        "review_id": review_id,
        "old_status": old_status,
        "new_status": "rejected"
    }


@router.post("/{review_id}/hold")
def hold_review(review_id: str, request: ReviewActionRequest):
    """
    보류
    - review_status: any → 'hold'
    - 추가 검토 필요
    """
    item = get_review_item(review_id)

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    old_status = item.get('review_status', 'draft')
    new_status = 'hold'

    # Validate state transition
    transition_result = validate_status_transition(old_status, new_status)
    if not transition_result.allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid status transition",
                "message": transition_result.error_message,
                "current_status": old_status,
                "requested_status": new_status,
                "allowed_next_states": transition_result.allowed_next_states
            }
        )

    # Update status
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE approval_queue
            SET review_status = 'hold',
                reviewed_at = ?,
                reviewed_by = ?,
                review_notes = ?,
                updated_at = ?
            WHERE review_id = ?
        ''', (
            datetime.now().isoformat(),
            request.reviewed_by,
            request.review_notes or "On hold",
            datetime.now().isoformat(),
            review_id
        ))

        conn.commit()

    # Record history
    record_review_history(
        review_id=review_id,
        action='hold',
        changed_by=request.reviewed_by,
        change_reason=request.review_notes or "On hold"
    )

    # Record audit log
    record_audit_log(
        entity_type='approval',
        entity_id=review_id,
        action='hold',
        old_status=old_status,
        new_status='hold',
        actor=request.reviewed_by,
        reason=request.review_notes
    )

    return {
        "message": "On hold",
        "review_id": review_id,
        "old_status": old_status,
        "new_status": "hold"
    }


@router.get("/{review_id}/allowed-actions")
def get_allowed_actions(review_id: str):
    """
    현재 상태에서 가능한 액션 목록 조회
    - UI에서 버튼 활성화/비활성화에 사용
    """
    item = get_review_item(review_id)

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    current_status = item.get('review_status', 'draft')
    allowed_next_states = get_allowed_next_statuses(current_status)

    return {
        "review_id": review_id,
        "current_status": current_status,
        "allowed_next_states": allowed_next_states,
        "available_actions": {
            "can_approve_export": "approved_for_export" in allowed_next_states,
            "can_approve_upload": "approved_for_upload" in allowed_next_states,
            "can_reject": "rejected" in allowed_next_states,
            "can_hold": "hold" in allowed_next_states,
            "can_under_review": "under_review" in allowed_next_states
        }
    }


@router.get("/list/all")
def list_all_reviews(
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    전체 Review 목록 조회
    - review_status로 필터링 가능
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if review_status:
            cursor.execute('''
                SELECT review_id, source_title, score, decision,
                       review_status, reviewed_at, reviewed_by,
                       generated_naver_title, reviewed_naver_title,
                       generated_price, reviewed_price,
                       created_at, updated_at
                FROM approval_queue
                WHERE review_status = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (review_status, limit, offset))
        else:
            cursor.execute('''
                SELECT review_id, source_title, score, decision,
                       review_status, reviewed_at, reviewed_by,
                       generated_naver_title, reviewed_naver_title,
                       generated_price, reviewed_price,
                       created_at, updated_at
                FROM approval_queue
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

        items = [dict(row) for row in cursor.fetchall()]

        # Get total count
        if review_status:
            cursor.execute('SELECT COUNT(*) FROM approval_queue WHERE review_status = ?', (review_status,))
        else:
            cursor.execute('SELECT COUNT(*) FROM approval_queue')

        total = cursor.fetchone()[0]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items
    }


# ============================================================
# Export Endpoints (Phase 4)
# ============================================================

class ExportRequest(BaseModel):
    """CSV Export 요청"""
    review_ids: List[str]
    channel: str  # 'naver' or 'coupang'
    exported_by: str = "system"


@router.post("/export/csv")
def export_to_csv(request: ExportRequest):
    """
    CSV Export (Naver or Coupang)
    - Only approved_for_export or approved_for_upload status allowed
    - Uses reviewed_* fields first, fallback to generated_*
    - Logs to export_log table
    """
    if request.channel == 'naver':
        result = export_service.export_to_naver_csv(
            review_ids=request.review_ids,
            exported_by=request.exported_by
        )
    elif request.channel == 'coupang':
        result = export_service.export_to_coupang_csv(
            review_ids=request.review_ids,
            exported_by=request.exported_by
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {request.channel}")

    if not result['success']:
        raise HTTPException(status_code=400, detail=result.get('error', 'Export failed'))

    return {
        "message": f"Exported to {request.channel} CSV successfully",
        "export_id": result['export_id'],
        "row_count": result['row_count'],
        "file_size": result['file_size'],
        "csv_data": result['csv_data']
    }


@router.get("/export/history")
def get_export_history(channel: Optional[str] = None, limit: int = 20):
    """
    Export 이력 조회
    - channel로 필터링 가능 (naver, coupang)
    """
    history = export_service.get_export_history(channel=channel, limit=limit)

    return {
        "total": len(history),
        "items": history
    }


@router.get("/export/downloadable")
def get_downloadable_items(review_status: Optional[str] = None, limit: int = 50):
    """
    Export 가능한 항목 조회
    - Only approved_for_export or approved_for_upload
    """
    items = export_service.get_exportable_items(
        review_status=review_status,
        limit=limit
    )

    return {
        "total": len(items),
        "items": items
    }


# ============================================================
# Image Review Endpoints (Phase 4)
# ============================================================

class ImageSaveRequest(BaseModel):
    """이미지 검수 정보 저장 요청"""
    reviewed_images: List[Dict[str, Any]]
    operator: str = "system"


class SetPrimaryImageRequest(BaseModel):
    """대표 이미지 지정 요청"""
    image_id: str
    operator: str = "system"


class ReorderImagesRequest(BaseModel):
    """이미지 순서 변경 요청"""
    ordered_image_ids: List[str]
    operator: str = "system"


class ExcludeImageRequest(BaseModel):
    """이미지 제외 요청"""
    image_id: str
    excluded: bool
    note: Optional[str] = None
    operator: str = "system"


class ImageWarningRequest(BaseModel):
    """이미지 경고 저장 요청"""
    image_id: str
    warning_type: str
    note: str
    operator: str = "system"


@router.get("/{review_id}/images")
def get_review_images(review_id: str):
    """
    Review의 이미지 정보 조회
    - original_images: 원본 이미지 목록
    - reviewed_images: 검수된 이미지 정보 (순서, 대표, 제외, 경고 포함)
    """
    images_data = image_manager.get_images(review_id)

    if not images_data:
        raise HTTPException(status_code=404, detail="Images not found for this review")

    return images_data


@router.post("/{review_id}/images/save")
def save_review_images(review_id: str, request: ImageSaveRequest):
    """
    이미지 검수 정보 저장 (Bulk Save)
    - Validates: exactly 1 primary, no excluded primary, at least 1 non-excluded
    - Saves to image_review table
    """
    result = image_manager.save_images(
        review_id=review_id,
        reviewed_images=request.reviewed_images,
        operator=request.operator
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail={
            "errors": result['errors'],
            "warnings": result.get('warnings', [])
        })

    return {
        "message": "Images saved successfully",
        "image_review_id": result['image_review_id'],
        "warnings": result.get('warnings', [])
    }


@router.post("/{review_id}/images/set-primary")
def set_primary_image(review_id: str, request: SetPrimaryImageRequest):
    """
    대표 이미지 지정
    - Clears previous primary
    - Cannot set excluded image as primary
    """
    result = image_manager.set_primary_image(
        review_id=review_id,
        image_id=request.image_id,
        operator=request.operator
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail={"errors": result['errors']})

    return {
        "message": "Primary image set successfully",
        "image_review_id": result['image_review_id']
    }


@router.post("/{review_id}/images/reorder")
def reorder_images(review_id: str, request: ReorderImagesRequest):
    """
    이미지 순서 변경
    - Updates display_order for all images
    """
    result = image_manager.reorder_images(
        review_id=review_id,
        ordered_image_ids=request.ordered_image_ids,
        operator=request.operator
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail={"errors": result['errors']})

    return {
        "message": "Images reordered successfully",
        "image_review_id": result['image_review_id']
    }


@router.post("/{review_id}/images/exclude")
def exclude_image(review_id: str, request: ExcludeImageRequest):
    """
    이미지 제외/복원 처리
    - If excluding primary image, automatically selects next available as primary
    """
    result = image_manager.exclude_image(
        review_id=review_id,
        image_id=request.image_id,
        excluded=request.excluded,
        operator=request.operator,
        note=request.note
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail={"errors": result['errors']})

    return {
        "message": f"Image {'excluded' if request.excluded else 'restored'} successfully",
        "image_review_id": result['image_review_id']
    }


@router.post("/{review_id}/images/warning")
def add_image_warning(review_id: str, request: ImageWarningRequest):
    """
    이미지 경고 저장
    - Warning types: low_quality, wrong_aspect, text_overlay, etc.
    """
    result = image_manager.save_image_warning(
        review_id=review_id,
        image_id=request.image_id,
        warning_type=request.warning_type,
        note=request.note,
        operator=request.operator
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail={"errors": result['errors']})

    return {
        "message": "Image warning saved successfully",
        "image_review_id": result['image_review_id']
    }


@router.get("/{review_id}/images/exportable")
def get_exportable_images(review_id: str):
    """
    Export 가능한 이미지 조회
    - Returns primary image and all non-excluded images
    - Validates: at least 1 exportable image exists
    """
    result = image_manager.get_exportable_images(review_id)

    if not result['success']:
        raise HTTPException(status_code=400, detail={"errors": result['errors']})

    return {
        "primary_image": result['primary_image'],
        "all_images": result['all_images'],
        "exportable_count": result['exportable_count']
    }
