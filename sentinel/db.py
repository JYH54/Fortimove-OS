"""
Sentinel DB — 공고 이력 및 중복 제거
"""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DATA_DIR, DB_PATH

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS intel_items (
    item_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,           -- bizinfo, kstartup, mfds, naver, coupang, kipris
    category TEXT NOT NULL,         -- funding, regulation, platform, trend
    title TEXT NOT NULL,
    summary TEXT,                   -- LLM 3줄 요약
    body TEXT,                      -- 원문
    url TEXT,
    deadline TEXT,                  -- 마감일 (YYYY-MM-DD)
    amount TEXT,                    -- 지원 금액
    eligibility_match REAL,         -- 자격 매칭 점수 (0-1)
    urgency TEXT,                   -- critical, high, medium, low
    action_suggestion TEXT,         -- 액션 제안
    keywords_json TEXT,             -- 매칭된 키워드
    raw_data_json TEXT,             -- 원본 파싱 데이터
    slack_sent INTEGER DEFAULT 0,   -- Slack 발송 여부
    slack_channel TEXT,
    user_action TEXT,               -- apply, watch, dismiss
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_intel_source ON intel_items(source);
CREATE INDEX IF NOT EXISTS idx_intel_category ON intel_items(category);
CREATE INDEX IF NOT EXISTS idx_intel_urgency ON intel_items(urgency);
CREATE INDEX IF NOT EXISTS idx_intel_deadline ON intel_items(deadline);
CREATE INDEX IF NOT EXISTS idx_intel_slack ON intel_items(slack_sent);
"""


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


def generate_item_id(source: str, title: str, url: str = "") -> str:
    """중복 방지용 UUID 생성"""
    raw = f"{source}:{title}:{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def item_exists(item_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT 1 FROM intel_items WHERE item_id=?", (item_id,)).fetchone()
        return row is not None


def save_item(item: Dict[str, Any]) -> bool:
    """아이템 저장 (중복이면 False)"""
    if item_exists(item["item_id"]):
        return False

    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO intel_items
            (item_id, source, category, title, summary, body, url, deadline,
             amount, eligibility_match, urgency, action_suggestion,
             keywords_json, raw_data_json, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            item["item_id"], item["source"], item["category"],
            item["title"], item.get("summary", ""),
            item.get("body", ""), item.get("url", ""),
            item.get("deadline", ""), item.get("amount", ""),
            item.get("eligibility_match", 0),
            item.get("urgency", "medium"),
            item.get("action_suggestion", ""),
            json.dumps(item.get("keywords", []), ensure_ascii=False),
            json.dumps(item.get("raw_data", {}), ensure_ascii=False),
            now, now,
        ))
    return True


def get_unsent_items(limit: int = 20) -> List[Dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM intel_items WHERE slack_sent=0 ORDER BY urgency, deadline LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def mark_sent(item_id: str, channel: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE intel_items SET slack_sent=1, slack_channel=?, updated_at=? WHERE item_id=?",
            (channel, datetime.now().isoformat(), item_id)
        )


def get_items(source: Optional[str] = None, category: Optional[str] = None, limit: int = 50) -> List[Dict]:
    query = "SELECT * FROM intel_items WHERE 1=1"
    params = []
    if source:
        query += " AND source=?"
        params.append(source)
    if category:
        query += " AND category=?"
        params.append(category)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(query, params).fetchall()]


init_db()
