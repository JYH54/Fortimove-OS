"""
Phase 3 Dashboard APIs
Approval Queue & Upload Queue 관리 API
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

from approval_queue import ApprovalQueueManager
from channel_upload_manager import ChannelUploadManager
from upload_validator import UploadValidator
from scoring_engine import ScoringEngine
try:
    from content_agent import ContentAgent
except ImportError:
    ContentAgent = None

router = APIRouter(prefix="/api/phase3", tags=["Phase3"])


# ============================================================
# Pydantic Models
# ============================================================

class ApprovalActionRequest(BaseModel):
    action: str  # 'approve', 'reject', 'hold', 'rescore', 'regenerate_content'
    note: Optional[str] = None
    actor: str = "system"


class UploadActionRequest(BaseModel):
    action: str  # 'validate', 'retry', 'export', 'mark_ready'
    actor: str = "system"


class BatchApprovalRequest(BaseModel):
    review_ids: List[str]
    action: str  # 'approve', 'reject'
    actor: str = "system"


# ============================================================
# Dependencies
# ============================================================

def get_approval_queue():
    return ApprovalQueueManager()


def get_upload_manager():
    return ChannelUploadManager()


def get_validator():
    return UploadValidator()


def get_scoring_engine():
    return ScoringEngine()


def get_content_agent():
    return ContentAgent()


# ============================================================
# Approval Queue APIs
# ============================================================

@router.get("/approval/list")
def list_approval_items(
    status: Optional[str] = Query(None, description="pending/approved/rejected/hold"),
    sort: Optional[str] = Query("priority", description="priority/score/created_at"),
    order: Optional[str] = Query("asc", description="asc/desc"),
    limit: Optional[int] = Query(50, le=200),
    offset: Optional[int] = Query(0),
    aq: ApprovalQueueManager = Depends(get_approval_queue)
):
    """
    Approval Queue 목록 조회 (필터/정렬/페이징)
    """
    try:
        # Get items
        if status:
            items = aq.list_items(reviewer_status=status)
        else:
            # Get all items
            all_items = []
            for s in ['pending', 'approved', 'rejected', 'needs_edit']:
                all_items.extend(aq.list_items(reviewer_status=s))
            items = all_items

        # Sort
        reverse = (order == "desc")

        if sort == "priority":
            items.sort(key=lambda x: x.get('priority', 999), reverse=reverse)
        elif sort == "score":
            items.sort(key=lambda x: x.get('score', 0), reverse=reverse)
        elif sort == "created_at":
            items.sort(key=lambda x: x.get('created_at', ''), reverse=reverse)

        # Pagination
        total = len(items)
        items = items[offset:offset + limit]

        # Parse JSON fields
        for item in items:
            if item.get('reasons_json'):
                try:
                    item['reasons'] = json.loads(item['reasons_json'])
                except:
                    item['reasons'] = []

            if item.get('audit_trail'):
                try:
                    item['audit_trail_parsed'] = json.loads(item['audit_trail'])
                except:
                    item['audit_trail_parsed'] = []

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": items
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approval/{review_id}")
def get_approval_item(
    review_id: str,
    aq: ApprovalQueueManager = Depends(get_approval_queue)
):
    """특정 Approval 항목 상세 조회"""
    try:
        item = aq.get_item(review_id)

        if not item:
            raise HTTPException(status_code=404, detail="Review not found")

        # Parse JSON fields
        if item.get('reasons_json'):
            try:
                item['reasons'] = json.loads(item['reasons_json'])
            except:
                item['reasons'] = []

        if item.get('source_data'):
            try:
                item['source_data_parsed'] = json.loads(item['source_data'])
            except:
                item['source_data_parsed'] = {}

        if item.get('agent_output'):
            try:
                item['agent_output_parsed'] = json.loads(item['agent_output'])
            except:
                item['agent_output_parsed'] = {}

        if item.get('audit_trail'):
            try:
                item['audit_trail_parsed'] = json.loads(item['audit_trail'])
            except:
                item['audit_trail_parsed'] = []

        return item

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approval/{review_id}/action")
def perform_approval_action(
    review_id: str,
    request: ApprovalActionRequest,
    aq: ApprovalQueueManager = Depends(get_approval_queue),
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),
    content_agent: ContentAgent = Depends(get_content_agent)
):
    """Approval 항목 액션 실행"""
    try:
        item = aq.get_item(review_id)
        if not item:
            raise HTTPException(status_code=404, detail="Review not found")

        action = request.action

        if action == "approve":
            # Mark as approved
            aq.update_item(review_id, {
                "reviewer_status": "approved",
                "approved_at": datetime.now().isoformat(),
                "approved_by": request.actor,
                "reviewer_note": request.note or "Approved"
            })

            # Append audit trail
            _append_audit_trail(aq, review_id, {
                "action": "approved",
                "actor": request.actor,
                "timestamp": datetime.now().isoformat(),
                "note": request.note
            })

            return {"message": "Approved successfully", "review_id": review_id}

        elif action == "reject":
            aq.update_item(review_id, {
                "reviewer_status": "rejected",
                "reviewer_note": request.note or "Rejected"
            })

            _append_audit_trail(aq, review_id, {
                "action": "rejected",
                "actor": request.actor,
                "timestamp": datetime.now().isoformat(),
                "note": request.note
            })

            return {"message": "Rejected successfully", "review_id": review_id}

        elif action == "hold":
            aq.update_item(review_id, {
                "decision": "hold",
                "reviewer_note": request.note or "On hold"
            })

            _append_audit_trail(aq, review_id, {
                "action": "hold",
                "actor": request.actor,
                "timestamp": datetime.now().isoformat(),
                "note": request.note
            })

            return {"message": "Put on hold", "review_id": review_id}

        elif action == "rescore":
            # Re-run scoring
            scoring_result = scoring_engine.score_product(item)

            aq.update_item(review_id, {
                "score": scoring_result['score'],
                "decision": scoring_result['decision'],
                "reasons_json": json.dumps(scoring_result['reasons'], ensure_ascii=False),
                "scoring_updated_at": datetime.now().isoformat(),
                "retry_count": item.get('retry_count', 0) + 1
            })

            _append_audit_trail(aq, review_id, {
                "action": "rescored",
                "actor": request.actor,
                "timestamp": datetime.now().isoformat(),
                "metadata": {"new_score": scoring_result['score'], "new_decision": scoring_result['decision']}
            })

            return {
                "message": "Rescored successfully",
                "review_id": review_id,
                "new_score": scoring_result['score'],
                "new_decision": scoring_result['decision']
            }

        elif action == "regenerate_content":
            # Re-generate content
            # TODO: Implement content regeneration
            return {"message": "Content regeneration not implemented yet"}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approval/batch")
def batch_approve_or_reject(
    request: BatchApprovalRequest,
    aq: ApprovalQueueManager = Depends(get_approval_queue)
):
    """일괄 승인/거부"""
    try:
        results = []

        for review_id in request.review_ids:
            try:
                if request.action == "approve":
                    aq.update_item(review_id, {
                        "reviewer_status": "approved",
                        "approved_at": datetime.now().isoformat(),
                        "approved_by": request.actor
                    })
                elif request.action == "reject":
                    aq.update_item(review_id, {
                        "reviewer_status": "rejected"
                    })

                _append_audit_trail(aq, review_id, {
                    "action": f"batch_{request.action}",
                    "actor": request.actor,
                    "timestamp": datetime.now().isoformat()
                })

                results.append({"review_id": review_id, "success": True})

            except Exception as e:
                results.append({"review_id": review_id, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r['success'])

        return {
            "message": f"Batch {request.action} completed",
            "total": len(request.review_ids),
            "success": success_count,
            "failed": len(request.review_ids) - success_count,
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Upload Queue APIs
# ============================================================

@router.get("/upload/list")
def list_upload_items(
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    validation_status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    upload_mgr: ChannelUploadManager = Depends(get_upload_manager)
):
    """Upload Queue 목록 조회"""
    try:
        # Get pending uploads (filtered by channel if specified)
        items = upload_mgr.get_pending_uploads(channel=channel, limit=1000)

        # Filter by status if specified
        if status:
            items = [item for item in items if item.get('upload_status') == status]

        if validation_status:
            items = [item for item in items if item.get('validation_status') == validation_status]

        # Pagination
        total = len(items)
        items = items[offset:offset + limit]

        # Parse content_json
        for item in items:
            if item.get('content_json'):
                try:
                    item['content'] = json.loads(item['content_json'])
                except:
                    item['content'] = {}

            if item.get('validation_errors'):
                try:
                    item['validation_errors_parsed'] = json.loads(item['validation_errors'])
                except:
                    item['validation_errors_parsed'] = []

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": items
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upload/{upload_id}")
def get_upload_item(
    upload_id: str,
    upload_mgr: ChannelUploadManager = Depends(get_upload_manager)
):
    """특정 Upload 항목 조회"""
    try:
        item = upload_mgr.get_upload_by_id(upload_id)

        if not item:
            raise HTTPException(status_code=404, detail="Upload item not found")

        # Parse JSON fields
        if item.get('content_json'):
            try:
                item['content'] = json.loads(item['content_json'])
            except:
                item['content'] = {}

        if item.get('validation_errors'):
            try:
                item['validation_errors_parsed'] = json.loads(item['validation_errors'])
            except:
                item['validation_errors_parsed'] = []

        return item

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{upload_id}/action")
def perform_upload_action(
    upload_id: str,
    request: UploadActionRequest,
    upload_mgr: ChannelUploadManager = Depends(get_upload_manager),
    validator: UploadValidator = Depends(get_validator)
):
    """Upload 항목 액션 실행"""
    try:
        item = upload_mgr.get_upload_by_id(upload_id)
        if not item:
            raise HTTPException(status_code=404, detail="Upload item not found")

        action = request.action

        if action == "validate":
            # Run validation
            channel = item['channel']
            content = json.loads(item['content_json'])

            validation_result = validator.validate(channel, content)

            # Update validation status
            import sqlite3
            from pathlib import Path
            db_path = Path(__file__).parent / "data" / "approval_queue.db"

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE channel_upload_queue
                    SET validation_status = ?,
                        validation_errors = ?,
                        validated_at = ?
                    WHERE upload_id = ?
                ''', (
                    "validated" if validation_result['valid'] else "validation_failed",
                    json.dumps(validation_result.get('errors', []), ensure_ascii=False),
                    datetime.now().isoformat(),
                    upload_id
                ))

                conn.commit()

            return {
                "message": "Validation completed",
                "upload_id": upload_id,
                "valid": validation_result['valid'],
                "errors": validation_result.get('errors', []),
                "warnings": validation_result.get('warnings', [])
            }

        elif action == "retry":
            # Reset status for retry
            upload_mgr.update_status(upload_id, "pending")

            return {"message": "Retry initiated", "upload_id": upload_id}

        elif action == "mark_ready":
            # Mark as ready to upload
            import sqlite3
            from pathlib import Path
            db_path = Path(__file__).parent / "data" / "approval_queue.db"

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE channel_upload_queue
                    SET upload_status = 'ready_to_upload',
                        ready_at = ?,
                        ready_by = ?
                    WHERE upload_id = ?
                ''', (
                    datetime.now().isoformat(),
                    request.actor,
                    upload_id
                ))

                conn.commit()

            return {"message": "Marked as ready to upload", "upload_id": upload_id}

        elif action == "export":
            # Export to CSV/Excel
            # TODO: Implement export
            return {"message": "Export not implemented yet"}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Helper Functions
# ============================================================

def _append_audit_trail(aq: ApprovalQueueManager, review_id: str, trail_entry: dict):
    """approval_queue의 audit_trail에 추가"""
    try:
        item = aq.get_item(review_id)
        current_trail = json.loads(item.get('audit_trail', '[]'))
        current_trail.append(trail_entry)

        aq.update_item(review_id, {
            "audit_trail": json.dumps(current_trail, ensure_ascii=False)
        })

    except Exception as e:
        # Audit trail은 실패해도 전체 요청을 실패시키지 않음
        import logging
        logging.error(f"Failed to append audit trail: {e}")
