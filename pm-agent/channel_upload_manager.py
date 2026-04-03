"""
Channel Upload Manager - 채널별 업로드 대기열 관리
"""

import logging
import sqlite3
import json
import uuid
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ChannelUploadManager:
    """채널별 업로드 대기열 관리"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Use same path as ApprovalQueueManager for consistency
            db_path = os.getenv("APPROVAL_DB_PATH", "data/approval_queue.db")

        self.db_path = db_path

    def add_upload_item(
        self,
        review_id: str,
        channel: str,
        content: Dict[str, Any]
    ) -> str:
        """업로드 항목 추가"""
        upload_id = f"upload-{uuid.uuid4().hex[:12]}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO channel_upload_queue (
                    upload_id, review_id, channel, content_json,
                    upload_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                upload_id,
                review_id,
                channel,
                json.dumps(content, ensure_ascii=False),
                'pending',
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
        
        logger.info(f"[{upload_id}] 업로드 항목 추가: {channel}")
        return upload_id

    def get_pending_uploads(self, channel: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """대기 중인 업로드 조회"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if channel:
                cursor.execute('''
                    SELECT * FROM channel_upload_queue
                    WHERE upload_status = 'pending' AND channel = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (channel, limit))
            else:
                cursor.execute('''
                    SELECT * FROM channel_upload_queue
                    WHERE upload_status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]

    def get_upload_by_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """특정 업로드 항목 조회"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM channel_upload_queue
                WHERE upload_id = ?
            ''', (upload_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def update_status(self, upload_id: str, status: str, error: Optional[str] = None):
        """업로드 상태 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if status == 'completed':
                cursor.execute('''
                    UPDATE channel_upload_queue
                    SET upload_status = ?,
                        uploaded_at = ?,
                        updated_at = ?
                    WHERE upload_id = ?
                ''', (status, datetime.now().isoformat(), datetime.now().isoformat(), upload_id))
            else:
                cursor.execute('''
                    UPDATE channel_upload_queue
                    SET upload_status = ?,
                        upload_error = ?,
                        updated_at = ?
                    WHERE upload_id = ?
                ''', (status, error, datetime.now().isoformat(), upload_id))

            conn.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    manager = ChannelUploadManager()
    
    # 테스트
    upload_id = manager.add_upload_item(
        review_id="test-123",
        channel="naver",
        content={"title": "테스트 상품", "description": "테스트"}
    )
    
    print(f"업로드 ID: {upload_id}")
    
    pending = manager.get_pending_uploads(channel="naver", limit=5)
    print(f"대기 중: {len(pending)}개")
