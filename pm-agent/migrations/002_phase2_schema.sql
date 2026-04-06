-- ============================================================
-- Phase 2 DB Schema Migration
-- 작성일: 2026-03-31
-- 목적: 점수화, 우선순위, 채널별 업로드 대기열 지원
-- ============================================================

-- ============================================================
-- 1. approval_queue 테이블 확장 (SQLite)
-- ============================================================

-- 점수 및 결정 관련 컬럼
ALTER TABLE approval_queue ADD COLUMN score INTEGER DEFAULT 0;
ALTER TABLE approval_queue ADD COLUMN decision TEXT DEFAULT 'review';  -- auto_approve, review, hold, reject
ALTER TABLE approval_queue ADD COLUMN priority INTEGER DEFAULT 50;
ALTER TABLE approval_queue ADD COLUMN reasons_json TEXT;  -- JSON array of reasons
ALTER TABLE approval_queue ADD COLUMN scoring_updated_at TEXT;

-- 콘텐츠 생성 상태
ALTER TABLE approval_queue ADD COLUMN content_status TEXT DEFAULT 'pending';  -- pending, processing, completed, failed

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_approval_queue_score ON approval_queue(score DESC);
CREATE INDEX IF NOT EXISTS idx_approval_queue_priority ON approval_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_approval_queue_decision ON approval_queue(decision);
CREATE INDEX IF NOT EXISTS idx_approval_queue_content_status ON approval_queue(content_status);

-- ============================================================
-- 2. wellness_products 테이블 확장 (PostgreSQL)
-- ============================================================

-- PostgreSQL 명령어 (원격 서버에서 실행)
-- ALTER TABLE wellness_products ADD COLUMN IF NOT EXISTS scoring_updated_at TIMESTAMP;
-- ALTER TABLE wellness_products ADD COLUMN IF NOT EXISTS publishing_status VARCHAR(50) DEFAULT 'draft';
-- CREATE INDEX IF NOT EXISTS idx_wellness_scoring ON wellness_products(scoring_updated_at DESC);
-- CREATE INDEX IF NOT EXISTS idx_wellness_publishing ON wellness_products(publishing_status);

-- ============================================================
-- 3. channel_upload_queue 테이블 생성 (SQLite)
-- ============================================================

CREATE TABLE IF NOT EXISTS channel_upload_queue (
    upload_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,  -- FK to approval_queue
    channel TEXT NOT NULL,  -- 'naver', 'coupang', 'amazon', etc.

    -- 채널별 맞춤 콘텐츠 (JSON)
    content_json TEXT NOT NULL,

    -- 업로드 상태
    upload_status TEXT NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    upload_error TEXT,

    -- 타임스탬프
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    uploaded_at TEXT,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_channel_upload_status ON channel_upload_queue(upload_status);
CREATE INDEX IF NOT EXISTS idx_channel_upload_channel ON channel_upload_queue(channel);
CREATE INDEX IF NOT EXISTS idx_channel_upload_review ON channel_upload_queue(review_id);
CREATE INDEX IF NOT EXISTS idx_channel_upload_created ON channel_upload_queue(created_at DESC);

-- ============================================================
-- 4. 점수 기록 테이블 (선택 사항, 향후 분석용)
-- ============================================================

CREATE TABLE IF NOT EXISTS scoring_history (
    history_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    -- 점수 상세
    score INTEGER NOT NULL,
    decision TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    breakdown_json TEXT NOT NULL,  -- 점수 항목별 상세

    -- 타임스탬프
    created_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scoring_history_review ON scoring_history(review_id);
CREATE INDEX IF NOT EXISTS idx_scoring_history_created ON scoring_history(created_at DESC);

-- ============================================================
-- 5. 채널별 설정 테이블 (선택 사항)
-- ============================================================

CREATE TABLE IF NOT EXISTS channel_configs (
    channel TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,  -- JSON: 제목 길이, 금지 표현, 템플릿 등
    active BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 기본 채널 설정 삽입
INSERT OR IGNORE INTO channel_configs (channel, config_json, active, created_at, updated_at)
VALUES
    ('naver', '{"max_title_length": 50, "max_description_length": 2000}', 1, datetime('now'), datetime('now')),
    ('coupang', '{"max_title_length": 100, "max_description_length": 3000}', 1, datetime('now'), datetime('now')),
    ('amazon', '{"max_title_length": 200, "max_description_length": 5000}', 1, datetime('now'), datetime('now'));

-- ============================================================
-- 6. 마이그레이션 완료 확인
-- ============================================================

-- SQLite에서 실행 확인
SELECT 'Migration 002 completed successfully' AS status;

-- ============================================================
-- 사용 예시
-- ============================================================

/*
-- 1. 점수 업데이트
UPDATE approval_queue
SET score = 85,
    decision = 'auto_approve',
    priority = 1,
    reasons_json = '["높은 마진율 (45%): +30점", "정책 위험 없음: +25점"]',
    scoring_updated_at = datetime('now')
WHERE review_id = 'abc123';

-- 2. 점수순 정렬 조회
SELECT review_id, source_title, score, decision, priority
FROM approval_queue
WHERE reviewer_status = 'pending'
ORDER BY score DESC, priority ASC
LIMIT 10;

-- 3. 채널별 업로드 대기열 추가
INSERT INTO channel_upload_queue (
    upload_id, review_id, channel, content_json,
    upload_status, created_at, updated_at
) VALUES (
    'upload-' || hex(randomblob(8)),
    'abc123',
    'naver',
    '{"title": "상품명", "description": "설명"}',
    'pending',
    datetime('now'),
    datetime('now')
);

-- 4. 업로드 대기 중인 항목 조회
SELECT u.upload_id, u.channel, a.source_title, u.upload_status
FROM channel_upload_queue u
JOIN approval_queue a ON u.review_id = a.review_id
WHERE u.upload_status = 'pending'
ORDER BY u.created_at ASC;
*/
