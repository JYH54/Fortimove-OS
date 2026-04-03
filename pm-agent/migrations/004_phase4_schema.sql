-- ============================================================
-- Phase 4 DB Schema Migration
-- 작성일: 2026-03-31
-- 목적: Review-First Publishing Console 지원
-- ============================================================

-- ============================================================
-- 1. approval_queue 테이블 확장 (Generated vs Reviewed 분리)
-- ============================================================

-- Generated fields (AI/Template 자동 생성, READ-ONLY)
ALTER TABLE approval_queue ADD COLUMN generated_naver_title TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_naver_description TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_naver_tags TEXT;  -- JSON array

ALTER TABLE approval_queue ADD COLUMN generated_coupang_title TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_coupang_description TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_coupang_tags TEXT;  -- JSON array

ALTER TABLE approval_queue ADD COLUMN generated_options_json TEXT;  -- JSON array
ALTER TABLE approval_queue ADD COLUMN generated_price REAL;
ALTER TABLE approval_queue ADD COLUMN generated_category TEXT;

-- Reviewed fields (운영자 수정 가능)
ALTER TABLE approval_queue ADD COLUMN reviewed_naver_title TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_naver_description TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_naver_tags TEXT;  -- JSON array

ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_title TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_description TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_tags TEXT;  -- JSON array

ALTER TABLE approval_queue ADD COLUMN reviewed_options_json TEXT;  -- JSON array
ALTER TABLE approval_queue ADD COLUMN reviewed_price REAL;
ALTER TABLE approval_queue ADD COLUMN reviewed_category TEXT;

-- Review metadata
ALTER TABLE approval_queue ADD COLUMN review_status TEXT DEFAULT 'draft';
-- 'draft', 'under_review', 'approved_for_export', 'approved_for_upload', 'hold', 'rejected'

ALTER TABLE approval_queue ADD COLUMN reviewed_at TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_by TEXT;
ALTER TABLE approval_queue ADD COLUMN review_notes TEXT;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_approval_review_status ON approval_queue(review_status);
CREATE INDEX IF NOT EXISTS idx_approval_reviewed_at ON approval_queue(reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_reviewed_by ON approval_queue(reviewed_by);

-- ============================================================
-- 2. image_review 테이블 생성 (이미지 검수 관리)
-- ============================================================

CREATE TABLE IF NOT EXISTS image_review (
    image_review_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    -- Original images (from source)
    original_images_json TEXT NOT NULL,  -- JSON array of URLs

    -- Reviewed images (with metadata)
    reviewed_images_json TEXT NOT NULL,  -- JSON array
    -- [
    --   {
    --     "url": "https://...",
    --     "order": 1,
    --     "is_primary": true,
    --     "excluded": false,
    --     "warnings": ["low_resolution"]
    --   }
    -- ]

    primary_image_index INTEGER DEFAULT 0,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_image_review_review ON image_review(review_id);

-- ============================================================
-- 3. review_history 테이블 생성 (검수 이력 추적)
-- ============================================================

CREATE TABLE IF NOT EXISTS review_history (
    history_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    -- Action type
    action TEXT NOT NULL,  -- 'edit', 'approve_export', 'approve_upload', 'reject', 'hold'

    -- Snapshot before change
    previous_state_json TEXT,  -- JSON of reviewed_* fields before change

    -- Changed fields
    changed_fields TEXT,  -- JSON array: ["reviewed_naver_title", "reviewed_price"]

    -- Changes detail
    changes_json TEXT,  -- JSON: {"reviewed_price": {"old": 15900, "new": 17900}}

    -- Actor
    changed_by TEXT NOT NULL,
    change_reason TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_review_history_review ON review_history(review_id);
CREATE INDEX IF NOT EXISTS idx_review_history_action ON review_history(action);
CREATE INDEX IF NOT EXISTS idx_review_history_created ON review_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_history_actor ON review_history(changed_by);

-- ============================================================
-- 4. export_log 테이블 생성 (Export 이력)
-- ============================================================

CREATE TABLE IF NOT EXISTS export_log (
    export_id TEXT PRIMARY KEY,

    -- Export info
    channel TEXT NOT NULL,  -- 'naver', 'coupang'
    review_ids TEXT NOT NULL,  -- JSON array of review_ids

    -- Export result
    export_format TEXT NOT NULL,  -- 'csv', 'excel', 'json'
    export_file_path TEXT,
    export_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'completed', 'failed'
    export_error TEXT,

    -- Metadata
    row_count INTEGER,
    file_size INTEGER,

    -- Actor
    exported_by TEXT NOT NULL,
    export_reason TEXT,

    created_at TEXT NOT NULL,
    completed_at TEXT,

    FOREIGN KEY (channel) REFERENCES channel_configs (channel)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_export_channel ON export_log(channel);
CREATE INDEX IF NOT EXISTS idx_export_status ON export_log(export_status);
CREATE INDEX IF NOT EXISTS idx_export_created ON export_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_export_actor ON export_log(exported_by);

-- ============================================================
-- 5. Default Data 삽입
-- ============================================================

-- Review status configurations (for UI dropdown)
CREATE TABLE IF NOT EXISTS review_status_config (
    status TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT,
    color TEXT,  -- UI color code
    allowed_next_states TEXT,  -- JSON array
    active INTEGER DEFAULT 1
);

INSERT OR IGNORE INTO review_status_config (status, display_name, description, color, allowed_next_states)
VALUES
    ('draft', '초안', '검수 전 임시 저장', '#gray', '["under_review", "hold"]'),
    ('under_review', '검수 중', '운영자가 검수 진행 중', '#blue', '["approved_for_export", "hold", "rejected"]'),
    ('approved_for_export', 'Export 승인', 'CSV Export 가능', '#green', '["approved_for_upload", "hold"]'),
    ('approved_for_upload', 'Upload 승인', 'API 업로드 가능 (수동)', '#purple', '["hold"]'),
    ('hold', '보류', '추가 검토 필요', '#yellow', '["under_review", "rejected"]'),
    ('rejected', '거부', '등록 불가', '#red', '[]');

-- ============================================================
-- 6. 마이그레이션 완료 확인
-- ============================================================

SELECT 'Migration 004 (Phase 4) completed successfully' AS status;
