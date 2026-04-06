"""
Image Review Manager - Phase 4
이미지 검수 계층: 대표 이미지, 순서, 제외, 경고 관리
"""

import logging
import json
import sqlite3
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# DB path
DB_PATH = Path(__file__).parent / "data" / "approval_queue.db"


class ImageReviewManager:
    """
    Image Review Manager

    핵심 규칙:
    1. 한 review_id당 is_primary=true 이미지는 최대 1개만 허용
    2. is_excluded=true 인 이미지는 is_primary=true 불가
    3. 기존 대표 이미지 변경 시 이전 대표 자동 해제
    4. 대표 이미지 제외 처리 시 대표 상태 자동 해제
    5. Export는 is_excluded=false 인 이미지만 사용
    6. 대표 이미지 없으면 display_order ASC 첫 번째 사용
    7. 사용 가능 이미지 0개면 export 금지
    """

    def __init__(self):
        self.db_path = DB_PATH

    def get_images(self, review_id: str) -> Optional[Dict[str, Any]]:
        """
        Review의 이미지 정보 조회

        Returns:
            {
                "image_review_id": str,
                "review_id": str,
                "original_images": [...],
                "reviewed_images": [
                    {
                        "image_id": str,
                        "url": str,
                        "display_order": int,
                        "is_primary": bool,
                        "is_excluded": bool,
                        "warnings": [],
                        "notes": str
                    }
                ],
                "primary_image_index": int,
                "updated_at": str,
                "updated_by": str
            }
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM image_review
                    WHERE review_id = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                ''', (review_id,))

                row = cursor.fetchone()

                if not row:
                    # No image review yet, try to initialize from source_data
                    return self._initialize_from_source_data(review_id)

                result = dict(row)

                # Parse JSON fields
                if result.get('original_images_json'):
                    try:
                        result['original_images'] = json.loads(result['original_images_json'])
                    except:
                        result['original_images'] = []

                if result.get('reviewed_images_json'):
                    try:
                        result['reviewed_images'] = json.loads(result['reviewed_images_json'])
                    except:
                        result['reviewed_images'] = []

                return result

        except Exception as e:
            logger.error(f"Failed to get images for {review_id}: {e}")
            return None

    def _initialize_from_source_data(self, review_id: str) -> Optional[Dict[str, Any]]:
        """
        source_data에서 이미지 목록을 추출하여 초기화

        Returns:
            Initialized image review data or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT source_data_json FROM approval_queue
                    WHERE review_id = ?
                ''', (review_id,))

                row = cursor.fetchone()

                if not row or not row['source_data_json']:
                    logger.warning(f"No source_data found for {review_id}")
                    return None

                source_data = json.loads(row['source_data_json'])
                image_urls = source_data.get('images', [])

                if not image_urls:
                    logger.warning(f"No images in source_data for {review_id}")
                    return None

                # 상품 이미지 필터링 (브랜드 로고·배너·UI 요소 제외)
                EXCLUDE_PATTERNS = [
                    '/brand/logo/', '/cms/banners/', '/cms/my-account/',
                    '/cms/logos/', '/icon/', '/badge/', '/flag/', '/ui/',
                    'sprite', 'placeholder', 'loading', 'rewards',
                    'logo', 'social-', 'footer', 'header',
                ]
                product_urls = []
                excluded_urls = []
                for url in image_urls:
                    u = url.lower() if isinstance(url, str) else ''
                    if any(pat in u for pat in EXCLUDE_PATTERNS):
                        excluded_urls.append(url)
                    else:
                        product_urls.append(url)

                # 상품 이미지가 없으면 빈 결과 (로고·배너만 있으면 안 씀)
                if not product_urls:
                    logger.warning(f"No product images after filtering for {review_id} (all {len(image_urls)} were logos/banners)")
                    return None

                if excluded_urls:
                    logger.info(f"Filtered {len(excluded_urls)} non-product images for {review_id}")

                # Initialize reviewed_images from filtered product images
                reviewed_images = []
                for idx, url in enumerate(product_urls):
                    reviewed_images.append({
                        'image_id': f"img-{uuid.uuid4().hex[:8]}",
                        'url': url,
                        'display_order': idx,
                        'is_primary': (idx == 0),
                        'is_excluded': False,
                        'warnings': [],
                        'notes': ''
                    })

                return {
                    'image_review_id': None,  # Not saved yet
                    'review_id': review_id,
                    'original_images': product_urls,
                    'reviewed_images': reviewed_images,
                    'primary_image_index': 0,
                    'updated_at': None,
                    'updated_by': None
                }

        except Exception as e:
            logger.error(f"Failed to initialize images from source_data for {review_id}: {e}")
            return None

    def save_images(
        self,
        review_id: str,
        reviewed_images: List[Dict[str, Any]],
        operator: str = "system"
    ) -> Dict[str, Any]:
        """
        이미지 검수 정보 저장 (Bulk Save)

        Args:
            review_id: Review ID
            reviewed_images: List of image objects with display_order, is_primary, is_excluded, etc.
            operator: Operator name

        Returns:
            {
                "success": bool,
                "image_review_id": str,
                "errors": [],
                "warnings": []
            }
        """
        errors = []
        warnings = []

        # Validation 1: Exactly one primary image
        primary_count = sum(1 for img in reviewed_images if img.get('is_primary', False))
        if primary_count == 0:
            errors.append("대표 이미지가 지정되지 않았습니다. 최소 1개의 대표 이미지를 지정하세요.")
        elif primary_count > 1:
            errors.append(f"대표 이미지는 1개만 지정할 수 있습니다. 현재 {primary_count}개 지정됨.")

        # Validation 2: Primary image cannot be excluded
        for img in reviewed_images:
            if img.get('is_primary', False) and img.get('is_excluded', False):
                errors.append(f"제외된 이미지는 대표 이미지로 지정할 수 없습니다. (image_id: {img.get('image_id', 'unknown')})")

        # Validation 3: At least one non-excluded image
        non_excluded_count = sum(1 for img in reviewed_images if not img.get('is_excluded', False))
        if non_excluded_count == 0:
            errors.append("모든 이미지가 제외되었습니다. 최소 1개의 이미지는 사용 가능 상태여야 합니다.")

        # Return errors if validation failed
        if errors:
            return {
                "success": False,
                "errors": errors,
                "warnings": warnings
            }

        # Get original images from source_data
        original_images = self._get_original_images(review_id)

        # Find primary image index
        primary_image_index = 0
        for idx, img in enumerate(reviewed_images):
            if img.get('is_primary', False):
                primary_image_index = idx
                break

        # Save to database
        try:
            image_review_id = self._upsert_image_review(
                review_id=review_id,
                original_images=original_images,
                reviewed_images=reviewed_images,
                primary_image_index=primary_image_index,
                operator=operator
            )

            logger.info(f"✅ Saved images for {review_id}: {len(reviewed_images)} images, primary at index {primary_image_index}")

            return {
                "success": True,
                "image_review_id": image_review_id,
                "errors": [],
                "warnings": warnings
            }

        except Exception as e:
            logger.error(f"Failed to save images for {review_id}: {e}")
            return {
                "success": False,
                "errors": [f"Database error: {str(e)}"],
                "warnings": warnings
            }

    def set_primary_image(
        self,
        review_id: str,
        image_id: str,
        operator: str = "system"
    ) -> Dict[str, Any]:
        """
        대표 이미지 지정 (단일 액션)

        Args:
            review_id: Review ID
            image_id: Image ID to set as primary
            operator: Operator name

        Returns:
            {"success": bool, "errors": []}
        """
        images_data = self.get_images(review_id)

        if not images_data:
            return {"success": False, "errors": ["Image review not found"]}

        reviewed_images = images_data.get('reviewed_images', [])

        # Find target image
        target_img = None
        for img in reviewed_images:
            if img['image_id'] == image_id:
                target_img = img
                break

        if not target_img:
            return {"success": False, "errors": [f"Image {image_id} not found"]}

        # Check if excluded
        if target_img.get('is_excluded', False):
            return {"success": False, "errors": ["제외된 이미지는 대표 이미지로 지정할 수 없습니다."]}

        # Clear all primary flags
        for img in reviewed_images:
            img['is_primary'] = False

        # Set new primary
        target_img['is_primary'] = True

        # Save
        return self.save_images(review_id, reviewed_images, operator)

    def reorder_images(
        self,
        review_id: str,
        ordered_image_ids: List[str],
        operator: str = "system"
    ) -> Dict[str, Any]:
        """
        이미지 순서 변경

        Args:
            review_id: Review ID
            ordered_image_ids: List of image_ids in desired order
            operator: Operator name

        Returns:
            {"success": bool, "errors": []}
        """
        images_data = self.get_images(review_id)

        if not images_data:
            return {"success": False, "errors": ["Image review not found"]}

        reviewed_images = images_data.get('reviewed_images', [])

        # Validate: all image_ids present
        current_ids = {img['image_id'] for img in reviewed_images}
        ordered_ids = set(ordered_image_ids)

        if current_ids != ordered_ids:
            return {"success": False, "errors": ["Image ID mismatch: provided IDs do not match existing images"]}

        # Create mapping
        id_to_img = {img['image_id']: img for img in reviewed_images}

        # Reorder
        reordered = []
        for idx, image_id in enumerate(ordered_image_ids):
            img = id_to_img[image_id]
            img['display_order'] = idx
            reordered.append(img)

        # Save
        return self.save_images(review_id, reordered, operator)

    def exclude_image(
        self,
        review_id: str,
        image_id: str,
        excluded: bool,
        operator: str = "system",
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        이미지 제외/복원 처리

        Args:
            review_id: Review ID
            image_id: Image ID
            excluded: True to exclude, False to restore
            operator: Operator name
            note: Optional note

        Returns:
            {"success": bool, "errors": []}
        """
        images_data = self.get_images(review_id)

        if not images_data:
            return {"success": False, "errors": ["Image review not found"]}

        reviewed_images = images_data.get('reviewed_images', [])

        # Find target image
        target_img = None
        for img in reviewed_images:
            if img['image_id'] == image_id:
                target_img = img
                break

        if not target_img:
            return {"success": False, "errors": [f"Image {image_id} not found"]}

        # If excluding primary image, clear primary status
        if excluded and target_img.get('is_primary', False):
            target_img['is_primary'] = False

            # Set next available image as primary
            for img in reviewed_images:
                if img['image_id'] != image_id and not img.get('is_excluded', False):
                    img['is_primary'] = True
                    break

        # Set excluded status
        target_img['is_excluded'] = excluded

        # Add note if provided
        if note:
            target_img['notes'] = note

        # Save
        return self.save_images(review_id, reviewed_images, operator)

    def save_image_warning(
        self,
        review_id: str,
        image_id: str,
        warning_type: str,
        note: str,
        operator: str = "system"
    ) -> Dict[str, Any]:
        """
        이미지 경고 저장

        Args:
            review_id: Review ID
            image_id: Image ID
            warning_type: Warning type (e.g., 'low_quality', 'wrong_aspect', 'text_overlay')
            note: Warning description
            operator: Operator name

        Returns:
            {"success": bool, "errors": []}
        """
        images_data = self.get_images(review_id)

        if not images_data:
            return {"success": False, "errors": ["Image review not found"]}

        reviewed_images = images_data.get('reviewed_images', [])

        # Find target image
        target_img = None
        for img in reviewed_images:
            if img['image_id'] == image_id:
                target_img = img
                break

        if not target_img:
            return {"success": False, "errors": [f"Image {image_id} not found"]}

        # Add warning
        if 'warnings' not in target_img:
            target_img['warnings'] = []

        target_img['warnings'].append({
            'type': warning_type,
            'note': note,
            'created_at': datetime.now().isoformat(),
            'created_by': operator
        })

        # Save
        return self.save_images(review_id, reviewed_images, operator)

    def get_exportable_images(self, review_id: str) -> Dict[str, Any]:
        """
        Export 가능한 이미지 목록 조회

        Rules:
        1. is_excluded=false AND is_primary=true 우선
        2. 없으면 is_excluded=false 인 이미지 중 display_order ASC 첫 번째
        3. 그래도 없으면 error

        Returns:
            {
                "success": bool,
                "primary_image": {...},
                "all_images": [...],
                "exportable_count": int,
                "errors": []
            }
        """
        images_data = self.get_images(review_id)

        if not images_data:
            return {
                "success": False,
                "errors": ["No image review found for this review"]
            }

        reviewed_images = images_data.get('reviewed_images', [])

        # Filter non-excluded images
        exportable = [img for img in reviewed_images if not img.get('is_excluded', False)]

        if not exportable:
            return {
                "success": False,
                "errors": ["모든 이미지가 제외되었습니다. Export 불가능."],
                "exportable_count": 0
            }

        # Sort by display_order
        exportable = sorted(exportable, key=lambda x: x.get('display_order', 999))

        # Find primary image
        primary_image = None
        for img in exportable:
            if img.get('is_primary', False):
                primary_image = img
                break

        # Fallback to first image if no primary
        if not primary_image:
            primary_image = exportable[0]

        return {
            "success": True,
            "primary_image": primary_image,
            "all_images": exportable,
            "exportable_count": len(exportable),
            "errors": []
        }

    def _get_original_images(self, review_id: str) -> List[str]:
        """Get original image URLs from source_data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT source_data_json FROM approval_queue
                    WHERE review_id = ?
                ''', (review_id,))

                row = cursor.fetchone()

                if row and row['source_data_json']:
                    source_data = json.loads(row['source_data_json'])
                    return source_data.get('images', [])

                return []

        except Exception as e:
            logger.error(f"Failed to get original images: {e}")
            return []

    def _upsert_image_review(
        self,
        review_id: str,
        original_images: List[str],
        reviewed_images: List[Dict[str, Any]],
        primary_image_index: int,
        operator: str
    ) -> str:
        """Insert or update image_review record"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if exists
                cursor.execute('''
                    SELECT image_review_id FROM image_review
                    WHERE review_id = ?
                ''', (review_id,))

                existing = cursor.fetchone()

                now = datetime.now().isoformat()

                original_images_json = json.dumps(original_images, ensure_ascii=False)
                reviewed_images_json = json.dumps(reviewed_images, ensure_ascii=False)

                if existing:
                    # Update
                    image_review_id = existing[0]

                    cursor.execute('''
                        UPDATE image_review
                        SET original_images_json = ?,
                            reviewed_images_json = ?,
                            primary_image_index = ?,
                            updated_at = ?
                        WHERE image_review_id = ?
                    ''', (
                        original_images_json,
                        reviewed_images_json,
                        primary_image_index,
                        now,
                        image_review_id
                    ))

                else:
                    # Insert
                    image_review_id = f"img-review-{uuid.uuid4().hex[:12]}"

                    cursor.execute('''
                        INSERT INTO image_review (
                            image_review_id, review_id,
                            original_images_json, reviewed_images_json,
                            primary_image_index,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        image_review_id,
                        review_id,
                        original_images_json,
                        reviewed_images_json,
                        primary_image_index,
                        now,
                        now
                    ))

                conn.commit()

                return image_review_id

        except Exception as e:
            logger.error(f"Failed to upsert image_review: {e}")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = ImageReviewManager()

    # Test review_id (from Phase 3/4 test data)
    test_review_id = "review-test-001"

    # Test 1: Get images (should initialize from source_data)
    print("\n" + "=" * 60)
    print("TEST 1: Get Images (Initialize from source_data)")
    print("=" * 60)

    images = manager.get_images(test_review_id)
    if images:
        print(f"✅ Images retrieved: {len(images.get('reviewed_images', []))} images")
        print(f"   Primary image index: {images.get('primary_image_index', -1)}")
        for img in images.get('reviewed_images', []):
            print(f"   - {img['image_id']}: order={img['display_order']}, primary={img['is_primary']}, excluded={img['is_excluded']}")
    else:
        print("❌ Failed to get images")

    # Test 2: Save images with modifications
    print("\n" + "=" * 60)
    print("TEST 2: Save Images with Modifications")
    print("=" * 60)

    if images:
        reviewed_images = images.get('reviewed_images', [])

        # Modify: exclude first image, set second as primary
        if len(reviewed_images) >= 2:
            reviewed_images[0]['is_excluded'] = True
            reviewed_images[0]['is_primary'] = False
            reviewed_images[1]['is_primary'] = True

        result = manager.save_images(test_review_id, reviewed_images, operator="test_operator")
        print(f"Save result: {result['success']}")
        if result['success']:
            print(f"✅ Image review saved: {result['image_review_id']}")
        else:
            print(f"❌ Errors: {result['errors']}")

    # Test 3: Get exportable images
    print("\n" + "=" * 60)
    print("TEST 3: Get Exportable Images")
    print("=" * 60)

    exportable = manager.get_exportable_images(test_review_id)
    print(f"Exportable success: {exportable['success']}")
    if exportable['success']:
        print(f"✅ Exportable count: {exportable['exportable_count']}")
        print(f"   Primary image: {exportable['primary_image']['url'][:50]}...")
    else:
        print(f"❌ Errors: {exportable['errors']}")
