"""
Daily Scout → PM Agent 자동 브릿지

Daily Scout가 발견한 상품을 자동으로 PM Agent 워크플로우에 투입.
API 호출 대신 직접 Python 함수 호출 (같은 머신).

실행: python3 daily_scout_bridge.py [--once | --continuous]
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Any

import psycopg2

from auto_scoring_trigger import AutoScoringTrigger

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("scout_bridge")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "fortimove_images"),
    "user": os.getenv("DB_USER", "fortimove"),
    "password": os.getenv("DB_PASSWORD", "fortimove123"),
}

BATCH_SIZE = int(os.getenv("BRIDGE_BATCH_SIZE", "10"))
POLL_INTERVAL = int(os.getenv("BRIDGE_POLL_INTERVAL", "300"))  # 5분


def fetch_pending(limit: int = BATCH_SIZE) -> List[Dict[str, Any]]:
    """Daily Scout DB에서 pending 상품 조회"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, date, region, source, product_name, brand, price,
                   category, trend_score, korea_demand, risk_status,
                   description, url, created_at
            FROM wellness_products
            WHERE workflow_status = 'pending'
            ORDER BY trend_score DESC, created_at DESC
            LIMIT %s
        """, (limit,))

        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def update_status(product_id: int, status: str, error: str = None):
    """workflow_status 업데이트"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE wellness_products
            SET workflow_status = %s, workflow_updated_at = %s
            WHERE id = %s
        """, (status, datetime.now(), product_id))
        conn.commit()
    except Exception as e:
        logger.error(f"상태 업데이트 실패 [{product_id}]: {e}")
        conn.rollback()
    finally:
        conn.close()


def _parse_price(price_str) -> float:
    if not price_str:
        return 0
    try:
        import re
        nums = re.findall(r"[\d.]+", str(price_str))
        return float(nums[0]) if nums else 0
    except (ValueError, IndexError):
        return 0


def process_product(product: Dict, trigger: AutoScoringTrigger) -> Dict:
    """단일 상품 처리: Auto-Scoring → Approval Queue → (95점+ 리디자인)"""
    pid = product["id"]
    name = product.get("product_name", "Unknown")

    logger.info(f"[#{pid}] 처리 시작: {name[:40]}")
    update_status(pid, "processing")

    try:
        product_data = {
            "product_name": name,
            "region": product.get("region", ""),
            "url": product.get("url", ""),
            "price": _parse_price(product.get("price")),
            "trend_score": product.get("trend_score", 0),
            "category": product.get("category", "general"),
            "source_price_cny": _parse_price(product.get("price")),
            "weight_kg": 0.5,
            "margin_rate": 0.35,
            "risk_flags": [],
            "policy_risks": [],
            "certification_required": False,
            "options": [],
            "images": [],
            "description": product.get("description", ""),
            "brand": product.get("brand", ""),
        }

        result = trigger.process_new_product(
            product_id=str(pid),
            product_data=product_data,
            source_type="wellness_products",
        )

        if result.get("error"):
            update_status(pid, "failed")
            logger.warning(f"[#{pid}] 실패: {result['error']}")
        else:
            update_status(pid, "completed")
            logger.info(
                f"[#{pid}] 완료: score={result.get('score', 0)}, "
                f"decision={result.get('decision', '')}, "
                f"redesign={result.get('redesign_triggered', False)}"
            )

        return result

    except Exception as e:
        update_status(pid, "failed")
        logger.error(f"[#{pid}] 처리 오류: {e}")
        return {"error": str(e)}


def run_once():
    """1회 배치 실행"""
    logger.info("=" * 60)
    logger.info("🔗 Daily Scout → PM Agent 브릿지 실행")
    logger.info("=" * 60)

    products = fetch_pending()
    logger.info(f"대기 상품: {len(products)}개")

    if not products:
        logger.info("처리할 상품 없음")
        return

    trigger = AutoScoringTrigger()
    results = {"total": len(products), "success": 0, "failed": 0}

    for product in products:
        result = process_product(product, trigger)
        if result.get("error"):
            results["failed"] += 1
        else:
            results["success"] += 1

    logger.info(f"✅ 완료: {results}")


def run_continuous():
    """연속 실행 (매 5분)"""
    logger.info(f"🔄 연속 모드: {POLL_INTERVAL}초 간격")
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"배치 실패: {e}")
        logger.info(f"⏰ 다음 실행까지 {POLL_INTERVAL}초 대기...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--continuous", action="store_true")
    args = parser.parse_args()

    if args.continuous:
        run_continuous()
    else:
        run_once()
