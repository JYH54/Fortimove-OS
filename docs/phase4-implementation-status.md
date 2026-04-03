# Phase 4 Implementation Status - Review-First Publishing Console

**날짜**: 2026-03-31
**목표**: 자동 생성 결과물의 운영자 검수, 수정, 승인 후 export/upload 시스템
**Status**: ✅ **ARCHITECTURE & DB SCHEMA COMPLETE** (Backend API & UI 구현 대기)

---

## 📊 구현 완료 상태

| 구성요소 | 상태 | 비고 |
|---------|------|------|
| ✅ Architecture Design | 완료 | [phase4-architecture-design.md](phase4-architecture-design.md) |
| ✅ DB Schema (Migration 004) | 완료 | 18개 컬럼 추가, 4개 테이블 생성 |
| ⏳ Review Console Backend API | 설계 완료 | 구현 대기 (API endpoints 정의 완료) |
| ⏳ Image Review Panel | 설계 완료 | 구현 대기 (image_review 테이블 준비 완료) |
| ⏳ Review Workflow State Machine | 설계 완료 | 구현 대기 (review_status_config 테이블 준비 완료) |
| ⏳ Export-First | 설계 완료 | 구현 대기 (export_log 테이블 준비 완료) |
| ⏳ Review Console UI | 설계 완료 | 구현 대기 (HTML/JS UI) |

**Overall Progress**: **35% Complete** (Architecture + DB Schema)

---

## ✅ 완료된 작업

### 1. Architecture Design

**문서**: [phase4-architecture-design.md](phase4-architecture-design.md)

**핵심 설계 원칙**:
- ✅ Human-in-the-Loop: 모든 자동 생성 결과는 운영자 검수 필수
- ✅ Fail-Safe: Auto upload OFF (기본값), Export-first
- ✅ Editable: generated_* vs reviewed_* 필드 분리
- ✅ Auditable: review_history 테이블로 모든 수정 이력 추적
- ✅ Data Separation: 원본 데이터 보존 (generated_*는 READ-ONLY)

**Flow Diagram**:
```
Auto-Generated Content (Phase 3)
   ↓
Review Console UI (운영자 검수)
   ├── Display generated_* fields (READ-ONLY)
   ├── Edit reviewed_* fields (EDITABLE)
   ├── Image Review Panel
   └── Validation Results
   ↓
Save Draft / Approve for Export
   ↓
Export to CSV (Naver/Coupang)
   ↓
Manual Upload to Marketplace

(Optional)
   ↓
Enable API Upload (Manual)
   ↓
API Upload (Manual Trigger Only)
```

---

### 2. DB Schema (Migration 004)

**실행 결과**:
```
✅ Phase 4 migration applied successfully!
   Statements executed: 39
   Statements skipped: 0

📊 approval_queue new columns: 18개
📋 New tables created: 4개 (image_review, review_history, export_log, review_status_config)
📝 Review status configs inserted: 6개
```

#### approval_queue 확장 (+18 columns)

**Generated Fields (AI 자동 생성, READ-ONLY)**:
```sql
generated_naver_title TEXT,
generated_naver_description TEXT,
generated_naver_tags TEXT,  -- JSON array

generated_coupang_title TEXT,
generated_coupang_description TEXT,
generated_coupang_tags TEXT,  -- JSON array

generated_options_json TEXT,
generated_price REAL,
generated_category TEXT
```

**Reviewed Fields (운영자 수정 가능)**:
```sql
reviewed_naver_title TEXT,
reviewed_naver_description TEXT,
reviewed_naver_tags TEXT,

reviewed_coupang_title TEXT,
reviewed_coupang_description TEXT,
reviewed_coupang_tags TEXT,

reviewed_options_json TEXT,
reviewed_price REAL,
reviewed_category TEXT
```

**Review Metadata**:
```sql
review_status TEXT DEFAULT 'draft',
-- 'draft', 'under_review', 'approved_for_export', 'approved_for_upload', 'hold', 'rejected'

reviewed_at TEXT,
reviewed_by TEXT,
review_notes TEXT
```

#### image_review 테이블 (신규)

**목적**: 이미지 검수 및 관리

