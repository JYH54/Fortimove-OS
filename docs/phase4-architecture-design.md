# Phase 4 Architecture Design - Review-First Publishing Console

**날짜**: 2026-03-31
**목표**: 자동 생성 결과물의 운영자 검수, 수정, 승인 후 export/upload 실행 시스템
**방향**: Human-in-the-Loop, Export-First (API 자동 업로드 보류)

---

## 📋 요구사항 분석

### 1. Review Console UI

**목적**: 상품별 상세 검수 화면

**표시 항목**:
- ✅ Score, Decision, Reasons (Phase 3 scoring 결과)
- ✅ Margin 분석 (수익성)
- ✅ Risk 분석 (정책 위험, 인증 요구사항)
- ✅ Validation 결과 (Naver/Coupang 검증)
- ✅ 채널별 콘텐츠 (Naver/Coupang 제목, 설명, 태그, 옵션, 가격)
- ✅ 원본 데이터 vs 생성 결과 동시 표시

**UI 구조**:
```
┌─────────────────────────────────────────────────────────────┐
│ Review Console - Product Detail                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ [Score: 75] [Decision: review] [Status: under_review]      │
│                                                             │
│ ┌─────────────────┬─────────────────┐                      │
│ │ 원본 데이터       │ 생성된 콘텐츠     │                      │
│ ├─────────────────┼─────────────────┤                      │
│ │ 제품명: ...      │ Naver 제목: ... │ [Edit]              │
│ │ 가격: 15,900원   │ Coupang 제목:...│ [Edit]              │
│ │ 옵션: [...]      │ 설명: ...       │ [Edit]              │
│ │ 이미지: [...]    │ 태그: [...]     │ [Edit]              │
│ └─────────────────┴─────────────────┘                      │
│                                                             │
│ [Reasons]                                                   │
│ • 마진율 45%: +30점                                          │
│ • 정책 위험 없음: +25점                                      │
│                                                             │
│ [Validation Results]                                        │
│ Naver: ✅ Valid | Coupang: ⚠️ Warning (배송 태그 권장)      │
│                                                             │
│ [Actions]                                                   │
│ [Save Draft] [Approve for Export] [Reject] [Hold]          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. Editable Review Fields

**목적**: 생성된 데이터와 검수된 데이터 분리 저장

**데이터 분리 원칙**:
```
generated_*  → AI/Template이 자동 생성한 원본 (수정 불가)
reviewed_*   → 운영자가 검수하고 수정한 최종본 (수정 가능)
```

**필드 구조**:

#### approval_queue 테이블 확장
```sql
-- Generated fields (AI/Template 결과, READ-ONLY)
generated_naver_title TEXT,
generated_naver_description TEXT,
generated_naver_tags TEXT,  -- JSON array

generated_coupang_title TEXT,
generated_coupang_description TEXT,
generated_coupang_tags TEXT,  -- JSON array

generated_options_json TEXT,  -- JSON array
generated_price REAL,
generated_category TEXT,

-- Reviewed fields (운영자 수정 가능)
reviewed_naver_title TEXT,
reviewed_naver_description TEXT,
reviewed_naver_tags TEXT,

reviewed_coupang_title TEXT,
reviewed_coupang_description TEXT,
reviewed_coupang_tags TEXT,

reviewed_options_json TEXT,
reviewed_price REAL,
reviewed_category TEXT,

-- Review metadata
review_status TEXT DEFAULT 'draft',
-- 'draft', 'under_review', 'approved_for_export', 'approved_for_upload', 'hold', 'rejected'

reviewed_at TEXT,
reviewed_by TEXT,
review_notes TEXT
```

**Edit Flow**:
```
1. User opens review console
2. Sees generated_* fields (원본)
3. Clicks [Edit] button
4. Edits in reviewed_* fields (복사본)
5. Clicks [Save Draft]
6. reviewed_* fields updated
7. Clicks [Approve for Export]
8. review_status → 'approved_for_export'
```

---

### 3. Image Review Panel

**목적**: 이미지 관리 및 검수

**기능**:
- ✅ 대표 이미지 지정 (primary_image_index)
- ✅ 이미지 순서 변경 (image_order)
- ✅ 이미지 제외 (image_excluded)
- ✅ 이미지 경고 표시 (image_warnings)

**DB 구조**:

#### image_review 테이블 (신규)
```sql
CREATE TABLE image_review (
    image_review_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    -- Original images (from source)
    original_images_json TEXT NOT NULL,  -- JSON array of URLs

    -- Reviewed images
    reviewed_images_json TEXT NOT NULL,  -- JSON array with metadata
    -- [
    --   {"url": "...", "order": 1, "is_primary": true, "excluded": false, "warnings": []},
    --   {"url": "...", "order": 2, "is_primary": false, "excluded": false, "warnings": ["low_resolution"]}
    -- ]

    primary_image_index INTEGER DEFAULT 0,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);
