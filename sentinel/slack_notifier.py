"""
Sentinel Slack Notifier — 채널 ID 기반 발송 (Bot API 우선, Webhook 폴백)
"""

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from config import SLACK_BOT_TOKEN, SLACK_CHANNELS, SLACK_WEBHOOK_DEFAULT
from db import mark_sent

logger = logging.getLogger(__name__)

# 카테고리 → 아이콘
CATEGORY_ICONS = {
    "funding": "💰",
    "regulation": "⚖️",
    "platform": "🚀",
    "trend": "📈",
}

URGENCY_LABELS = {
    "critical": "🔴 긴급",
    "high": "🟡 중요",
    "medium": "🔵 참고",
    "low": "⚪ 아카이브",
}

# 카테고리 → 채널 키
CATEGORY_CHANNEL_MAP = {
    "funding": "funding",
    "regulation": "health",
    "platform": "platform",
}


def _resolve_channel(item: Dict) -> tuple:
    """아이템의 카테고리/긴급도에 따른 채널 ID + 채널명 결정"""
    urgency = item.get("urgency", "medium")
    category = item.get("category", "")

    # 긴급은 무조건 urgent 채널
    if urgency == "critical":
        return SLACK_CHANNELS.get("urgent", ""), "#00-긴급-브리핑"

    # 카테고리별 채널
    channel_key = CATEGORY_CHANNEL_MAP.get(category, "")
    if channel_key:
        channel_names = {
            "funding": "#01-자금-지원금",
            "health": "#02-헬스케어-인텔",
            "platform": "#03-플랫폼-정책",
        }
        return SLACK_CHANNELS.get(channel_key, ""), channel_names.get(channel_key, "#scout")

    # 기본: funding 채널
    return SLACK_CHANNELS.get("funding", ""), "#01-자금-지원금"


def _build_blocks(item: Dict) -> List[Dict]:
    """Executive-grade Slack Block Kit 메시지"""
    icon = CATEGORY_ICONS.get(item.get("category", ""), "📋")
    urgency = URGENCY_LABELS.get(item.get("urgency", "medium"), "🔵 참고")

    deadline = item.get("deadline", "")
    deadline_text = f"📅 마감: {deadline}" if deadline else "📅 마감: 미정"

    # D-day 계산
    if deadline:
        try:
            from datetime import datetime
            dl = datetime.strptime(deadline.replace(".", "-"), "%Y-%m-%d")
            days = (dl - datetime.now()).days
            if days > 0:
                deadline_text += f" (D-{days})"
            elif days == 0:
                deadline_text += " (D-DAY!)"
        except ValueError:
            pass

    summary = item.get("summary", item.get("title", ""))
    action = item.get("action_suggestion", "모니터링 유지")

    eligibility = item.get("eligibility_match", 0)
    if isinstance(eligibility, str):
        try:
            eligibility = float(eligibility)
        except ValueError:
            eligibility = 0
    elig_pct = int(eligibility * 100)
    elig_bar = "🟢" if eligibility >= 0.7 else "🟡" if eligibility >= 0.4 else "⚪"
    elig_label = "직접 해당" if eligibility >= 0.7 else "참고 가치" if eligibility >= 0.4 else "벤치마킹"

    # 자금줄 가능성
    funding = item.get("funding_potential", "NONE")
    funding_icons = {"HIGH": "💰💰💰", "MEDIUM": "💰💰", "LOW": "💰", "REFERENCE": "📚", "NONE": "—"}
    funding_text = funding_icons.get(funding, "—")

    keywords = item.get("keywords", [])
    if isinstance(keywords, str):
        try:
            keywords = json.loads(keywords)
        except (json.JSONDecodeError, TypeError):
            keywords = []

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{icon} [{urgency}] {item.get('title', '')[:70]}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📋 핵심 요약*\n{summary}"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*{deadline_text}*"},
                {"type": "mrkdwn", "text": f"*💵 {item.get('amount', '미상')}*"},
                {"type": "mrkdwn", "text": f"*{elig_bar} 적합도: {elig_pct}% ({elig_label})*"},
                {"type": "mrkdwn", "text": f"*자금 가능성: {funding_text}*"},
            ]
        },
    ]

    # 자금 상세 (있으면)
    funding_detail = item.get("funding_detail", "")
    if funding_detail:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*💼 자금 분석*\n{funding_detail}"}
        })

    # 경영 인사이트 (있으면)
    insight = item.get("executive_insight", "")
    if insight:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*💡 경영 인사이트*\n{insight}"}
        })

    # 액션
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*🎯 액션*: {action}"}
    })

    # 주의사항
    risk = item.get("risk_note", "")
    if risk:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*⚠️ 주의*: {risk}"}
        })

    if item.get("url"):
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📎 원문 보기"},
                    "url": item["url"],
                    "style": "primary"
                },
            ]
        })

    blocks.append({"type": "divider"})
    return blocks


