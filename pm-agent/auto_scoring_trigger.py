"""
Auto-Scoring Trigger - Daily Scout 크롤링 후 자동 채점
Phase 3 Core Module
"""

import logging
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from scoring_engine import ScoringEngine
from approval_queue import ApprovalQueueManager
from content_agent import ContentAgent
from channel_upload_manager import ChannelUploadManager

logger = logging.getLogger(__name__)


class AutoScoringTrigger:
    """Daily Scout 크롤링 결과를 자동으로 채점하고 처리"""

    def __init__(self):
        self.scoring_engine = ScoringEngine()
        self.approval_queue = ApprovalQueueManager()
        self.content_agent = ContentAgent()
        self.upload_manager = ChannelUploadManager()

    def process_new_product(
        self,
        product_id: str,
        product_data: Dict[str, Any],
        source_type: str = "wellness_products"
    ) -> Dict[str, Any]:
        """
        신규 상품 처리 파이프라인

        Args:
            product_id: wellness_products.id
            product_data: 상품 데이터 (wellness_products row)
            source_type: 소스 타입 (기본: wellness_products)

        Returns:
            {
                "review_id": str,
                "score": int,
                "decision": str,
                "content_generated": bool,
                "upload_items_created": int,
                "error": str | None
            }
        """
        try:
            logger.info(f"[AutoScoring] Processing product {product_id}")

            # Step 1: Transform to review format
            review_data = self._transform_to_review_format(product_id, product_data)

            # Step 2: Score product
            scoring_result = self.scoring_engine.score_product(review_data)

            logger.info(f"[AutoScoring] Score: {scoring_result['score']}, "
                       f"Decision: {scoring_result['decision']}")

            # Step 3: Save to approval_queue
            review_id = self._save_to_approval_queue(
                product_id=product_id,
                source_type=source_type,
                review_data=review_data,
                scoring_result=scoring_result
            )

            # Step 4: Log audit
            self._log_audit(
                entity_type="approval",
                entity_id=review_id,
                action="auto_scored",
                actor="system",
                metadata={
                    "product_id": product_id,
                    "score": scoring_result['score'],
                    "decision": scoring_result['decision']
                }
            )

            # Step 5: Generate content if decision allows
            content_generated = False
            upload_items_created = 0

            if scoring_result['decision'] in ['review', 'auto_approve']:
                try:
                    content_generated, upload_items_created = self._generate_content(
                        review_id=review_id,
                        product_data=product_data
                    )
                except Exception as e:
                    logger.error(f"[AutoScoring] Content generation failed: {e}")
                    # Update approval_queue with error
                    self.approval_queue.update_item(review_id, {
                        "content_status": "failed",
                        "last_error": str(e),
                        "retry_count": 1
                    })

            # Step 6: 95점 이상 → 상세페이지 리디자인 자동 트리거
            redesign_triggered = False
            if scoring_result['score'] >= 95:
                try:
                    redesign_triggered = self._trigger_auto_redesign(
                        review_id=review_id,
                        product_data=product_data,
                        score=scoring_result['score']
                    )
                except Exception as e:
                    logger.warning(f"[AutoScoring] 리디자인 자동 트리거 실패 (비치명적): {e}")

            return {
                "review_id": review_id,
                "score": scoring_result['score'],
                "decision": scoring_result['decision'],
                "content_generated": content_generated,
                "upload_items_created": upload_items_created,
                "redesign_triggered": redesign_triggered,
                "error": None
            }

        except Exception as e:
            logger.error(f"[AutoScoring] Failed to process {product_id}: {e}")
            return {
                "review_id": None,
                "score": 0,
                "decision": "error",
                "content_generated": False,
                "upload_items_created": 0,
                "error": str(e)
            }

    def _transform_to_review_format(
        self,
        product_id: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        wellness_products 데이터를 approval_queue 형식으로 변환
        """
        # Extract relevant fields
        return {
            "review_id": f"review-{uuid.uuid4().hex[:12]}",
            "source_id": product_id,
            "source_type": "wellness_products",
            "source_title": product_data.get('product_name', 'Unknown Product'),
            "source_url": product_data.get('url', ''),
            "source_data": {
                "product_name": product_data.get('product_name'),
                "region": product_data.get('region'),
                "price": product_data.get('price'),
                "trend_score": product_data.get('trend_score', 0),
                "category": product_data.get('category', '기타'),
                "source_price_cny": product_data.get('source_price_cny', 0),
                "weight_kg": product_data.get('weight_kg', 0.5),
                "target_margin_rate": product_data.get('target_margin_rate', 0.4)
            },
            "agent_output": {
                "sourcing": {
                    "sourcing_decision": "통과",
                    "risk_flags": product_data.get('risk_flags', []),
                    "product_classification": product_data.get('category', '테스트')
                },
                "margin": {
                    "margin_analysis": {
                        "net_margin_rate": product_data.get('margin_rate', 0),
                        "net_profit": product_data.get('profit', 0)
                    }
                },
                "registration": {
                    "policy_risks": product_data.get('policy_risks', []),
                    "certification_required": product_data.get('certification_required', False),
                    "category": product_data.get('category', '기타'),
                    "options": product_data.get('options', [])
                }
            },
            "created_at": datetime.now().isoformat()
        }

    def _save_to_approval_queue(
        self,
        product_id: str,
        source_type: str,
        review_data: Dict[str, Any],
        scoring_result: Dict[str, Any]
    ) -> str:
        """approval_queue에 저장"""

        item_data = {
            "source_id": product_id,
            "source_type": source_type,
            "source_title": review_data.get('source_title'),
            "source_url": review_data.get('source_url'),
            "source_data": json.dumps(review_data.get('source_data', {}), ensure_ascii=False),
            "agent_output": json.dumps(review_data.get('agent_output', {}), ensure_ascii=False),
            "reviewer_status": "pending",
            "score": scoring_result['score'],
            "decision": scoring_result['decision'],
            "priority": 50,  # Will be updated by approval_ranker
            "reasons_json": json.dumps(scoring_result['reasons'], ensure_ascii=False),
            "scoring_updated_at": datetime.now().isoformat(),
            "content_status": "pending",
            "audit_trail": json.dumps([{
                "action": "auto_scored",
                "actor": "system",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "score": scoring_result['score'],
                    "decision": scoring_result['decision']
                }
            }], ensure_ascii=False)
        }

        review_id = self.approval_queue.create_item(source_type=source_type, source_title=review_data.get("source_title"), agent_output=item_data, source_data=review_data.get("source_data"))
        logger.info(f"[AutoScoring] Saved to approval_queue: {review_id}")

        return review_id

    def _generate_content(
        self,
        review_id: str,
        product_data: Dict[str, Any]
    ) -> tuple[bool, int]:
        """
        콘텐츠 생성 및 upload queue 추가

        Returns:
            (content_generated: bool, upload_items_created: int)
        """
        logger.info(f"[AutoScoring] Generating content for {review_id}")

        # Prepare content input
        content_input = {
            "product_name": product_data.get('product_name', 'Product'),
            "product_category": product_data.get('category', '기타'),
            "key_features": self._extract_features(product_data),
            "price": product_data.get('price', 10000),
            "channels": ["naver", "coupang"],
            "options": product_data.get('options', []),
            "generate_usp": True,
            "generate_options": True,
            "compliance_mode": True
        }

        # Generate content
        content_result = self.content_agent.execute_multichannel(content_input)

        # Create upload queue items for each channel
        upload_items_created = 0

        for channel in ["naver", "coupang"]:
            upload_id = self.upload_manager.add_upload_item(
                review_id=review_id,
                channel=channel,
                content={
                    "title": content_result.get(f"{channel}_title"),
                    "description": content_result.get('detail_description', ''),
                    "usp_points": content_result.get('usp_points', []),
                    "seo_tags": content_result.get('seo_tags', []),
                    "options_korean": content_result.get('options_korean', {}),
                    "images": product_data.get('images', []),
                    "price": product_data.get('price'),
                    "options": product_data.get('options', []),
                    "return_policy": "7일 이내 무료 반품",
                    "compliance_status": content_result.get('compliance_status', 'safe')
                }
            )

            logger.info(f"[AutoScoring] Created upload item: {upload_id} ({channel})")
            upload_items_created += 1

            # Log audit
            self._log_audit(
                entity_type="upload",
                entity_id=upload_id,
                action="created",
                actor="system",
                metadata={"review_id": review_id, "channel": channel}
            )

        # Update approval_queue content_status
        self.approval_queue.update_item(review_id, {
            "content_status": "completed"
        })

        # Add audit trail
        self._append_audit_trail(review_id, {
            "action": "content_generated",
            "actor": "system",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"channels": ["naver", "coupang"], "items_created": upload_items_created}
        })

        return True, upload_items_created

    def _extract_features(self, product_data: Dict[str, Any]) -> list[str]:
        """상품 데이터에서 주요 특징 추출"""
        features = []

        # Category-based features
        category = product_data.get('category', '')
        if '주방' in category:
            features.extend(['고품질 소재', '실용적인 디자인'])
        elif '뷰티' in category or '건강' in category:
            features.extend(['피부 친화적', '안전한 성분'])
        elif '패션' in category:
            features.extend(['트렌디한 스타일', '활용도 높음'])
        else:
            features.extend(['합리적인 가격', '빠른 배송'])

        # Add generic feature
        if product_data.get('price', 0) < 20000:
            features.append('가성비 우수')
        else:
            features.append('프리미엄 품질')

        return features[:3]  # Limit to 3 features

    def _log_audit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """audit_log 테이블에 기록"""
        try:
            import sqlite3
            db_path = Path(__file__).parent / "data" / "approval_queue.db"

            with sqlite3.connect(db_path) as conn:
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

        except Exception as e:
            logger.error(f"[AutoScoring] Failed to log audit: {e}")

    def _append_audit_trail(self, review_id: str, trail_entry: Dict):
        """approval_queue의 audit_trail에 추가"""
        try:
            item = self.approval_queue.get_item(review_id)
            current_trail = json.loads(item.get('audit_trail', '[]'))
            current_trail.append(trail_entry)

            self.approval_queue.update_item(review_id, {
                "audit_trail": json.dumps(current_trail, ensure_ascii=False)
            })

        except Exception as e:
            logger.error(f"[AutoScoring] Failed to append audit trail: {e}")


    def _trigger_auto_redesign(
        self,
        review_id: str,
        product_data: Dict[str, Any],
        score: int
    ) -> bool:
        """95점 이상 상품 → 상세페이지 리디자인 자동 트리거"""
        from redesign_queue_manager import RedesignQueueManager

        images = product_data.get("images", [])
        if not images:
            logger.info(f"[AutoScoring] 리디자인 스킵: 이미지 없음 (review_id={review_id})")
            return False

        manager = RedesignQueueManager()
        redesign_id = manager.add_to_queue(
            source_title=product_data.get("product_name", "자동 트리거 상품"),
            source_images=images,
            source_type="sourcing_agent",
            moodtone="premium",
            category=product_data.get("category", "general"),
            review_id=review_id,
            trigger_type="auto_score",
            trigger_score=score,
        )

        logger.info(
            f"[AutoScoring] 리디자인 자동 트리거: "
            f"score={score}, review_id={review_id}, redesign_id={redesign_id}"
        )
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with sample product data
    trigger = AutoScoringTrigger()

    sample_product = {
        "product_name": "프리미엄 스테인리스 텀블러 500ml",
        "region": "Korea",
        "url": "https://item.taobao.com/item.htm?id=987654321",
        "price": 15900,
        "trend_score": 85,
        "category": "주방용품",
        "source_price_cny": 30.0,
        "weight_kg": 0.5,
        "margin_rate": 0.45,
        "profit": 7000,
        "risk_flags": [],
        "policy_risks": [],
        "certification_required": False,
        "options": ["300ml", "500ml", "700ml"],
        "images": ["https://example.com/image1.jpg"]
    }

    result = trigger.process_new_product(
        product_id="test-product-001",
        product_data=sample_product
    )

    print(f"\n✅ Auto-Scoring Result:")
    print(f"   Review ID: {result['review_id']}")
    print(f"   Score: {result['score']}")
    print(f"   Decision: {result['decision']}")
    print(f"   Content Generated: {result['content_generated']}")
    print(f"   Upload Items: {result['upload_items_created']}")
    if result['error']:
        print(f"   Error: {result['error']}")