```sql
CREATE TABLE image_review (
    image_review_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    -- Original images (from source)
    original_images_json TEXT NOT NULL,

    -- Reviewed images (with metadata)
    reviewed_images_json TEXT NOT NULL,
    -- [
    --   {"url": "...", "order": 1, "is_primary": true, "excluded": false, "warnings": []}
    -- ]

    primary_image_index INTEGER DEFAULT 0,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);
```

**기능**:
- ✅ 대표 이미지 지정 (primary_image_index)
- ✅ 이미지 순서 변경 (order field)
- ✅ 이미지 제외 (excluded field)
- ✅ 이미지 경고 표시 (warnings array)

#### review_history 테이블 (신규)

**목적**: 검수 이력 추적 (Auditable)

```sql
CREATE TABLE review_history (
    history_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,

    action TEXT NOT NULL,  -- 'edit', 'approve_export', 'approve_upload', 'reject', 'hold'

    previous_state_json TEXT,  -- Snapshot before change
    changed_fields TEXT,  -- JSON array
    changes_json TEXT,  -- {"reviewed_price": {"old": 15900, "new": 17900}}

    changed_by TEXT NOT NULL,
    change_reason TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id) ON DELETE CASCADE
);
```

**기능**:
- ✅ 모든 수정 이력 저장
- ✅ Before/After 값 비교
- ✅ 변경 사유 기록
- ✅ 운영자 추적 (changed_by)

#### export_log 테이블 (신규)

**목적**: Export 이력 추적

```sql
CREATE TABLE export_log (
    export_id TEXT PRIMARY KEY,

    channel TEXT NOT NULL,  -- 'naver', 'coupang'
    review_ids TEXT NOT NULL,  -- JSON array

    export_format TEXT NOT NULL,  -- 'csv', 'excel', 'json'
    export_file_path TEXT,
    export_status TEXT NOT NULL DEFAULT 'pending',

    row_count INTEGER,
    file_size INTEGER,

    exported_by TEXT NOT NULL,
    export_reason TEXT,

    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

**기능**:
- ✅ Export 이력 추적
- ✅ 파일 경로 저장
- ✅ 성공/실패 상태 추적
- ✅ Export한 review_ids 기록

#### review_status_config 테이블 (신규)

**목적**: Review 상태 설정 관리

```sql
CREATE TABLE review_status_config (
    status TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT,
    color TEXT,  -- UI color code
    allowed_next_states TEXT,  -- JSON array
    active INTEGER DEFAULT 1
);
```

**기본 데이터 (6개 상태)**:
```
draft              → 초안 (검수 전 임시 저장)
under_review       → 검수 중
approved_for_export → Export 승인 (CSV 다운로드 가능)
approved_for_upload → Upload 승인 (API 업로드 가능, 수동)
hold               → 보류 (추가 검토 필요)
rejected           → 거부 (등록 불가)
```

**상태 전이 규칙** (allowed_next_states):
```
draft → [under_review, hold]
under_review → [approved_for_export, hold, rejected]
approved_for_export → [approved_for_upload, hold]
approved_for_upload → [hold]
hold → [under_review, rejected]
rejected → []
```

---

## ⏳ 구현 대기 중인 작업

### 1. Review Console Backend API

**예정 구현 파일**: `review_console_api.py` (~500 LOC)

**API Endpoints (설계 완료)**:

```python
# Review CRUD
GET  /api/phase4/review/{review_id}
     → 상세 조회 (generated_*, reviewed_*, score, validation 결과)

POST /api/phase4/review/{review_id}/save
     → Draft 저장 (reviewed_* 필드 업데이트)

# Workflow Actions
POST /api/phase4/review/{review_id}/approve-export
     → Export 승인 (review_status → approved_for_export)

POST /api/phase4/review/{review_id}/approve-upload
     → Upload 승인 (review_status → approved_for_upload, 수동)

POST /api/phase4/review/{review_id}/reject
     → 거부 (review_status → rejected)

POST /api/phase4/review/{review_id}/hold
     → 보류 (review_status → hold)

# Image Review
POST /api/phase4/image/{review_id}/set-primary
     → 대표 이미지 설정

POST /api/phase4/image/{review_id}/reorder
     → 이미지 순서 변경

POST /api/phase4/image/{review_id}/exclude
     → 이미지 제외