def _send_via_bot(channel_id: str, blocks: List[Dict], fallback_text: str) -> bool:
    """Slack Bot API로 발송"""
    if not SLACK_BOT_TOKEN:
        return False

    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "channel": channel_id,
                "blocks": blocks,
                "text": fallback_text,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            return True
        else:
            logger.warning(f"Bot API 실패: {data.get('error', 'unknown')}")
            return False
    except Exception as e:
        logger.error(f"Bot API 오류: {e}")
        return False


def _send_via_webhook(webhook_url: str, blocks: List[Dict], fallback_text: str) -> bool:
    """Webhook으로 발송 (폴백)"""
    if not webhook_url:
        return False

    try:
        resp = requests.post(
            webhook_url,
            json={"blocks": blocks, "text": fallback_text},
            timeout=10,
        )
        return resp.status_code == 200 and resp.text == "ok"
    except Exception as e:
        logger.error(f"Webhook 오류: {e}")
        return False


def send_item(item: Dict) -> bool:
    """단일 아이템을 적절한 Slack 채널로 발송 + 긴급 시 00채널 중복 발송"""
    channel_id, channel_name = _resolve_channel(item)
    blocks = _build_blocks(item)
    fallback = f"{CATEGORY_ICONS.get(item.get('category', ''), '📋')} {item.get('title', '')}"

    sent = False

    # 1. 카테고리 채널로 발송
    if channel_id and SLACK_BOT_TOKEN:
        if _send_via_bot(channel_id, blocks, fallback):
            logger.info(f"  [Bot] 발송: [{channel_name}] {item['title'][:40]}")
            sent = True
    if not sent:
        if _send_via_webhook(SLACK_WEBHOOK_DEFAULT, blocks, fallback):
            logger.info(f"  [Webhook] 발송: [{channel_name}] {item['title'][:40]}")
            sent = True

    # 2. 긴급(마감 3일 이내) 또는 수원 지역 → 00-긴급-브리핑에 중복 발송
    urgency = item.get("urgency", "medium")
    is_local = item.get("raw_data", {}).get("is_local_suwon", False) if isinstance(item.get("raw_data"), dict) else False
    urgent_channel = SLACK_CHANNELS.get("urgent", "")

    if (urgency in ("critical", "high") or is_local) and urgent_channel and channel_id != urgent_channel:
        tag = "📍수원" if is_local else "⏰긴급"
        urgent_blocks = [{"type": "context", "elements": [{"type": "mrkdwn", "text": f"*{tag} — 카테고리 채널에도 발송됨*"}]}] + blocks
        _send_via_bot(urgent_channel, urgent_blocks, f"[{tag}] {fallback}")
        logger.info(f"  [중복발송] #00-긴급-브리핑 ← {tag}")

    if sent:
        mark_sent(item["item_id"], channel_name)

    return sent


def send_daily_briefing(items: List[Dict]) -> bool:
    """매일 아침 브리핑 요약 — 긴급 채널로 발송"""
    if not items:
        return True

    counts = {}
    for item in items:
        u = item.get("urgency", "medium")
        counts[u] = counts.get(u, 0) + 1

    cat_counts = {}
    for item in items:
        c = item.get("category", "기타")
        cat_counts[c] = cat_counts.get(c, 0) + 1

    summary_text = (
        f"*🛰️ Sentinel Daily Briefing*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 수집된 인텔리전스: *{len(items)}건*\n"
        f"{'🔴 긴급: ' + str(counts.get('critical', 0)) + '건  ' if counts.get('critical') else ''}"
        f"{'🟡 중요: ' + str(counts.get('high', 0)) + '건  ' if counts.get('high') else ''}"
        f"{'🔵 참고: ' + str(counts.get('medium', 0)) + '건  ' if counts.get('medium') else ''}"
        f"\n📁 카테고리: "
        + ", ".join(f"{CATEGORY_ICONS.get(k, '📋')}{k}({v})" for k, v in cat_counts.items())
        + "\n━━━━━━━━━━━━━━━━━━━━"
    )

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": summary_text}},
        {"type": "divider"},
    ]

    # 상위 3개 요약
    sorted_items = sorted(items, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("urgency", "medium"), 2))
    for item in sorted_items[:3]:
        icon = CATEGORY_ICONS.get(item.get("category", ""), "📋")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{icon} *{item['title'][:60]}*\n{item.get('summary', '')[:120]}"}
        })

    fallback = f"Sentinel Briefing: {len(items)}건"

    # 긴급 채널로 브리핑 발송
    urgent_id = SLACK_CHANNELS.get("urgent", "")
    if urgent_id and SLACK_BOT_TOKEN:
        return _send_via_bot(urgent_id, blocks, fallback)

    return _send_via_webhook(SLACK_WEBHOOK_DEFAULT, blocks, fallback)
