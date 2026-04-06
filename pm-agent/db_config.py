"""
데이터베이스 설정 모듈
- 환경변수에 따라 PostgreSQL 또는 SQLite 선택
- Phase 1-4: SQLite → PostgreSQL 마이그레이션 지원
- Phase 1-5: Alembic 마이그레이션 프레임워크 연동
"""

import os
import logging

logger = logging.getLogger(__name__)

# Database URL 결정
# PostgreSQL: postgresql://user:pass@host:port/dbname
# SQLite: sqlite:///path/to/db.sqlite (default for dev)
DATABASE_URL = os.getenv(
    "PM_DATABASE_URL",
    os.getenv("DATABASE_URL", "sqlite:///data/pm_agent.db")
)

def is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")

def get_sync_url() -> str:
    """SQLAlchemy 동기 URL 반환"""
    return DATABASE_URL

def get_async_url() -> str:
    """SQLAlchemy 비동기 URL 반환"""
    if is_postgres():
        return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    return DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

# Log database type at import time
if is_postgres():
    # 비밀번호 마스킹
    safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    logger.info(f"Database: PostgreSQL ({safe_url})")
else:
    logger.info(f"Database: SQLite ({DATABASE_URL})")