```

**UI**:
```
┌──────────────────────────────────────────┐
│ Image Review Panel                       │
├──────────────────────────────────────────┤
│                                          │
│ [Image 1] ⭐ Primary                     │
│ ┌──────────┐                             │
│ │          │ [Set as Primary]            │
│ │  Image   │ [Move Up] [Move Down]       │
│ │          │ [Exclude]                   │
│ └──────────┘ ⚠️ Warning: Low resolution  │
│                                          │
│ [Image 2]                                │
│ ┌──────────┐                             │
│ │          │ [Set as Primary]            │
│ │  Image   │ [Move Up] [Move Down]       │
│ │          │ [Exclude]                   │
│ └──────────┘                             │
│                                          │
└──────────────────────────────────────────┘
```

---

### 4. Review Workflow

**목적**: 검수 프로세스 상태 관리

**상태 정의**:
```
draft                 → 초안 (저장 중)
under_review          → 검수 중
approved_for_export   → Export 승인 (CSV 다운로드 가능)
approved_for_upload   → Upload 승인 (API 업로드 가능)
hold                  → 보류 (추가 검토 필요)
rejected              → 거부 (등록 불가)
```

**상태 전이 규칙**:
```
                    draft
                      ↓
                [Start Review]
                      ↓
                under_review
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
   [Approve]      [Hold]       [Reject]
        ↓             ↓             ↓
approved_for_export  hold       rejected
        ↓
   [Enable Upload]
        ↓
approved_for_upload
```

**Actions**:

#### 1. Save Draft
```python
POST /api/phase4/review/{review_id}/save
{
    "reviewed_naver_title": "...",
    "reviewed_naver_description": "...",
    "reviewed_price": 15900,
    "review_notes": "가격 수정함"
}
→ review_status: draft (변경 없음)
```

#### 2. Approve for Export
```python
POST /api/phase4/review/{review_id}/approve-export
{
    "review_notes": "검수 완료, export 승인"
}
→ review_status: draft → approved_for_export
→ Export 버튼 활성화
```

#### 3. Reject
```python
POST /api/phase4/review/{review_id}/reject
{
    "review_notes": "금지어 포함으로 거부"
}
→ review_status: rejected
```

#### 4. Hold
```python
POST /api/phase4/review/{review_id}/hold
{
    "review_notes": "추가 확인 필요"
}
→ review_status: hold
```

---

### 5. Export-First

**목적**: 검수 완료 후 Export 파일 생성 (API 업로드는 수동 실행)

**Export Workflow**:
```
1. 운영자가 reviewed_* 필드 수정
2. [Approve for Export] 클릭
3. review_status → approved_for_export
4. [Export to Naver CSV] 버튼 활성화
5. [Export to Coupang CSV] 버튼 활성화
6. 운영자가 CSV 다운로드
7. 운영자가 수동으로 Naver/Coupang에 업로드

(Optional)
8. [Enable API Upload] 클릭 (수동)
9. review_status → approved_for_upload
10. [Upload to Naver API] 버튼 활성화 (수동 실행)
```

**Export Format**:

#### Naver Export (reviewed_* 필드 사용)
```csv
상품명,판매가,재고수량,상품상세,옵션,배송비,반품정보,이미지URL1,이미지URL2,이미지URL3
{reviewed_naver_title},{reviewed_price},100,{reviewed_naver_description},{reviewed_options_json},...
```

#### Coupang Export (reviewed_* 필드 사용)
```csv
상품명,판매가,할인가,상품설명,배송정보,반품정책,대표이미지
{reviewed_coupang_title},{reviewed_price},{reviewed_price},{reviewed_coupang_description},...
```

**Export API**:
```python
GET /api/phase4/export/naver?review_ids=id1,id2,id3
→ Returns: Naver CSV file (using reviewed_* fields)

