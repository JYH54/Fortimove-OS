"""
COO API — COO 브리핑 및 경영 인텔리전스 엔드포인트
"""

import logging
from fastapi import APIRouter, BackgroundTasks
from coo_agent import COOAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coo", tags=["coo"])


def _get_coo() -> COOAgent:
    return COOAgent()


@router.get("/snapshot")
async def system_snapshot():
    """시스템 전체 현황 스냅샷"""
    return _get_coo().get_system_snapshot()


@router.get("/briefing")
async def daily_briefing(period: str = "daily"):
    """COO 브리핑 생성 (daily/weekly)"""
    return _get_coo().generate_briefing(period)


@router.get("/winners")
async def winning_products():
    """위닝 상품 후보"""
    return _get_coo().identify_winning_products()


@router.get("/margin-alerts")
async def margin_alerts():
    """마진 경고"""
    alerts = _get_coo().margin_alerts()
    return {"count": len(alerts), "alerts": alerts}


@router.get("/pb-candidates")
async def pb_candidates():
    """PB 전환 후보"""
    candidates = _get_coo().pb_candidates()
    return {"count": len(candidates), "candidates": candidates}


@router.get("/bottlenecks")
async def bottlenecks():
    """운영 병목 분석"""
    return _get_coo().bottleneck_analysis()


@router.get("/sales")
async def sales_summary(days: int = 30):
    """매출 트래킹 요약"""
    return _get_coo().get_sales_summary(days)


@router.get("/competitors")
async def competitor_intel(send_slack: bool = False):
    """경쟁사 모니터링 (send_slack=true → Slack 발송)"""
    report = _get_coo().get_competitor_intel()

    if send_slack and report.get("all_items"):
        try:
            import requests as req
            from config import SLACK_BOT_TOKEN, SLACK_CHANNELS
        except ImportError:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sentinel'))
            SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "xoxb-REDACTED")
            SLACK_CHANNELS = {"urgent": "C0ARMGT1SKA"}
            import requests as req

        type_icons = {"industry": "📊", "pricing": "💰", "trademark": "🏷️"}
        blocks = [{"type": "header", "text": {"type": "plain_text", "text": "⚔️ 경쟁 동향 리포트"}}]
        for item in report.get("all_items", [])[:8]:
            icon = type_icons.get(item.get("type", ""), "📋")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{icon} *{item.get('title', '')[:50]}*\n{item.get('media', '')}"},
                "accessory": {"type": "button", "text": {"type": "plain_text", "text": "원문 →"}, "url": item.get("url", "#")} if item.get("url") else None,
            })
            # accessory가 None이면 제거
            if blocks[-1]["accessory"] is None:
                del blocks[-1]["accessory"]

        blocks.append({"type": "divider"})

        COMPETITOR_CHANNEL = "C0AR76S7481"  # #05-경쟁동향-이슈
        req.post("https://slack.com/api/chat.postMessage", headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json",
        }, json={"channel": COMPETITOR_CHANNEL, "blocks": blocks, "text": "경쟁 동향 리포트"}, timeout=10)

    return report


@router.get("/weekly-report")
async def weekly_report():
    """주간 종합 경영 리포트"""
    return _get_coo().generate_weekly_report()


@router.get("/reorder-alerts")
async def reorder_alerts():
    """위닝 상품 재주문 알림 (판매 속도 기반)"""
    try:
        from sales_tracker import SalesTracker
        tracker = SalesTracker()
        stats = tracker.get_dashboard_stats(days=14)
        top = stats.get("top_products", [])

        alerts = []
        for product in top:
            qty = product.get("total_qty", 0)
            if qty >= 5:  # 2주간 5개 이상 판매 → 재주문 검토
                daily_rate = qty / 14
                est_days_left = 30  # 재고 추정 (초기에는 고정값)
                alerts.append({
                    "product": product.get("product_name", ""),
                    "sold_14d": qty,
                    "daily_rate": round(daily_rate, 1),
                    "revenue_14d": product.get("total_revenue", 0),
                    "action": "재주문 검토" if qty >= 10 else "모니터링",
                    "message": f"2주간 {qty}개 판매 (일평균 {daily_rate:.1f}개) — {'즉시 재발주 권장' if qty >= 10 else '판매 추이 관찰'}",
                })

        return {"count": len(alerts), "alerts": alerts}
    except Exception as e:
        return {"count": 0, "alerts": [], "error": str(e)}
