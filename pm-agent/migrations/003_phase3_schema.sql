-- ============================================================
-- Phase 3 DB Schema Migration
-- 작성일: 2026-03-31
-- 목적: Auto-Scoring, Validation, Semi-Auto Upload 지원
-- ============================================================

-- ============================================================
-- 1. approval_queue 테이블 확장 (Retry & Audit)
-- ============================================================

-- Retry 관련
ALTER TABLE approval_queue ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE approval_queue ADD COLUMN last_error TEXT;

-- Validation 및 Approval 타임스탬프
ALTER TABLE approval_queue ADD COLUMN validated_at TEXT;
ALTER TABLE approval_queue ADD COLUMN approved_at TEXT;
ALTER TABLE approval_queue ADD COLUMN approved_by TEXT;  -- 'system' or user_id

-- Audit trail (JSON array of actions)
ALTER TABLE approval_queue ADD COLUMN audit_trail TEXT;  -- JSON: [{"action": "scored", "actor": "system", "timestamp": "..."}]

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_approval_retry ON approval_queue(retry_count);
CREATE INDEX IF NOT EXISTS idx_approval_approved_at ON approval_queue(approved_at DESC);

-- ============================================================
-- 2. channel_upload_queue 테이블 확장 (Validation & Upload)
-- ============================================================

-- Retry 관련
ALTER TABLE channel_upload_queue ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE channel_upload_queue ADD COLUMN last_error TEXT;

-- Validation 상태
ALTER TABLE channel_upload_queue ADD COLUMN validation_status TEXT DEFAULT 'pending';
-- 'pending', 'validating', 'validated', 'validation_failed', 'validation_error'

ALTER TABLE channel_upload_queue ADD COLUMN validation_errors TEXT;  -- JSON array
ALTER TABLE channel_upload_queue ADD COLUMN validated_at TEXT;

-- Upload 준비 상태
ALTER TABLE channel_upload_queue ADD COLUMN ready_at TEXT;  -- When approved for upload
ALTER TABLE channel_upload_queue ADD COLUMN ready_by TEXT;  -- 'system' or user_id

-- Export 데이터 (CSV/Excel 출력용)
ALTER TABLE channel_upload_queue ADD COLUMN export_data TEXT;  -- JSON

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_upload_validation ON channel_upload_queue(validation_status);
CREATE INDEX IF NOT EXISTS idx_upload_retry ON channel_upload_queue(retry_count);
CREATE INDEX IF NOT EXISTS idx_upload_ready_at ON channel_upload_queue(ready_at DESC);

-- ============================================================
-- 3. audit_log 테이블 생성 (Auditable)
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,

    -- Entity reference
    entity_type TEXT NOT NULL,  -- 'approval', 'upload', 'wellness_product'
    entity_id TEXT NOT NULL,

    -- Action
    action TEXT NOT NULL,  -- 'scored', 'approved', 'rejected', 'validated', 'uploaded', etc.
    old_status TEXT,
    new_status TEXT,

    -- Actor
    actor TEXT NOT NULL,  -- 'system', 'user:{user_id}'
    reason TEXT,

    -- Metadata
    metadata TEXT,  -- JSON

    -- Timestamp
    created_at TEXT NOT NULL
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);

-- ============================================================
-- 4. validation_rules 테이블 생성 (Hot-reload rules)
-- ============================================================

CREATE TABLE IF NOT EXISTS validation_rules (
    rule_id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,  -- 'naver', 'coupang', 'amazon'
    rule_type TEXT NOT NULL,  -- 'title_length', 'prohibited_words', 'price_range', etc.
    rule_config TEXT NOT NULL,  -- JSON config
    severity TEXT NOT NULL DEFAULT 'error',  -- 'error', 'warning'
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_validation_channel ON validation_rules(channel, active);

-- 기본 검증 규칙 삽입
INSERT OR IGNORE INTO validation_rules (rule_id, channel, rule_type, rule_config, severity, created_at, updated_at)
VALUES
    -- Naver 규칙
    ('naver-title-length', 'naver', 'title_length', '{"max": 50}', 'error', datetime('now'), datetime('now')),
    ('naver-prohibited-words', 'naver', 'prohibited_words', '{"words": ["의료기기", "치료", "질병", "FDA", "특허", "임상", "승인", "인증번호"]}', 'error', datetime('now'), datetime('now')),
    ('naver-price-min', 'naver', 'price_range', '{"min": 1000, "max": 10000000}', 'error', datetime('now'), datetime('now')),
    ('naver-option-max', 'naver', 'option_limit', '{"max": 100}', 'error', datetime('now'), datetime('now')),
    ('naver-image-min', 'naver', 'image_requirement', '{"min": 1, "max": 20}', 'error', datetime('now'), datetime('now')),

    -- Coupang 규칙
    ('coupang-title-length', 'coupang', 'title_length', '{"max": 100}', 'error', datetime('now'), datetime('now')),
    ('coupang-prohibited-words', 'coupang', 'prohibited_words', '{"words": ["의료기기", "치료", "질병", "FDA", "특허", "임상", "승인", "인증번호"]}', 'error', datetime('now'), datetime('now')),
    ('coupang-price-min', 'coupang', 'price_range', '{"min": 1000, "max": 10000000}', 'error', datetime('now'), datetime('now')),
    ('coupang-delivery-tag', 'coupang', 'required_tag', '{"tags": ["오늘출발", "로켓배송"]}', 'warning', datetime('now'), datetime('now')),
    ('coupang-return-policy', 'coupang', 'required_field', '{"fields": ["return_policy"]}', 'error', datetime('now'), datetime('now'));

-- ============================================================
-- 5. workflow_state 테이블 생성 (State machine tracking)
-- ============================================================

CREATE TABLE IF NOT EXISTS workflow_state (
    state_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL UNIQUE,  -- FK to approval_queue

    -- Current state
    current_state TEXT NOT NULL,
    -- 'scored', 'content_generated', 'validated', 'ready_to_upload', 'uploading', 'completed'

    -- State history
    state_history TEXT NOT NULL,  -- JSON array of {state, timestamp, actor}

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_workflow_state ON workflow_state(current_state);
CREATE INDEX IF NOT EXISTS idx_workflow_review ON workflow_state(review_id);

-- ============================================================
-- 6. retry_queue 테이블 생성 (Failed jobs retry)
-- ============================================================

CREATE TABLE IF NOT EXISTS retry_queue (
    retry_id TEXT PRIMARY KEY,

    -- Task info
    task_type TEXT NOT NULL,  -- 'scoring', 'content_generation', 'validation', 'upload'
    task_payload TEXT NOT NULL,  -- JSON

    -- Retry info
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    last_error TEXT,
    next_retry_at TEXT,  -- Exponential backoff

    -- Status
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'retrying', 'completed', 'failed_permanent'

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_retry_status ON retry_queue(status);
CREATE INDEX IF NOT EXISTS idx_retry_next_at ON retry_queue(next_retry_at);
CREATE INDEX IF NOT EXISTS idx_retry_task_type ON retry_queue(task_type);

-- ============================================================
-- 7. 마이그레이션 완료 확인
-- ============================================================

SELECT 'Migration 003 (Phase 3) completed successfully' AS status;