GET /api/phase4/export/coupang?review_ids=id1,id2,id3
→ Returns: Coupang CSV file (using reviewed_* fields)
```

**Auto Upload OFF (기본값)**:
```python
# .env 설정
AUTO_UPLOAD_ENABLED=false  # Default

# API upload는 수동 실행만 허용
POST /api/phase4/upload/naver/{review_id}
→ Requires: review_status = 'approved_for_upload'
→ Requires: Explicit user action (not automated)
```

---

## 🏗️ 시스템 아키텍처

### Phase 4 Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   PHASE 4: REVIEW-FIRST CONSOLE                     │
└─────────────────────────────────────────────────────────────────────┘

[Phase 3 Output]
    approval_queue (score, decision, generated_* fields)
    channel_upload_queue (validation results)
          ↓
[1] Review Console UI
          ├── Display generated_* fields (READ-ONLY)
          ├── Display score, decision, reasons
          ├── Display validation results
          └── Display original source data
          ↓
[2] Operator Edit
          ├── Edit reviewed_naver_title
          ├── Edit reviewed_naver_description
          ├── Edit reviewed_price
          ├── Edit reviewed_options_json
          └── Edit reviewed_tags
          ↓
[3] Save Draft
          ├── POST /api/phase4/review/{id}/save
          └── review_status: draft
          ↓
[4] Image Review
          ├── Set primary image
          ├── Reorder images
          ├── Exclude images
          └── Mark warnings
          ↓
[5] Approve for Export
          ├── POST /api/phase4/review/{id}/approve-export
          ├── review_status: approved_for_export
          └── Enable export buttons
          ↓
[6] Export to CSV
          ├── GET /api/phase4/export/naver?review_ids=...
          ├── GET /api/phase4/export/coupang?review_ids=...
          └── Download CSV (using reviewed_* fields)
          ↓
[7] Manual Upload to Marketplace
          └── Operator uploads CSV to Naver/Coupang manually

(Optional)
[8] Enable API Upload (Manual)
          ├── POST /api/phase4/review/{id}/enable-upload
          └── review_status: approved_for_upload
          ↓
[9] API Upload (Manual Trigger Only)
          ├── POST /api/phase4/upload/naver/{id}
          └── POST /api/phase4/upload/coupang/{id}
```

---

## 🗄️ DB Schema Changes (Migration 004)

### 1. approval_queue 테이블 확장

```sql
-- Generated fields (AI 자동 생성, READ-ONLY)
ALTER TABLE approval_queue ADD COLUMN generated_naver_title TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_naver_description TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_naver_tags TEXT;

ALTER TABLE approval_queue ADD COLUMN generated_coupang_title TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_coupang_description TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_coupang_tags TEXT;

ALTER TABLE approval_queue ADD COLUMN generated_options_json TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_price REAL;
ALTER TABLE approval_queue ADD COLUMN generated_category TEXT;

-- Reviewed fields (운영자 수정 가능)
ALTER TABLE approval_queue ADD COLUMN reviewed_naver_title TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_naver_description TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_naver_tags TEXT;

ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_title TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_description TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_coupang_tags TEXT;

ALTER TABLE approval_queue ADD COLUMN reviewed_options_json TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_price REAL;
ALTER TABLE approval_queue ADD COLUMN reviewed_category TEXT;

-- Review metadata
ALTER TABLE approval_queue ADD COLUMN review_status TEXT DEFAULT 'draft';
ALTER TABLE approval_queue ADD COLUMN reviewed_at TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_by TEXT;
ALTER TABLE approval_queue ADD COLUMN review_notes TEXT;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_approval_review_status ON approval_queue(review_status);
```

### 2. image_review 테이블 (신규)

```sql
CREATE TABLE IF NOT EXISTS image_review (
    image_review_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    -- Original images
    original_images_json TEXT NOT NULL,

    -- Reviewed images (with metadata)
    reviewed_images_json TEXT NOT NULL,

    primary_image_index INTEGER DEFAULT 0,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_image_review_review ON image_review(review_id);
```

### 3. review_history 테이블 (신규)

