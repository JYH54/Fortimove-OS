-- 005_redesign_schema.sql
-- 상세페이지 리디자인 파이프라인 스키마

CREATE TABLE IF NOT EXISTS redesign_queue (
    redesign_id TEXT PRIMARY KEY,
    review_id TEXT,                          -- approval_queue FK (nullable: 수동 업로드 시 없음)

    -- 소스 정보
    source_type TEXT NOT NULL,               -- sourcing_agent / manual_upload / employee
    source_title TEXT NOT NULL,
    source_images_json TEXT NOT NULL,         -- JSON: 원본 이미지 경로/URL 배열
    moodtone TEXT DEFAULT 'premium',         -- premium / value / minimal / trendy
    category TEXT DEFAULT 'general',         -- wellness / supplement / beauty 등

    -- 파이프라인 상태
    status TEXT NOT NULL DEFAULT 'waiting',   -- waiting / processing / completed / failed
    trigger_type TEXT,                        -- manual / auto_score
    trigger_score INTEGER,                   -- 자동 트리거 시 점수

    -- 파이프라인 결과
    localized_images_json TEXT,              -- JSON: image-localization API 결과
    text_content_json TEXT,                  -- JSON: DetailPageStrategist 결과
    composed_images_json TEXT,               -- JSON: [{filename, section_type, display_order}]
    output_directory TEXT,                   -- 출력 디렉토리 경로

    -- 편집 상태
    edit_overrides_json TEXT,                -- JSON: 사용자 수정 {section: {text, image_path}}

    -- 메타
    error_message TEXT,
    processing_started_at TEXT,
    processing_completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_redesign_status ON redesign_queue(status);
CREATE INDEX IF NOT EXISTS idx_redesign_review ON redesign_queue(review_id);
CREATE INDEX IF NOT EXISTS idx_redesign_created ON redesign_queue(created_at DESC);
