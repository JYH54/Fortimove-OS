"""
Project Sentinel — 메인 실행 엔트리포인트

실행 모드:
  python main.py              → 1회 실행 (크롤링 → 분석 → Slack 발송)
  python main.py --schedule   → 매일 09:00 자동 실행
  python main.py --test       → 테스트 (크롤링만, Slack 미발송)
"""

import argparse
import json
import logging
import time
from datetime import datetime

from config import SCHEDULE_TIME
from crawlers import run_all_crawlers
from db import get_unsent_items, save_item
from intelligence import batch_analyze
from slack_notifier import send_daily_briefing, send_item

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sentinel")


def run_once(send_slack: bool = True) -> dict:
    """1회 실행: 크롤링 → 분석 → 저장 → Slack 발송"""
    logger.info("=" * 60)
    logger.info("🛰️  Project Sentinel 실행 시작")
    logger.info("=" * 60)

    # Step 1: 크롤링
    logger.info("\n📡 Step 1: 크롤링 중...")
    raw_items = run_all_crawlers()
    logger.info(f"   수집된 아이템: {len(raw_items)}개")

    # Step 2: 중복 제거 및 저장
    logger.info("\n🔄 Step 2: 중복 제거 및 저장...")
    new_count = 0
    for item in raw_items:
        if save_item(item):
            new_count += 1
    logger.info(f"   신규 아이템: {new_count}개 (중복 제거: {len(raw_items) - new_count}개)")

    if new_count == 0:
        logger.info("   신규 아이템 없음 — 분석 스킵")
        return {"crawled": len(raw_items), "new": 0, "analyzed": 0, "sent": 0}

    # Step 3: LLM 분석
    logger.info("\n🧠 Step 3: 인텔리전스 분석 중...")
    unsent = get_unsent_items(limit=30)
    analyzed = batch_analyze(unsent)
    # 분석 결과 업데이트
    for item in analyzed:
        save_item(item)  # 이미 존재하면 스킵되므로 DB 직접 업데이트 필요
        _update_analysis(item)
    logger.info(f"   분석 완료: {len(analyzed)}개")

    # Step 4: Slack 발송
    sent_count = 0
    if send_slack:
        logger.info("\n📢 Step 4: Slack 알림 발송...")
        # 먼저 일일 브리핑
        send_daily_briefing(analyzed)

        # 개별 아이템 발송 (적합도 15% 이상만, 카테고리별 최대 5개)
        cat_count = {}
        for item in analyzed:
            eligibility = item.get("eligibility_match", 0)
            if eligibility < 0.15:
                continue  # 적합도 미달 → 발송 차단

            cat = item.get("category", "funding")
            cat_count[cat] = cat_count.get(cat, 0) + 1
            if cat_count[cat] > 5:
                continue  # 카테고리당 최대 5개

            if send_item(item):
                sent_count += 1
        logger.info(f"   Slack 발송: {sent_count}건")
    else:
        logger.info("\n⏸️  Step 4: Slack 발송 스킵 (테스트 모드)")

    result = {
        "crawled": len(raw_items),
        "new": new_count,
        "analyzed": len(analyzed),
        "sent": sent_count,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"\n✅ 실행 완료: {json.dumps(result, ensure_ascii=False)}")
    return result


def _update_analysis(item: dict):
    """분석 결과를 DB에 업데이트"""
    import sqlite3
    from config import DB_PATH

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE intel_items
            SET summary=?, eligibility_match=?, amount=?, urgency=?,
                action_suggestion=?, updated_at=?
            WHERE item_id=?
        """, (
            item.get("summary", ""),
            item.get("eligibility_match", 0),
            item.get("amount", ""),
            item.get("urgency", "medium"),
            item.get("action_suggestion", ""),
            datetime.now().isoformat(),
            item["item_id"],
        ))


def run_scheduler():
    """매일 지정 시간에 자동 실행"""
    logger.info(f"📅 스케줄 모드: 매일 {SCHEDULE_TIME}에 실행")

    while True:
        now = datetime.now()
        target = now.replace(
            hour=int(SCHEDULE_TIME.split(":")[0]),
            minute=int(SCHEDULE_TIME.split(":")[1]),
            second=0, microsecond=0
        )

        if now >= target:
            target = target.replace(day=target.day + 1)

        wait_seconds = (target - now).total_seconds()
        logger.info(f"   다음 실행: {target.isoformat()} ({wait_seconds/3600:.1f}시간 후)")
        time.sleep(wait_seconds)

        try:
            run_once(send_slack=True)
        except Exception as e:
            logger.error(f"실행 실패: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project Sentinel")
    parser.add_argument("--schedule", action="store_true", help="매일 자동 실행")
    parser.add_argument("--test", action="store_true", help="테스트 (Slack 미발송)")
    args = parser.parse_args()

    if args.schedule:
        run_scheduler()
    else:
        run_once(send_slack=not args.test)