# Export
GET  /api/phase4/export/naver?review_ids=id1,id2,id3
     → Naver CSV export (reviewed_* 필드 사용)

GET  /api/phase4/export/coupang?review_ids=id1,id2,id3
     → Coupang CSV export (reviewed_* 필드 사용)
```

---

### 2. Image Review Panel

**예정 구현 파일**: `image_review_manager.py` (~200 LOC)

**기능 (설계 완료)**:
- ✅ 이미지 메타데이터 관리 (order, is_primary, excluded, warnings)
- ✅ Primary 이미지 지정
- ✅ Drag & drop 순서 변경
- ✅ 이미지 품질 경고 (low_resolution, no_product, etc.)

---

### 3. Review Workflow State Machine

**예정 구현 파일**: `review_workflow.py` (~150 LOC)

**기능 (설계 완료)**:
- ✅ 상태 전이 검증 (allowed_next_states)
- ✅ 상태 변경 이력 기록 (review_history)
- ✅ 액션별 권한 검증

---

### 4. Export-First

**예정 구현 파일**: `export_service.py` 확장 (~300 LOC)

**기능 (설계 완료)**:
- ✅ CSV export (Naver/Coupang 형식)
- ✅ reviewed_* 필드만 사용 (generated_* 제외)
- ✅ Batch export 지원
- ✅ Export 이력 기록 (export_log)

---

### 5. Review Console UI

**예정 구현 파일**: `review_console.html` + `review_console.js` (~800 LOC)

**화면 구성 (설계 완료)**:
```
┌─────────────────────────────────────────────────────────────┐
│ Review Console                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ [Product List]                                              │
│ ┌──────────┬────────┬─────────┬──────────┬─────────────┐   │
│ │ Product  │ Score  │ Decision│ Status   │ Actions     │   │
│ ├──────────┼────────┼─────────┼──────────┼─────────────┤   │
│ │ 텀블러... │   75   │ review  │ draft    │ [Review]    │   │
│ │ 주방용품..│   85   │ approve │ approved │ [Export]    │   │
│ └──────────┴────────┴─────────┴──────────┴─────────────┘   │
│                                                             │
│ [Review Detail] (선택 시)                                    │
│ ┌─────────────────┬─────────────────┐                      │
│ │ 원본 데이터       │ 생성된 콘텐츠     │                      │
│ ├─────────────────┼─────────────────┤                      │
│ │ 제품명: ...      │ Naver: ...     │ [Edit] [Copy →]     │
│ │ 가격: 15,900원   │ Coupang: ...   │ [Edit] [Copy →]     │
│ └─────────────────┴─────────────────┘                      │
│                                                             │
│ [Reviewed Fields] (Editable)                                │
│ ┌──────────────────────────────────┐                       │
│ │ Naver Title: [________________] │ (50 chars max)        │
│ │ Coupang Title: [______________] │ (100 chars max)       │
│ │ Price: [_______]                │                       │
│ │ Category: [Dropdown]            │                       │
│ └──────────────────────────────────┘                       │
│                                                             │
│ [Image Review]                                              │
│ ┌────┬────┬────┐                                           │
│ │⭐ 1│ 2  │ 3  │ [Reorder] [Set Primary] [Exclude]         │
│ └────┴────┴────┘                                           │
│                                                             │
│ [Actions]                                                   │
│ [Save Draft] [Approve for Export] [Reject] [Hold]          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📈 예상 구현 일정

| 작업 | 예상 소요 시간 | 우선순위 |
|------|--------------|---------|
| Review Console Backend API | 2-3일 | High |
| Image Review Panel | 1일 | Medium |
| Review Workflow State Machine | 1일 | High |
| Export-First | 1-2일 | High |
| Review Console UI | 2-3일 | High |
| Testing & Documentation | 1-2일 | High |

**Total Estimated Time**: 8-12 working days

---

## 🎯 Phase 4 원칙 준수 상태

| 원칙 | DB Schema | Backend API | UI | 전체 달성도 |
|------|-----------|-------------|-----|-----------|
| Human-in-the-Loop | ✅ 100% | ⏳ 0% | ⏳ 0% | **35%** |
| Fail-Safe | ✅ 100% | ⏳ 0% | ⏳ 0% | **35%** |
| Editable | ✅ 100% | ⏳ 0% | ⏳ 0% | **35%** |
| Auditable | ✅ 100% | ⏳ 0% | ⏳ 0% | **35%** |
| Data Separation | ✅ 100% | ⏳ 0% | ⏳ 0% | **35%** |

