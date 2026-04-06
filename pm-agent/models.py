"""
SQLAlchemy ORM Models for Fortimove PM Agent
- 기존 SQLite 스키마를 SQLAlchemy로 선언
- PostgreSQL + SQLite 모두 호환
- Alembic autogenerate 지원
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, ForeignKey,
    Index, JSON, create_engine
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Organization(Base):
    __tablename__ = "organizations"

    org_id = Column(String(32), primary_key=True)
    org_name = Column(String(255), nullable=False)
    plan = Column(String(50), default="free")  # free, pro, enterprise
    api_quota_monthly = Column(Integer, default=1000)
    api_usage_current = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(32), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), nullable=False, default="viewer")  # admin, operator, viewer
    org_id = Column(String(32), ForeignKey("organizations.org_id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")


class ApprovalQueueItem(Base):
    __tablename__ = "approval_queue"

    review_id = Column(String(36), primary_key=True)
    source_type = Column(String(100), nullable=False)
    source_title = Column(Text, nullable=False)
    registration_title_ko = Column(Text, nullable=True)
    registration_status = Column(String(50), nullable=False)
    needs_human_review = Column(Boolean, nullable=False)
    hold_reason = Column(Text, nullable=True)
    reject_reason = Column(Text, nullable=True)
    risk_notes_json = Column(Text, nullable=True)
    suggested_next_action = Column(Text, nullable=True)
    raw_agent_output = Column(Text, nullable=False)
    source_data_json = Column(Text, nullable=True)
    latest_revision_id = Column(String(36), nullable=True)
    latest_revision_number = Column(Integer, nullable=True)
    latest_registration_status = Column(String(50), nullable=True)
    latest_registration_title_ko = Column(Text, nullable=True)
    reviewer_status = Column(String(50), nullable=False, index=True)
    reviewer_note = Column(Text, nullable=True)
    # Multi-tenancy
    org_id = Column(String(32), ForeignKey("organizations.org_id"), nullable=True, index=True)
    created_by = Column(String(32), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    revisions = relationship("Revision", back_populates="queue_item")


class Revision(Base):
    __tablename__ = "revisions"

    revision_id = Column(String(36), primary_key=True)
    review_id = Column(String(36), ForeignKey("approval_queue.review_id"), nullable=False, index=True)
    revision_number = Column(Integer, nullable=False)
    source_snapshot_json = Column(Text, nullable=False)
    previous_agent_output_json = Column(Text, nullable=True)
    reviewer_note = Column(Text, nullable=True)
    revised_agent_output_json = Column(Text, nullable=True)
    generation_status = Column(String(50), nullable=False)  # pending, completed, failed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    queue_item = relationship("ApprovalQueueItem", back_populates="revisions")


class HandoffLog(Base):
    __tablename__ = "handoff_logs"

    log_id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    item_count = Column(Integer, nullable=False)
    export_generated = Column(Boolean, nullable=False)
    slack_status = Column(String(50), nullable=False)
    slack_error = Column(Text, nullable=True)
    email_status = Column(String(50), nullable=False)
    email_error = Column(Text, nullable=True)
    mode = Column(String(50), nullable=False)


class HandoffRun(Base):
    __tablename__ = "handoff_runs"

    run_id = Column(String(36), primary_key=True)
    status = Column(String(50), nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    mode = Column(String(50), nullable=False)
    item_count = Column(Integer, nullable=True)
    slack_status = Column(String(50), nullable=True)
    email_status = Column(String(50), nullable=True)
    overall_result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)


class ApiUsageLog(Base):
    """API 사용량 추적 (Phase 2 과금 준비)"""
    __tablename__ = "api_usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String(32), ForeignKey("organizations.org_id"), nullable=False, index=True)
    user_id = Column(String(32), ForeignKey("users.user_id"), nullable=True)
    agent_name = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    tokens_used = Column(Integer, default=0)
    cost_estimate_krw = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_usage_org_date", "org_id", "created_at"),
    )
