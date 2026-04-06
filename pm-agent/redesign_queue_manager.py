"""
Redesign Queue Manager — 상세페이지 리디자인 대기열 관리
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("APPROVAL_DB_PATH", str(Path(__file__).parent / "data" / "approval_queue.db"))
MIGRATION_PATH = Path(__file__).parent / "migrations" / "005_redesign_schema.sql"


class RedesignQueueManager:

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        if MIGRATION_PATH.exists():
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(MIGRATION_PATH.read_text())

    def _now(self) -> str:
        return datetime.now().isoformat()

    # ── Create ────────────────────────────────────────────

    def add_to_queue(
        self,
        source_title: str,
        source_images: List[str],
        source_type: str = "manual_upload",
        moodtone: str = "premium",
        category: str = "general",
        review_id: Optional[str] = None,
        trigger_type: Optional[str] = None,
        trigger_score: Optional[int] = None,
    ) -> str:
        redesign_id = f"rdsg-{uuid.uuid4().hex[:12]}"
        now = self._now()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO redesign_queue
                   (redesign_id, review_id, source_type, source_title,
                    source_images_json, moodtone, category, status,
                    trigger_type, trigger_score, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    redesign_id, review_id, source_type, source_title,
                    json.dumps(source_images, ensure_ascii=False),
                    moodtone, category, "waiting",
                    trigger_type, trigger_score, now, now,
                ),
            )
        logger.info(f"[{redesign_id}] 큐 등록: {source_title} ({source_type})")
        return redesign_id

    # ── Read ──────────────────────────────────────────────

    def list_queue(
        self,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM redesign_queue WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_item(self, redesign_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM redesign_queue WHERE redesign_id = ?",
                (redesign_id,),
            ).fetchone()
        return dict(row) if row else None

    # ── Update ────────────────────────────────────────────

    def update_status(
        self,
        redesign_id: str,
        status: str,
        error_message: Optional[str] = None,
    ):
        now = self._now()
        fields = ["status = ?", "updated_at = ?"]
        params: list = [status, now]

        if status == "processing":
            fields.append("processing_started_at = ?")
            params.append(now)
        elif status in ("completed", "failed"):
            fields.append("processing_completed_at = ?")
            params.append(now)

        if error_message:
            fields.append("error_message = ?")
            params.append(error_message)

        params.append(redesign_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE redesign_queue SET {', '.join(fields)} WHERE redesign_id = ?",
                params,
            )

    def save_pipeline_results(
        self,
        redesign_id: str,
        localized_images: Optional[Any] = None,
        text_content: Optional[Any] = None,
        composed_images: Optional[Any] = None,
        output_directory: Optional[str] = None,
    ):
        fields = ["updated_at = ?"]
        params: list = [self._now()]

        if localized_images is not None:
            fields.append("localized_images_json = ?")
            params.append(json.dumps(localized_images, ensure_ascii=False))
        if text_content is not None:
            fields.append("text_content_json = ?")
            params.append(json.dumps(text_content, ensure_ascii=False))
        if composed_images is not None:
            fields.append("composed_images_json = ?")
            params.append(json.dumps(composed_images, ensure_ascii=False))
        if output_directory is not None:
            fields.append("output_directory = ?")
            params.append(output_directory)

        params.append(redesign_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE redesign_queue SET {', '.join(fields)} WHERE redesign_id = ?",
                params,
            )

    def save_edit_overrides(self, redesign_id: str, overrides: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE redesign_queue SET edit_overrides_json = ?, updated_at = ? WHERE redesign_id = ?",
                (json.dumps(overrides, ensure_ascii=False), self._now(), redesign_id),
            )

    # ── Delete ────────────────────────────────────────────

    def delete_item(self, redesign_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM redesign_queue WHERE redesign_id = ?", (redesign_id,))
