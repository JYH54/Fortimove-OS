"""
Semi-Auto Uploader - 검토-승인-업로드 Flow
Phase 3 Core Module
"""

import logging
import json
import sqlite3
import csv
import io
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from channel_upload_manager import ChannelUploadManager
from upload_validator import UploadValidator

logger = logging.getLogger(__name__)


class SemiAutoUploader:
    """Semi-automatic upload flow with review-confirm-upload structure"""

    def __init__(self):
        self.upload_manager = ChannelUploadManager()
        self.validator = UploadValidator()
        self.db_path = Path(__file__).parent / "data" / "approval_queue.db"

    def get_ready_to_upload_items(
        self,
        channel: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        업로드 준비 완료된 항목 조회

        Status flow:
        pending → validated → ready_to_upload → uploading → completed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if channel:
                    cursor.execute('''
                        SELECT * FROM channel_upload_queue
                        WHERE upload_status = 'ready_to_upload' AND channel = ?
                        ORDER BY ready_at DESC
                        LIMIT ?
                    ''', (channel, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM channel_upload_queue
                        WHERE upload_status = 'ready_to_upload'
                        ORDER BY ready_at DESC
                        LIMIT ?
                    ''', (limit,))

                items = [dict(row) for row in cursor.fetchall()]

                # Parse JSON fields
                for item in items:
                    if item.get('content_json'):
                        try:
                            item['content'] = json.loads(item['content_json'])
                        except:
                            item['content'] = {}

                return items

        except Exception as e:
            logger.error(f"[SemiAutoUploader] Failed to get ready items: {e}")
            return []

    def export_to_csv(
        self,
        upload_ids: List[str],
        include_fields: Optional[List[str]] = None
    ) -> str:
        """
        Upload 항목을 CSV로 export

        Returns:
            CSV string
        """
        try:
            items = []
            for upload_id in upload_ids:
                item = self.upload_manager.get_upload_by_id(upload_id)
                if item:
                    items.append(item)

            if not items:
                return ""

            # Default fields
            if include_fields is None:
                include_fields = [
                    'upload_id', 'channel', 'review_id',
                    'title', 'price', 'description',
                    'upload_status', 'validation_status',
                    'created_at'
                ]

            # Create CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=include_fields)

            writer.writeheader()

            for item in items:
                # Parse content_json
                content = {}
                if item.get('content_json'):
                    try:
                        content = json.loads(item['content_json'])
                    except:
                        pass

                row = {}
                for field in include_fields:
                    if field in item:
                        row[field] = item[field]
                    elif field in content:
                        row[field] = content[field]
                    else:
                        row[field] = ''

                writer.writerow(row)

            return output.getvalue()

        except Exception as e:
            logger.error(f"[SemiAutoUploader] Export failed: {e}")
            return ""

    def export_to_naver_format(self, upload_ids: List[str]) -> str:
        """
        Naver 스마트스토어 업로드 형식으로 export

        Naver Required Fields:
        - 상품명 (title)
        - 판매가 (price)
        - 상품상세 (description)
        - 옵션 (options)
        - 배송비 (shipping_cost)
        - 반품정보 (return_policy)
        - 이미지URL (images)
        """
        try:
            items = []
            for upload_id in upload_ids:
                item = self.upload_manager.get_upload_by_id(upload_id)
                if item and item.get('channel') == 'naver':
                    items.append(item)

            if not items:
                return ""

            # Naver CSV fields
            fields = [
                '상품명', '판매가', '재고수량', '상품상세',
                '옵션', '배송비', '반품정보', '이미지URL1',
                '이미지URL2', '이미지URL3'
            ]

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)

            writer.writeheader()

            for item in items:
                content = {}
                if item.get('content_json'):
                    try:
                        content = json.loads(item['content_json'])
                    except:
                        pass

                images = content.get('images', [])

                row = {
                    '상품명': content.get('title', ''),
                    '판매가': content.get('price', 0),
                    '재고수량': 100,  # Default
                    '상품상세': content.get('description', ''),
                    '옵션': self._format_options_naver(content.get('options', [])),
                    '배송비': 3000,  # Default
                    '반품정보': content.get('return_policy', '7일 이내 무료 반품'),
                    '이미지URL1': images[0] if len(images) > 0 else '',
                    '이미지URL2': images[1] if len(images) > 1 else '',
                    '이미지URL3': images[2] if len(images) > 2 else ''
                }

                writer.writerow(row)

            return output.getvalue()

        except Exception as e:
            logger.error(f"[SemiAutoUploader] Naver export failed: {e}")
            return ""

    def export_to_coupang_format(self, upload_ids: List[str]) -> str:
        """
        Coupang 파트너스 업로드 형식으로 export

        Coupang Required Fields:
        - 상품명 (title)
        - 판매가 (price)
        - 상품설명 (description)
        - 배송정보 (shipping_info)
        - 반품정책 (return_policy)
        """
        try:
            items = []
            for upload_id in upload_ids:
                item = self.upload_manager.get_upload_by_id(upload_id)
                if item and item.get('channel') == 'coupang':
                    items.append(item)

            if not items:
                return ""

            fields = [
                '상품명', '판매가', '할인가', '상품설명',
                '배송정보', '반품정책', '대표이미지'
            ]

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)

            writer.writeheader()

            for item in items:
                content = {}
                if item.get('content_json'):
                    try:
                        content = json.loads(item['content_json'])
                    except:
                        pass

                images = content.get('images', [])

                row = {
                    '상품명': content.get('title', ''),
                    '판매가': content.get('price', 0),
                    '할인가': content.get('price', 0),  # No discount by default
                    '상품설명': content.get('description', ''),
                    '배송정보': '오늘출발 (로켓배송)',
                    '반품정책': content.get('return_policy', '7일 이내 무료 반품'),
                    '대표이미지': images[0] if images else ''
                }

                writer.writerow(row)

            return output.getvalue()

        except Exception as e:
            logger.error(f"[SemiAutoUploader] Coupang export failed: {e}")
            return ""

    def mark_as_uploading(self, upload_id: str, actor: str = "system"):
        """업로드 중 상태로 변경"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE channel_upload_queue
                    SET upload_status = 'uploading',
                        updated_at = ?
                    WHERE upload_id = ?
                ''', (datetime.now().isoformat(), upload_id))

                conn.commit()

                logger.info(f"[SemiAutoUploader] {upload_id} → uploading")

        except Exception as e:
            logger.error(f"[SemiAutoUploader] Failed to mark uploading: {e}")

    def mark_as_completed(
        self,
        upload_id: str,
        marketplace_id: Optional[str] = None,
        actor: str = "system"
    ):
        """업로드 완료 상태로 변경"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Store marketplace ID in export_data
                export_data = {}
                if marketplace_id:
                    export_data['marketplace_id'] = marketplace_id

                cursor.execute('''
                    UPDATE channel_upload_queue
                    SET upload_status = 'completed',
                        uploaded_at = ?,
                        export_data = ?,
                        updated_at = ?
                    WHERE upload_id = ?
                ''', (
                    datetime.now().isoformat(),
                    json.dumps(export_data, ensure_ascii=False),
                    datetime.now().isoformat(),
                    upload_id
                ))

                conn.commit()

                logger.info(f"[SemiAutoUploader] {upload_id} → completed")

        except Exception as e:
            logger.error(f"[SemiAutoUploader] Failed to mark completed: {e}")

    def mark_as_failed(
        self,
        upload_id: str,
        error_message: str,
        actor: str = "system"
    ):
        """업로드 실패 상태로 변경"""
        try:
            item = self.upload_manager.get_upload_by_id(upload_id)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE channel_upload_queue
                    SET upload_status = 'failed',
                        last_error = ?,
                        retry_count = ?,
                        updated_at = ?
                    WHERE upload_id = ?
                ''', (
                    error_message,
                    item.get('retry_count', 0) + 1,
                    datetime.now().isoformat(),
                    upload_id
                ))

                conn.commit()

                logger.info(f"[SemiAutoUploader] {upload_id} → failed: {error_message}")

        except Exception as e:
            logger.error(f"[SemiAutoUploader] Failed to mark failed: {e}")

    def _format_options_naver(self, options: List[str]) -> str:
        """Naver 옵션 형식으로 변환"""
        if not options:
            return ""

        # Format: "색상:빨강|파랑|노랑;사이즈:S|M|L"
        # For simplicity, just join with |
        return "|".join(options)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    uploader = SemiAutoUploader()

    # Test: Get ready to upload items
    ready_items = uploader.get_ready_to_upload_items(limit=5)
    print(f"\n✅ Ready to upload: {len(ready_items)} items")

    if ready_items:
        upload_ids = [item['upload_id'] for item in ready_items]

        # Test: Export to generic CSV
        csv_data = uploader.export_to_csv(upload_ids)
        print(f"\n📄 Generic CSV ({len(csv_data)} bytes):")
        print(csv_data[:200] + "...")

        # Test: Export to Naver format
        naver_csv = uploader.export_to_naver_format(upload_ids)
        if naver_csv:
            print(f"\n📄 Naver CSV ({len(naver_csv)} bytes):")
            print(naver_csv[:200] + "...")

        # Test: Export to Coupang format
        coupang_csv = uploader.export_to_coupang_format(upload_ids)
        if coupang_csv:
            print(f"\n📄 Coupang CSV ({len(coupang_csv)} bytes):")
            print(coupang_csv[:200] + "...")
