"""
LLM 응답 캐시 매니저
=====================
동일 입력에 대한 LLM 호출을 캐싱하여 API 비용 절감

전략:
  - 상품명 + 카테고리 + 국가를 키로 사용
  - SQLite 기반 영구 캐시 (TTL 7일)
  - premium, keyword, review 결과 캐싱
  - 캐시 히트 시 API 호출 0회

사용법 (다른 모듈에서):
  from cache_manager import LLMCache
  cache = LLMCache()

  # 캐시 조회
  cached = cache.get("premium", "콜라겐 분말", category="wellness")
  if cached:
      return cached

  # LLM 호출 후 저장
  result = call_llm(...)
  cache.set("premium", "콜라겐 분말", result, category="wellness")
"""

import os
import json
import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DB = os.getenv("CACHE_DB_PATH", "data/llm_cache.db")
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "7"))


class LLMCache:
    def __init__(self, db_path: str = CACHE_DB):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA encoding = 'UTF-8'")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    tokens_saved INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    hit_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_tool ON llm_cache(tool_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON llm_cache(expires_at)")

    def _make_key(self, tool: str, title: str, **kwargs) -> str:
        """캐시 키 생성 — 상품명 + 도구 + 추가 파라미터"""
        parts = [tool, title.strip().lower()]
        for k in sorted(kwargs.keys()):
            v = kwargs[k]
            if v is not None:
                parts.append(f"{k}={v}")
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]

    def get(self, tool: str, title: str, **kwargs) -> Optional[Dict]:
        """캐시 조회. 만료되었으면 None 반환."""
        key = self._make_key(tool, title, **kwargs)
        now = datetime.now().isoformat()

        with self._conn() as conn:
            row = conn.execute(
                "SELECT result_json, hit_count FROM llm_cache WHERE cache_key = ? AND expires_at > ?",
                (key, now)
            ).fetchone()

            if row:
                conn.execute(
                    "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                    (key,)
                )
                logger.info(f"Cache HIT: {tool}/{title[:20]} (hits: {row['hit_count']+1})")
                return json.loads(row["result_json"])

        return None

    def set(self, tool: str, title: str, result: Dict, tokens_used: int = 0, **kwargs):
        """캐시 저장"""
        key = self._make_key(tool, title, **kwargs)
        now = datetime.now()
        expires = now + timedelta(days=CACHE_TTL_DAYS)

        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO llm_cache
                (cache_key, tool_name, input_hash, result_json, tokens_saved, created_at, expires_at, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                key, tool, key,
                json.dumps(result, ensure_ascii=False),
                tokens_used,
                now.isoformat(),
                expires.isoformat()
            ))
        logger.info(f"Cache SET: {tool}/{title[:20]} (TTL: {CACHE_TTL_DAYS}d)")

    def invalidate(self, tool: str, title: str, **kwargs):
        """특정 캐시 무효화"""
        key = self._make_key(tool, title, **kwargs)
        with self._conn() as conn:
            conn.execute("DELETE FROM llm_cache WHERE cache_key = ?", (key,))

    def clear_expired(self) -> int:
        """만료된 캐시 정리"""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM llm_cache WHERE expires_at <= ?", (now,))
            count = cursor.rowcount
        if count:
            logger.info(f"Cache cleanup: {count}개 만료 항목 삭제")
        return count

    def stats(self) -> Dict:
        """캐시 통계"""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
            total_hits = conn.execute("SELECT COALESCE(SUM(hit_count), 0) FROM llm_cache").fetchone()[0]
            total_tokens = conn.execute("SELECT COALESCE(SUM(tokens_saved * hit_count), 0) FROM llm_cache").fetchone()[0]

            by_tool = {}
            rows = conn.execute(
                "SELECT tool_name, COUNT(*) as cnt, SUM(hit_count) as hits FROM llm_cache GROUP BY tool_name"
            ).fetchall()
            for r in rows:
                by_tool[r["tool_name"]] = {"entries": r["cnt"], "hits": r["hits"]}

        return {
            "total_entries": total,
            "total_hits": total_hits,
            "estimated_tokens_saved": total_tokens,
            "estimated_cost_saved_usd": round(total_tokens * 0.000003, 4),
            "by_tool": by_tool,
        }

    def clear_all(self) -> int:
        """전체 캐시 삭제"""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM llm_cache")
            return cursor.rowcount