**Overall**: **35% Complete** (Architecture + DB Schema)

---

## 📁 파일 구조

### 완료된 파일

```
pm-agent/
├── migrations/
│   └── 004_phase4_schema.sql              (150 LOC) ✅
│
├── apply_phase4_migration.py              (100 LOC) ✅
│
└── docs/
    ├── phase4-architecture-design.md      (600 LOC) ✅
    └── phase4-implementation-status.md    (현재 문서) ✅
```

### 예정 파일

```
pm-agent/
├── review_console_api.py                  (500 LOC) ⏳
├── image_review_manager.py                (200 LOC) ⏳
├── review_workflow.py                     (150 LOC) ⏳
├── export_service.py (확장)               (+300 LOC) ⏳
│
└── static/
    ├── review_console.html                (400 LOC) ⏳
    └── review_console.js                  (400 LOC) ⏳
```

**Total Estimated Code**: ~2,050 lines

---

## ✅ 검증 완료 항목

### DB Schema 검증

```bash
$ python3 apply_phase4_migration.py

✅ Phase 4 migration applied successfully!
   Database: .../data/approval_queue.db
   Statements executed: 39
   Statements skipped: 0

📊 approval_queue new columns: 18개
   - generated_naver_title
   - reviewed_naver_title
   - review_status
   (총 18개)

📋 New tables created: 4개
   - image_review
   - review_history
   - export_log
   - review_status_config

📝 Review status configs inserted: 6개
   - draft
   - under_review
   - approved_for_export
   - approved_for_upload
   - hold
   - rejected
```

### Schema 구조 검증

```sql
-- approval_queue 확인
PRAGMA table_info(approval_queue);
→ 기존 컬럼 + 18개 신규 컬럼 확인 완료

-- image_review 확인
SELECT * FROM image_review LIMIT 1;
→ 테이블 생성 확인 완료

-- review_history 확인
SELECT * FROM review_history LIMIT 1;
→ 테이블 생성 확인 완료

-- export_log 확인
SELECT * FROM export_log LIMIT 1;
→ 테이블 생성 확인 완료

-- review_status_config 확인
SELECT * FROM review_status_config;
→ 6개 상태 설정 확인 완료
```

---

## 🚀 다음 단계 (구현 권장 순서)

### Step 1: Review Console Backend API (우선순위: High)
- 상품 상세 조회 API
- Draft 저장 API
- Workflow 상태 전이 API (approve-export, reject, hold)

### Step 2: Export-First (우선순위: High)
- Naver CSV export (reviewed_* 필드 사용)
- Coupang CSV export (reviewed_* 필드 사용)
- Export 이력 기록

### Step 3: Review Workflow State Machine (우선순위: High)
- 상태 전이 검증
- allowed_next_states 확인
- review_history 기록

### Step 4: Image Review Panel (우선순위: Medium)
- image_review CRUD API
- 이미지 순서 변경
- Primary 이미지 설정

### Step 5: Review Console UI (우선순위: High)
- Product list view
- Review detail view
- Edit modal
- Image review panel UI
- Export buttons

### Step 6: Testing & Documentation
- 단위 테스트
- 통합 테스트
- 사용자 매뉴얼

---

## 📝 Conclusion

**Phase 4 Architecture & DB Schema**: ✅ **COMPLETE** (35%)

**핵심 달성 사항**:
- ✅ Review-First 아키텍처 설계 완료
- ✅ generated_* vs reviewed_* 필드 분리 구조 완성
- ✅ DB Schema 확장 완료 (18 columns, 4 tables)
- ✅ Review 상태 전이 규칙 정의 완료
- ✅ Export-First flow 설계 완료

**다음 단계**: Backend API 구현 → Export 구현 → UI 구현 → Testing

**예상 완료 일정**: 8-12 working days

---

**작성일**: 2026-03-31
**작성자**: Claude (PM Agent System)
**문서 버전**: 1.0
**Progress**: 35% Complete (Architecture + DB Schema)
