"""
Export Service - Phase 4
reviewed_* 필드 기반 CSV export (generated_* fallback)
"""

import logging
import json
import sqlite3
import csv
import io
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from image_review_manager import ImageReviewManager

logger = logging.getLogger(__name__)

# DB path
DB_PATH = Path(__file__).parent / "data" / "approval_queue.db"


class ExportService:
    """
    Phase 4 Export Service

    Principles:
    1. Export uses reviewed_* fields first, fallback to generated_* if null
    2. Only approved_for_export or approved_for_upload status can export
    3. All exports logged in export_log table
    4. Export creates downloadable CSV files
    5. Images from image_review_manager (primary image priority)
    """

    def __init__(self):
        self.db_path = DB_PATH
        self.image_manager = ImageReviewManager()

    def get_exportable_items(
        self,
        review_status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Export 가능한 항목 조회

        Args:
            review_status: 'approved_for_export' or 'approved_for_upload' (None이면 둘 다)
            limit: 최대 조회 개수

        Returns:
            List of review items
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if review_status:
                    cursor.execute('''
                        SELECT * FROM approval_queue
                        WHERE review_status = ?
                        ORDER BY updated_at DESC
                        LIMIT ?
                    ''', (review_status, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM approval_queue
                        WHERE review_status IN ('approved_for_export', 'approved_for_upload')
                        ORDER BY updated_at DESC
                        LIMIT ?
                    ''', (limit,))

                items = [dict(row) for row in cursor.fetchall()]

                logger.info(f"Found {len(items)} exportable items")
                return items

        except Exception as e:
            logger.error(f"Failed to get exportable items: {e}")
            return []

    def _get_field_value(self, item: Dict[str, Any], field_name: str) -> Any:
        """
        reviewed_* 우선, 없으면 generated_* fallback

        Args:
            item: approval_queue row
            field_name: 'naver_title', 'naver_description', 'price', etc.

        Returns:
            Field value (reviewed or generated)
        """
        reviewed_key = f"reviewed_{field_name}"
        generated_key = f"generated_{field_name}"

        # Try reviewed first
        reviewed_value = item.get(reviewed_key)
        if reviewed_value is not None and reviewed_value != '':
            return reviewed_value

        # Fallback to generated
        generated_value = item.get(generated_key)
        return generated_value if generated_value is not None else ''

    def export_to_naver_csv(
        self,
        review_ids: List[str],
        exported_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Naver 스마트스토어 CSV export

        Args:
            review_ids: List of review_id to export
            exported_by: Operator name

        Returns:
            {
                "success": bool,
                "export_id": str,
                "csv_data": str,
                "row_count": int,
                "file_size": int
            }
        """
        try:
            items = self._get_items_by_ids(review_ids)

            if not items:
                return {"success": False, "error": "No items found"}

            # Validate all items are approved
            not_approved = [
                item['review_id'] for item in items
                if item.get('review_status') not in ['approved_for_export', 'approved_for_upload']
            ]

            if not_approved:
                return {
                    "success": False,
                    "error": f"Items not approved: {', '.join(not_approved)}"
                }

            # Naver CSV fields
            fields = [
                '상품명', '판매가', '재고수량', '상품상세',
                '태그', '배송비', '반품정보',
                '이미지URL1', '이미지URL2', '이미지URL3'
            ]

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()

            for item in items:
                # Get reviewed or generated values
                title = self._get_field_value(item, 'naver_title')
                description = self._get_field_value(item, 'naver_description')
                price = self._get_field_value(item, 'price') or 0

                # Parse tags (JSON)
                tags_json = self._get_field_value(item, 'naver_tags')
                try:
                    tags = json.loads(tags_json) if tags_json else []
                except:
                    tags = []

                # Get exportable images from image_review_manager
                images = []
                exportable_result = self.image_manager.get_exportable_images(item['review_id'])

                if exportable_result['success']:
                    # Primary image first
                    primary_img = exportable_result['primary_image']
                    images.append(primary_img['url'])

                    # Add other exportable images
                    for img in exportable_result['all_images']:
                        # Use 'url' for comparison since image_id might not exist
                        if img.get('url') != primary_img.get('url'):
                            images.append(img['url'])
                else:
                    # Fallback to source_data if image review not available
                    if item.get('source_data_json'):
                        try:
                            source_data = json.loads(item['source_data_json'])
                            images = source_data.get('images', [])
                        except:
                            pass

                row = {
                    '상품명': title,
                    '판매가': price,
                    '재고수량': 100,  # Default
                    '상품상세': description,
                    '태그': ', '.join(tags),
                    '배송비': 3000,  # Default
                    '반품정보': '7일 이내 무료 반품',
                    '이미지URL1': images[0] if len(images) > 0 else '',
                    '이미지URL2': images[1] if len(images) > 1 else '',
                    '이미지URL3': images[2] if len(images) > 2 else ''
                }

                writer.writerow(row)

            csv_data = output.getvalue()

            # Log export
            export_id = self._log_export(
                channel='naver',
                review_ids=review_ids,
                export_format='csv',
                row_count=len(items),
                file_size=len(csv_data.encode('utf-8')),
                exported_by=exported_by
            )

            return {
                "success": True,
                "export_id": export_id,
                "csv_data": csv_data,
                "row_count": len(items),
                "file_size": len(csv_data.encode('utf-8'))
            }

        except Exception as e:
            logger.error(f"Naver CSV export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_to_coupang_csv(
        self,
        review_ids: List[str],
        exported_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Coupang 파트너스 CSV export

        Args:
            review_ids: List of review_id to export
            exported_by: Operator name

        Returns:
            {
                "success": bool,
                "export_id": str,
                "csv_data": str,
                "row_count": int,
                "file_size": int
            }
        """
        try:
            items = self._get_items_by_ids(review_ids)

            if not items:
                return {"success": False, "error": "No items found"}

            # Validate all items are approved
            not_approved = [
                item['review_id'] for item in items
                if item.get('review_status') not in ['approved_for_export', 'approved_for_upload']
            ]

            if not_approved:
                return {
                    "success": False,
                    "error": f"Items not approved: {', '.join(not_approved)}"
                }

            # Coupang CSV fields
            fields = [
                '상품명', '판매가', '할인가', '상품설명',
                '태그', '배송정보', '반품정책', '대표이미지'
            ]

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()

            for item in items:
                # Get reviewed or generated values
                title = self._get_field_value(item, 'coupang_title')
                description = self._get_field_value(item, 'coupang_description')
                price = self._get_field_value(item, 'price') or 0

                # Parse tags (JSON)
                tags_json = self._get_field_value(item, 'coupang_tags')
                try:
                    tags = json.loads(tags_json) if tags_json else []
                except:
                    tags = []

                # Get exportable images from image_review_manager
                primary_image_url = ''
                exportable_result = self.image_manager.get_exportable_images(item['review_id'])

                if exportable_result['success']:
                    # Use primary image
                    primary_image_url = exportable_result['primary_image']['url']
                else:
                    # Fallback to source_data if image review not available
                    if item.get('source_data_json'):
                        try:
                            source_data = json.loads(item['source_data_json'])
                            images = source_data.get('images', [])
                            primary_image_url = images[0] if images else ''
                        except:
                            pass

                row = {
                    '상품명': title,
                    '판매가': price,
                    '할인가': price,  # No discount by default
                    '상품설명': description,
                    '태그': ', '.join(tags),
                    '배송정보': '오늘출발 (로켓배송)',
                    '반품정책': '7일 이내 무료 반품',
                    '대표이미지': primary_image_url
                }

                writer.writerow(row)

            csv_data = output.getvalue()

            # Log export
            export_id = self._log_export(
                channel='coupang',
                review_ids=review_ids,
                export_format='csv',
                row_count=len(items),
                file_size=len(csv_data.encode('utf-8')),
                exported_by=exported_by
            )

            return {
                "success": True,
                "export_id": export_id,
                "csv_data": csv_data,
                "row_count": len(items),
                "file_size": len(csv_data.encode('utf-8'))
            }

        except Exception as e:
            logger.error(f"Coupang CSV export failed: {e}")
            return {"success": False, "error": str(e)}

    def _get_items_by_ids(self, review_ids: List[str]) -> List[Dict[str, Any]]:
        """review_id로 항목 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                placeholders = ', '.join('?' * len(review_ids))
                cursor.execute(f'''
                    SELECT * FROM approval_queue
                    WHERE review_id IN ({placeholders})
                ''', review_ids)

                items = [dict(row) for row in cursor.fetchall()]
                return items

        except Exception as e:
            logger.error(f"Failed to get items by IDs: {e}")
            return []

    def _log_export(
        self,
        channel: str,
        review_ids: List[str],
        export_format: str,
        row_count: int,
        file_size: int,
        exported_by: str
    ) -> str:
        """export_log 테이블에 기록"""
        try:
            export_id = f"export-{uuid.uuid4().hex[:12]}"

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO export_log (
                        export_id, channel, review_ids, export_format,
                        export_status, row_count, file_size,
                        exported_by, exported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    export_id,
                    channel,
                    json.dumps(review_ids, ensure_ascii=False),
                    export_format,
                    'completed',
                    row_count,
                    file_size,
                    exported_by,
                    datetime.now().isoformat()
                ))

                conn.commit()

            logger.info(f"Export logged: {export_id} ({channel}, {row_count} items)")
            return export_id

        except Exception as e:
            logger.error(f"Failed to log export: {e}")
            return f"export-{uuid.uuid4().hex[:8]}"

    def get_export_history(
        self,
        channel: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Export 이력 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if channel:
                    cursor.execute('''
                        SELECT * FROM export_log
                        WHERE channel = ?
                        ORDER BY exported_at DESC
                        LIMIT ?
                    ''', (channel, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM export_log
                        ORDER BY exported_at DESC
                        LIMIT ?
                    ''', (limit,))

                items = [dict(row) for row in cursor.fetchall()]

                # Parse review_ids JSON
                for item in items:
                    if item.get('review_ids'):
                        try:
                            item['review_ids_parsed'] = json.loads(item['review_ids'])
                        except:
                            item['review_ids_parsed'] = []

                return items

        except Exception as e:
            logger.error(f"Failed to get export history: {e}")
            return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    service = ExportService()

    # Test: Get exportable items
    exportable = service.get_exportable_items(limit=5)
    print(f"\n✅ Exportable items: {len(exportable)}")

    if exportable:
        review_ids = [item['review_id'] for item in exportable[:2]]

        # Test: Export to Naver
        naver_result = service.export_to_naver_csv(review_ids, exported_by="test")
        if naver_result['success']:
            print(f"\n📄 Naver CSV export: {naver_result['row_count']} rows, {naver_result['file_size']} bytes")
            print(f"   Export ID: {naver_result['export_id']}")
            print(f"   CSV Preview:\n{naver_result['csv_data'][:200]}...")

        # Test: Export to Coupang
        coupang_result = service.export_to_coupang_csv(review_ids, exported_by="test")
        if coupang_result['success']:
            print(f"\n📄 Coupang CSV export: {coupang_result['row_count']} rows, {coupang_result['file_size']} bytes")
            print(f"   Export ID: {coupang_result['export_id']}")
            print(f"   CSV Preview:\n{coupang_result['csv_data'][:200]}...")

        # Test: Get export history
        history = service.get_export_history(limit=5)
        print(f"\n📜 Export history: {len(history)} records")
        for record in history:
            print(f"   {record['export_id']}: {record['channel']} - {record['row_count']} rows ({record['export_status']})")