```sql
CREATE TABLE IF NOT EXISTS review_history (
    history_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    -- Snapshot of reviewed_* fields before change
    previous_state_json TEXT NOT NULL,

    -- Changed fields
    changed_fields TEXT NOT NULL,  -- JSON array

    -- Actor
    changed_by TEXT NOT NULL,
    change_reason TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_history_review ON review_history(review_id);
CREATE INDEX IF NOT EXISTS idx_review_history_created ON review_history(created_at DESC);
```

---

## 📊 Implementation Plan

### Phase 4.1: DB Schema & Data Migration (Day 1)
- [ ] `migrations/004_phase4_schema.sql` 작성
- [ ] `image_review`, `review_history` 테이블 생성
- [ ] `approval_queue` 확장 (generated_*, reviewed_* 필드)
- [ ] Migration 실행 및 검증

### Phase 4.2: Review Console Backend API (Day 2-3)
- [ ] `review_console_api.py` 구현
- [ ] GET `/api/phase4/review/{review_id}` - 상세 조회
- [ ] POST `/api/phase4/review/{review_id}/save` - Draft 저장
- [ ] POST `/api/phase4/review/{review_id}/approve-export` - Export 승인
- [ ] POST `/api/phase4/review/{review_id}/approve-upload` - Upload 승인
- [ ] POST `/api/phase4/review/{review_id}/reject` - 거부
- [ ] POST `/api/phase4/review/{review_id}/hold` - 보류

### Phase 4.3: Image Review Panel (Day 3)
- [ ] `image_review_manager.py` 구현
- [ ] POST `/api/phase4/image/{review_id}/set-primary` - 대표 이미지 설정
- [ ] POST `/api/phase4/image/{review_id}/reorder` - 순서 변경
- [ ] POST `/api/phase4/image/{review_id}/exclude` - 이미지 제외
- [ ] POST `/api/phase4/image/{review_id}/warnings` - 경고 추가

### Phase 4.4: Export-First (Day 4)
- [ ] `export_service.py` 확장
- [ ] GET `/api/phase4/export/naver` - Naver CSV (reviewed_* 사용)
- [ ] GET `/api/phase4/export/coupang` - Coupang CSV (reviewed_* 사용)
- [ ] Batch export 지원 (review_ids parameter)

### Phase 4.5: Review Console UI (Day 5-6)
- [ ] HTML/JS UI 구현
- [ ] Review detail page
- [ ] Edit modal for reviewed_* fields
- [ ] Image review panel UI
- [ ] Export buttons
- [ ] Workflow state visualization

### Phase 4.6: Testing & Documentation (Day 6-7)
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] End-to-End 시나리오 테스트
- [ ] 문서화

---

## ✅ 원칙 준수

### 1. Human-in-the-Loop ✅
- 모든 자동 생성 결과는 운영자 검수 필수
- reviewed_* 필드만 export/upload에 사용
- review_status로 검수 진행 상태 추적

### 2. Fail-Safe ✅
- Auto upload OFF (기본값)
- Export-first (CSV 다운로드 우선)
- API upload는 수동 승인 필요 (approved_for_upload)

### 3. Editable ✅
- 모든 필드 수정 가능 (reviewed_* fields)
- 이미지 순서 변경, 제외 가능
- Draft 저장 기능

### 4. Auditable ✅
- review_history 테이블 (모든 수정 이력)
- reviewed_at, reviewed_by 기록
- review_notes 필수

### 5. Data Separation ✅
- generated_* vs reviewed_* 명확히 분리
- generated_* 는 READ-ONLY (원본 보존)
- reviewed_* 만 export/upload에 사용

---

## 📈 Success Metrics

### Operational Metrics
- Review throughput: 시간당 검수 가능 상품 수
- Review completion rate: 검수 완료율 (approved / total)
- Edit rate: 수정 비율 (edited / total)

### Quality Metrics
- Export error rate: Export 후 오류 발생률 < 5%
- Rejection rate: 거부율 < 10%
- Hold rate: 보류율 < 15%

---

## 🎯 Phase 4 Goals

| 목표 | 달성 기준 |
|------|----------|
| Review Console UI | 상품 상세 검수 화면 구현 |
| Editable Fields | generated_* vs reviewed_* 분리 |
| Image Review | 이미지 관리 패널 구현 |
| Review Workflow | 6가지 상태 전이 지원 |
| Export-First | CSV export 우선, API upload 수동 |

---

**작성일**: 2026-03-31
**작성자**: Claude (PM Agent System)
**문서 버전**: 1.0
