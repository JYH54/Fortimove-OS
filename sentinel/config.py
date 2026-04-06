"""
Project Sentinel — Configuration (.env 기반)
"""

import os
from pathlib import Path

# .env 로드
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

# ── Slack ─────────────────────────────────────────────────
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")

SLACK_CHANNELS = {
    "urgent":    os.getenv("CHANNEL_ID_URGENT", "C0ARMGT1SKA"),
    "funding":   os.getenv("CHANNEL_ID_MONEY", "C0AQWS67UNQ"),
    "health":    os.getenv("CHANNEL_ID_WELLNESS", "C0AQLSVV2M9"),
    "platform":  os.getenv("CHANNEL_ID_ECOMMERCE", "C0AQR6Z5F3Q"),
}

# Webhook 폴백
SLACK_WEBHOOK_DEFAULT = os.getenv(
    "SLACK_WEBHOOK_URL",
    "https://hooks.slack.com/services/REDACTED"
)

# ── API Keys ──────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── 기업 프로필 ───────────────────────────────────────────
COMPANY_PROFILE = {
    "name": "Fortimove Global",
    "business_type": "이커머스/해외구매대행",
    "industry": ["건강기능식품", "웰니스", "헬스케어", "해외직구", "구매대행"],
    "location": "경기도 수원시 영통구",
    "region_keywords": ["수원", "영통", "경기", "전국"],
    "employee_count": 1,
    "revenue_krw": 0,
    "founded_year": 2026,
    "ceo_age_group": "청년",
    "certifications": [],
    "vision": "구매대행 → 웰니스/헬스케어 대기업",
    "current_stage": "초기 창업 (구매대행 운영 중)",
}

# ── 크롤링 키워드 ─────────────────────────────────────────
KEYWORDS = {
    "primary": ["헬스케어", "건강기능식품", "이커머스", "구매대행", "웰니스", "해외직구"],
    "location": ["수원", "영통", "경기", "전국"],
    "support_type": ["청년창업", "수출", "온라인판매", "소상공인", "창업지원", "1인기업", "초기창업"],
}

# ── 스케줄 / 경로 ─────────────────────────────────────────
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "09:00")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "sentinel.db")
