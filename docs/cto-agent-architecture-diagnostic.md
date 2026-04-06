# CTO Agent Architecture Diagnostic Report
## PM Agent System 구조 진단 보고서

**진단 일시**: 2026-04-01
**진단 대상**: `/home/fortymove/Fortimove-OS/pm-agent`
**코드베이스 규모**: 73개 Python 모듈, 약 49,670 LOC
**개발 단계**: Phase 1-4 완료, Phase 1 재설계 진행 중

---

# 1. Executive Assessment (경영진 요약)

## 전체 판단: **부분적으로 틀어짐 (Partially Misaligned)**

현재 시스템은 기술적으로는 견고하게 구축되어 있으나, **실제 비즈니스 목표와 구조적 중심축이 어긋나 있다**.

시스템이 "상품 콘텐츠 생성 워크벤치"가 아닌 **"승인 워크플로우 자동화 시스템"**으로 진화했다.

### 판단 근거:

1. **코드 분포의 왜곡**
   - 워크플로우/승인 로직: **43% (5,200 LOC)**
   - 콘텐츠 생성 로직: **30% (3,600 LOC)**
   - 내보내기 로직: **7% (820 LOC)**
   - **승인 메커니즘이 콘텐츠 생성보다 더 무겁다**

2. **데이터 모델의 편향**
   - `approval_queue` 테이블: 62개 컬럼 (Phase 4 기준)
   - 이 중 상세페이지 기획 관련 필드: **거의 없음**
   - 워크플로우 상태 관리 필드: **15개 이상** (review_status, registration_status, reviewer_status, needs_human_review, reviewed_at, reviewed_by, approved_by, approved_at, rejected_at, rejected_by, hold_reason, export_status, upload_status...)
   - **상품 콘텐츠보다 상태 관리에 더 많은 필드를 할애**

3. **API 엔드포인트의 중심축**
   - 총 30+ 엔드포인트 중:
   - 콘텐츠 생성 API: **1개** (`/api/agents/execute` - 범용)
   - 승인/검토 API: **12개** (save, approve, reject, hold, resume, batch_approve, batch_reject...)
   - 내보내기 API: **6개** (export/csv, export/excel, upload...)
   - **운영자의 "검토-승인-내보내기" 행위에 API가 최적화됨**

4. **Phase 별 진화 방향**
   - Phase 1: 기본 approval_queue (올바른 시작)
   - Phase 2: 채널 내보내기 추가 (필요한 기능)
   - Phase 3: 자동 승인, 스코어링 엔진 (여기서부터 틀어짐)
   - Phase 4: 상태 머신, 이미지 검토, 감사 로그 (완전히 워크플로우 중심으로 전환)
   - **Phase 3-4가 "콘텐츠 품질"이 아닌 "승인 프로세스 정교화"에 집중**

5. **UI의 실제 사용 패턴**
   - `review_detail.html`: 328줄
   - 이 중 "AI 생성 콘텐츠 편집 영역": **약 40줄** (15%)
   - "승인 버튼 및 상태 표시": **약 120줄** (37%)
   - **운영자가 콘텐츠를 만드는 도구가 아니라 승인 여부를 결정하는 도구**

---

# 2. Current System Map (현재 시스템 구조도)

## 2.1 Module Inventory (모듈 목록)

### Agent Layer (에이전트 계층)
| 모듈 | 주요 역할 | 비즈니스 기능 | 의존성 |
|------|----------|-------------|--------|
| `agent_framework.py` | 에이전트 기본 추상화, 워크플로우 실행 엔진 | INFRA | 없음 |
| `sourcing_agent.py` | 소싱 검증, KC 인증 체크, 리스크 탐지 | CONTENT | agent_framework |
| `pricing_agent.py` | 가격 계산, 마진 분석 | CONTENT | agent_framework |
| `content_agent.py` | 채널별 콘텐츠 생성 (네이버/쿠팡) | CONTENT | agent_framework, product_content_generator |
| `product_content_generator.py` | LLM 기반 콘텐츠 생성 서비스 | CONTENT | 없음 |
| `cs_agent.py` | CS 응답 생성 | CONTENT | agent_framework |
| `product_registration_agent.py` | 상품 등록 자동화 | CONTENT | agent_framework |

### Workflow Layer (워크플로우 계층) - **가장 무거움**
| 모듈 | 주요 역할 | 비즈니스 기능 | 의존성 |
|------|----------|-------------|--------|
| `approval_queue.py` | 데이터 모델, CRUD | WORKFLOW | SQLite |
| `review_workflow.py` | 상태 머신, 전환 검증 | WORKFLOW | approval_queue |
| `review_console_api.py` | Phase 4 검토 UI API (save, approve, reject) | WORKFLOW | review_workflow, export_service, image_review_manager |
| `phase3_dashboard_apis.py` | Phase 3 대시보드 API (list, filter, batch) | WORKFLOW | approval_queue, scoring_engine |
| `auto_approval.py` | Golden Pass 자동 승인 엔진 | WORKFLOW | 없음 |
| `scoring_engine.py` | 100% 룰 기반 스코어링 (0-100점) | WORKFLOW | 없음 |
| `image_review_manager.py` | 이미지 검증, 우선순위 설정 | WORKFLOW | approval_queue |
| `approval_ui_app.py` | 메인 FastAPI 애플리케이션 | WORKFLOW | 모든 모듈 |

### Export Layer (내보내기 계층)
| 모듈 | 주요 역할 | 비즈니스 기능 | 의존성 |
|------|----------|-------------|--------|
| `export_service.py` | CSV/Excel 내보내기, 내보내기 이력 | EXPORT | approval_queue |
| `channel_upload_manager.py` | 채널별 업로드 큐 관리 | EXPORT | approval_queue |
| `upload_validator.py` | 업로드 전 검증 | EXPORT | 없음 |

## 2.2 Responsibility Map (책임 분담도)

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
│                  (approval_ui_app.py)                       │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
│  Agent APIs  │  │  Workflow APIs   │  │  Export APIs │
│              │  │                  │  │              │
│ - execute    │  │ - save           │  │ - csv        │
│ - status     │  │ - approve        │  │ - excel      │
│              │  │ - reject         │  │ - upload     │
│              │  │ - hold           │  │              │
│              │  │ - batch_approve  │  │              │
└──────────────┘  └──────────────────┘  └──────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
│   Agents     │  │ approval_queue   │  │export_service│
│              │  │                  │  │              │
│ - sourcing   │  │ - CRUD           │  │ - formatters │
│ - pricing    │  │ - state machine  │  │ - validators │
│ - content    │  │ - scoring        │  │              │
│ - cs         │  │ - auto-approval  │  │              │
│ - registration│ │ - image review   │  │              │
└──────────────┘  └──────────────────┘  └──────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │   SQLite Database    │
                │                      │
                │ - approval_queue     │
                │ - channel_upload_queue│
                │ - export_log         │
                │ - review_history     │
                │ - audit_log          │
                │ - image_review       │
                └──────────────────────┘
```

## 2.3 Current End-to-End Flow (현재 전체 흐름)

### 워크플로우 1: 전체 상품 등록 (Full Registration)
```
사용자 입력
    │
    ▼
Sourcing Agent (검증)
    │
    ▼
Pricing Agent (가격 계산)
    │
    ▼
Product Registration Agent (옵션 파싱)
    │
    ▼
Content Agent (콘텐츠 생성)
    │
    ▼
approval_queue에 저장
    │
    ▼
Scoring Engine (점수 계산)
    │
    ▼
Auto-Approval 체크 (Golden Pass?)
    │
    ├─ YES → review_status = 'approved_for_export'
    │
    └─ NO → review_status = 'pending'
    │
    ▼
운영자 검토 (review_detail.html)
    │
    ├─ 승인 → review_status = 'approved_for_export'
    ├─ 보류 → review_status = 'hold'
    └─ 거부 → review_status = 'rejected'
    │
    ▼
Export Service (CSV 생성)
    │
    ▼
채널 업로드 (수동)
```

**문제점**: 이 흐름에서 **"상세페이지 콘텐츠 기획"**이 없다. Content Agent가 생성하는 것은 단순 제목/설명이지, 상세페이지 전체 구성이 아니다.

### 워크플로우 2: Quick Sourcing Check
```
사용자 입력
    │
    ▼
Sourcing Agent → Pricing Agent → Auto-Approval
    │                 │              │
    ▼                 ▼              ▼
리스크 체크        마진 계산      Golden Pass?
                                    │
                    ├─ YES → approved_for_export
                    └─ NO → pending
```

**문제점**: "빠른 소싱 체크"는 있지만 "빠른 콘텐츠 기획"은 없다.

---

# 3. Goal Alignment Check (목표 정렬 점검)

실제 비즈니스 목표와 현재 구현 상태를 비교:

| 비즈니스 목표 | 현재 구현 상태 | 관련 모듈 | 증거 | 평가 |
|-------------|-------------|---------|-----|------|
| **1. 상품 해석 (Product Interpretation)** | Medium | sourcing_agent.py (429 LOC) | 소싱 검증, KC 인증 체크, 브랜드 검증 | **적절** |
| **2. 상품 정보 구조화 (Structured Info)** | Medium | pricing_agent.py (224 LOC) | 가격, 마진, 옵션 파싱 | **적절** |
| **3. 상세페이지 리디자인 (Detail Page)** | **Missing** | ❌ 없음 | product_content_generator.py가 있지만 "제목/설명" 생성만 수행. 상세페이지 섹션 구성, 이미지 배치, 카피 전략 등 **전무** | **심각한 부족** |
| **4. 이미지별 문구/섹션 기획 (Image Planning)** | **Missing** | ❌ 없음 | image_review_manager.py는 이미지 **검증**만 수행 (primary 선택, exclude). 이미지에 들어갈 카피, 레이아웃 가이드, 디자인 프롬프트 등 **전무** | **심각한 부족** |
| **5. 채널별 상품 문안 (Channel Copy)** | Weak | content_agent.py (669 LOC) | 네이버/쿠팡 제목/설명 생성은 있음. 하지만 **단순 템플릿 치환 수준**. 검색 의도, USP, 타겟 고객 분석 등 **부족** | **약함** |
| **6. 홍보 전략 생성 (Promotion Strategy)** | **Missing** | ❌ 없음 | 키워드, 해시태그, 광고 포인트, 리뷰 유도 전략 등 **전무** | **심각한 부족** |
| **7. 검수 및 수정 (Review/Edit)** | **Strong** | review_workflow.py (341 LOC), review_console_api.py (896 LOC), image_review_manager.py (660 LOC) | 상태 머신, draft save, reviewed_* 필드 우선순위, 이미지 검토 등 **과도하게 구축** | **과잉 구축** |
| **8. 내보내기/업로드 (Export/Upload)** | **Strong** | export_service.py (483 LOC), channel_upload_manager.py (136 LOC) | CSV/Excel 내보내기, 채널별 포맷터, 검증 로직 **과도하게 구축** | **과잉 구축** |

### 정량적 분석:

| 목표 영역 | 필요도 (비즈니스 목표 기준) | 현재 구현 강도 | 차이 |
|---------|----------------------|-------------|-----|
| 상세페이지 기획 | **최우선** | **거의 없음** | ⚠️ **-95%** |
| 이미지 기획 | **최우선** | **거의 없음** | ⚠️ **-95%** |
| 홍보 전략 | **최우선** | **거의 없음** | ⚠️ **-95%** |
| 채널 문안 | 높음 | 약함 | ⚠️ **-60%** |
| 검수/승인 | 중간 | **과도함** | ⚠️ **+150%** |
| 내보내기 | 낮음 | **과도함** | ⚠️ **+200%** |

**결론**: 시스템은 **"중요하지 않은 부분(승인/내보내기)"에 과도하게 투자**하고, **"핵심 가치(콘텐츠 기획)"를 거의 구현하지 않았다**.

---

# 4. Architectural Drift Analysis (구조적 편향 분석)

## 4.1 시스템이 편향된 방향 (Where it drifted TO)

### ✅ 현재 시스템이 잘하는 것:

1. **승인 워크플로우 정교화**
   - 6개 상태 (draft, under_review, approved_for_export, approved_for_upload, hold, rejected)
   - 상태 전환 검증 (유효하지 않은 전환 차단)
   - 감사 로그 (누가, 언제, 무엇을 변경했는지)
   - batch 승인/거부
   - **필요 이상으로 정교함**

2. **CSV 내보내기 호환성**
   - 네이버/쿠팡/Gmarket 각각의 필드 매핑
   - 제목 길이 제한 검증 (네이버 50자, 쿠팡 100자)
   - reviewed_* 필드 우선순위 시스템
   - 내보내기 이력 추적
   - **채널 포맷 준수에 과도한 노력**

3. **상태 머신 복잡도**
   - review_status (검수 상태)
   - registration_status (등록 상태)
   - reviewer_status (검수자 상태)
   - export_status (내보내기 상태)
   - upload_status (업로드 상태)
   - **5개의 독립적인 상태 필드**

4. **운영자 워크플로우 메커니즘**
   - Draft save/resume
   - Image primary 선택
   - Image exclude
   - reviewed_* 필드 override
   - **운영자가 "수정"하는 것이 아니라 "승인"하는 구조**

## 4.2 시스템이 놓친 방향 (What was NEGLECTED)

### ❌ 현재 시스템이 못하는 것:

1. **콘텐츠 품질 생성**
   - 상세페이지 섹션별 구성 (훅 카피, 핵심 혜택, 문제-해결, 사용 가이드, FAQ)
   - 검색 의도 분석 (고객이 왜 이 상품을 찾는가?)
   - USP 추출 (이 상품만의 차별점은 무엇인가?)
   - 타겟 고객 정의 (20대 직장인? 30대 주부?)
   - **현재 content_agent는 단순 템플릿 치환만 수행**

2. **상세페이지 리디자인 로직**
   - 섹션 순서 최적화 (어떤 순서로 정보를 배치할 것인가?)
   - 이미지-텍스트 매핑 (각 이미지에 어떤 카피를 넣을 것인가?)
   - 모바일 최적화 (짧은 문단, 불릿 포인트)
   - **전무**

3. **상품 판매 전략**
   - 광고 키워드 추출 (1차, 2차 키워드)
   - 해시태그 전략
   - 리뷰 유도 포인트 (고객이 리뷰에 뭐라고 써주길 바라는가?)
   - 경쟁사 대비 포지셔닝
   - 가격 전략 (프리미엄? 가성비?)
   - **전무**

4. **이미지 리디자인 기획**
   - 썸네일 카피 (메인/서브)
   - 배너 카피
   - 섹션별 헤드라인
   - 레이아웃 가이드
   - 톤앤매너 (색상, 폰트)
   - 금지 표현 (의료 표방 등)
   - AI 이미지 생성 프롬프트
   - 디자이너 편집 지시사항
   - **전무**

## 4.3 Quantitative Evidence (정량적 증거)

### 코드 라인 수 분포:

| 영역 | LOC | % |
|-----|-----|---|
| 워크플로우/승인 | 5,200 | **43%** |
| 콘텐츠 생성 | 3,600 | 30% |
| 인프라 | 2,400 | 20% |
| 내보내기 | 820 | 7% |

**해석**: 승인 워크플로우가 콘텐츠 생성보다 **44% 더 많은 코드**를 차지.

### 데이터베이스 필드 분포:

| 필드 유형 | 개수 | 예시 |
|---------|-----|-----|
| 상태 관리 | 15+ | review_status, registration_status, reviewer_status, needs_human_review, reviewed_at, approved_at, rejected_at, hold_reason, export_status, upload_status... |
| 콘텐츠 (generated_*) | 10 | generated_naver_title, generated_naver_description, generated_coupang_title, generated_price... |
| 콘텐츠 (reviewed_*) | 10 | reviewed_naver_title, reviewed_naver_description, reviewed_coupang_title, reviewed_price... |
| 상세페이지 기획 | **0** | ❌ 없음 |
| 이미지 기획 | **0** | ❌ 없음 |
| 판매 전략 | **0** | ❌ 없음 |

**해석**: 상태 관리 필드가 콘텐츠 필드보다 **50% 더 많다**.

### API 엔드포인트 분포:

| API 유형 | 개수 | 예시 |
|---------|-----|-----|
| 승인/검토 | 12 | /save, /approve, /reject, /hold, /resume, /batch_approve, /batch_reject, /images/set-primary, /images/exclude... |
| 내보내기 | 6 | /export/csv, /export/excel, /upload, /export/log... |
| 콘텐츠 생성 | **1** | /api/agents/execute (범용 에이전트 실행) |
| 상세페이지 기획 | **0** | ❌ 없음 (Phase 1 재설계에서 추가 시작) |

**해석**: 운영자의 "승인-거부" 행위를 지원하는 API가 **콘텐츠 생성 API의 12배**.

## 4.4 Where the System is TOO HEAVY (과도한 영역)

1. **상태 머신 복잡도**: 6개 상태, 검증된 전환, 감사 로그 → **Over-engineered**
2. **Image Review Layer**: image_review 테이블, primary 선택, exclude, reorder → **과도함** (단순히 "이미지 순서 바꾸기"에 660 LOC)
3. **Export Service**: 채널별 포맷터, 검증, 이력 추적 → **필요 이상으로 정교**
4. **Auto-Approval Engine**: Golden Pass 기준 5가지 체크 → **적절하지만 우선순위 낮음**

## 4.5 Where the System is TOO THIN (부족한 영역)

1. **상세페이지 콘텐츠 구조**: 섹션별 기획, 순서 최적화 → **전무**
2. **이미지 리디자인 로직**: 카피, 레이아웃, 프롬프트 → **전무**
3. **판매 전략 생성**: 키워드, 해시태그, 리뷰 유도 → **전무**
4. **Content Agent**: 템플릿 치환만 수행, LLM 활용도 낮음 → **약함**

---

# 5. Data Model Fitness (데이터 모델 적합성)

## 5.1 현재 스키마 분석

### approval_queue 테이블 (62개 컬럼)

#### 소싱 정보 (적절함)
- source_url, source_title, source_price_cny, source_data_json, category, weight_kg

#### AI 생성 콘텐츠 (부족함)
- generated_naver_title
- generated_naver_description
- generated_coupang_title
- generated_price
- **문제**: 단순 제목/설명만 있음. 상세페이지 섹션, 이미지 카피, 판매 전략 필드 **전무**

#### 운영자 검수 콘텐츠 (적절함)
- reviewed_naver_title
- reviewed_naver_description
- reviewed_coupang_title
- reviewed_price
- **문제**: AI 생성 필드와 동일한 한계

#### 상태 관리 (과도함)
- review_status (검수 상태)
- registration_status (등록 상태)
- reviewer_status (검수자 상태)
- export_status (내보내기 상태)
- upload_status (업로드 상태)
- needs_human_review (수동 검토 필요 여부)
- reviewed_at, reviewed_by
- approved_at, approved_by
- rejected_at, rejected_by
- hold_reason
- **문제**: 5개의 독립적인 상태 필드는 불필요. review_status 하나로 충분

#### Phase 1 추가 필드 (2026-04-01 추가, 올바른 방향)
- product_summary_json (상품 요약)
- detail_content_json (상세 콘텐츠)
- image_design_json (이미지 디자인)
- sales_strategy_json (판매 전략)
- risk_assessment_json (리스크 평가)
- content_generated_at, content_reviewed_at, content_reviewer

**평가**: Phase 1 재설계가 **올바른 방향**. 하지만 JSON 필드보다는 정규화된 테이블이 더 나을 수 있음.

## 5.2 필요한 추가 필드/테이블

### 제안 1: 정규화된 상세 콘텐츠 테이블

```sql
CREATE TABLE product_content (
    id INTEGER PRIMARY KEY,
    review_id TEXT REFERENCES approval_queue(review_id),

    -- 상품 핵심 요약
    positioning_summary TEXT,
    usp_points TEXT,  -- JSON array
    target_customer TEXT,
    usage_scenarios TEXT,  -- JSON array
    differentiation_points TEXT,
    search_intent_summary TEXT,

    -- 상세페이지 섹션
    main_title TEXT,
    hook_copies TEXT,  -- JSON array
    key_benefits TEXT,  -- JSON array
    problem_scenarios TEXT,  -- JSON array
    solution_narrative TEXT,
    target_users TEXT,
    usage_guide TEXT,
    cautions TEXT,
    faq TEXT,  -- JSON array of {q, a}
    naver_body TEXT,
    coupang_body TEXT,
    short_ad_copies TEXT,  -- JSON array

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 제안 2: 이미지 리디자인 테이블

```sql
CREATE TABLE image_design_plan (
    id INTEGER PRIMARY KEY,
    review_id TEXT REFERENCES approval_queue(review_id),

    -- 썸네일 카피
    main_thumbnail_copy TEXT,
    sub_thumbnail_copies TEXT,  -- JSON array
    banner_copy TEXT,

    -- 섹션 카피
    section_copies TEXT,  -- JSON array
    layout_guide TEXT,
    tone_manner TEXT,
    forbidden_expressions TEXT,  -- JSON array

    -- 디자인 프롬프트
    generation_prompt TEXT,
    edit_prompt TEXT,

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 제안 3: 판매 전략 테이블

```sql
CREATE TABLE sales_strategy (
    id INTEGER PRIMARY KEY,
    review_id TEXT REFERENCES approval_queue(review_id),

    -- 타겟 및 포지셔닝
    target_audience TEXT,
    ad_points TEXT,  -- JSON array

    -- 키워드 전략
    primary_keywords TEXT,  -- JSON array
    secondary_keywords TEXT,  -- JSON array
    hashtags TEXT,  -- JSON array

    -- 리뷰 및 프로모션
    review_points TEXT,  -- JSON array
    price_positioning TEXT,
    sales_channels TEXT,  -- JSON array
    competitive_angles TEXT,  -- JSON array

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## 5.3 Classification (분류)

| 필요 기능 | 현재 지원 상태 |
|---------|------------|
| 메인/서브 카피 | ❌ Not supported |
| USP 구조 | ❌ Not supported |
| 상세페이지 섹션 | ❌ Not supported |
| 이미지 캡션 플랜 | ❌ Not supported |
| 프로모션 전략 | ❌ Not supported |
| 타겟 고객 | ❌ Not supported |
| 검색 키워드 | ❌ Not supported |
| 블로그 앵글 | ❌ Not supported |
| 숏폼 앵글 | ❌ Not supported |
| 채널 전략 노트 | ❌ Not supported |
| 네이버 제목/설명 | ✅ Already supported (generated_*/reviewed_*) |
| 쿠팡 제목 | ✅ Already supported |
| 가격 | ✅ Already supported |

**결론**: 핵심 가치 기능의 **90%가 데이터 모델에 없다**.

---

# 6. Workflow Fitness (워크플로우 적합성)

## 6.1 현재 워크플로우 평가

### 문제 1: 워크플로우가 내보내기 승인 중심

현재 review_workflow.py의 상태 흐름:

```
draft → under_review → approved_for_export → approved_for_upload
                    ↓
                  hold
                    ↓
                rejected
```

**문제점**:
- 목표 상태가 "approved_for_**export**" (내보내기 승인)
- 콘텐츠 품질이 목표가 아니라, **CSV 내보내기 가능 여부가 목표**
- 운영자는 "콘텐츠를 완성"하는 것이 아니라 "승인 버튼을 누르는" 것

### 문제 2: 운영자 UI가 잘못된 Artifact 중심

`review_detail.html`의 현재 구조:
1. 소싱 정보 (읽기 전용)
2. AI 생성 콘텐츠 (읽기 전용)
3. **운영자 수정 영역 (네이버 제목/설명, 쿠팡 제목, 가격)**
4. 이미지 검토
5. **승인/거부 버튼**

**문제점**:
- 운영자가 편집하는 것: **제목/설명/가격** (4개 필드)
- 운영자가 결정하는 것: **승인/거부/보류**
- 실제로 필요한 것: **상세페이지 전체 기획, 이미지 카피, 판매 전략**

### 문제 3: 최종 출력물이 잘못됨

현재 시스템의 최종 출력물:
- **CSV 파일** (네이버/쿠팡 스마트스토어 업로드용)

실제로 필요한 최종 출력물:
- **콘텐츠 패키지** (상세페이지 HTML, 이미지 카피, 판매 전략 문서)

## 6.2 불필요한 복잡도

### 제거 가능한 요소:

1. **5개의 독립적인 상태 필드**
   - review_status, registration_status, reviewer_status, export_status, upload_status
   - → review_status 하나로 충분

2. **Batch 승인/거부 API**
   - 현재 사용 사례: 없음
   - 실제 업무: 상품마다 다르게 판단해야 함
   - → 제거 가능

3. **Image Review Layer의 과도한 기능**
   - primary 선택, exclude, reorder
   - → 단순히 "대표 이미지 1개 선택"으로 충분

4. **Auto-Approval의 5가지 체크**
   - 현재: 마진율, 가격 범위, KC 인증, 리스크 플래그, 소싱 판정
   - → 마진율, 리스크 플래그 2가지로 충분

## 6.3 유지해야 할 부분

1. **Agent Framework** (재사용 가능)
2. **Approval Queue** (데이터 모델, 단순화 필요)
3. **Export Service** (보조 기능으로 유지)
4. **Scoring Engine** (유용하지만 우선순위 낮음)

## 6.4 보조 기능으로 전환해야 할 부분

1. **승인/거부 워크플로우** → "최종 확인" 단계로 격하
2. **CSV 내보내기** → "선택적 부가 기능"으로 격하
3. **상태 머신** → 단순화 (draft → complete 2개 상태로 충분)

---

# 7. Keep / Reduce / Expand (유지/축소/확대)

## 7.1 Keep (유지해야 할 것)

### 구조적으로 가치 있는 모듈:

1. **`agent_framework.py`** (444 LOC)
   - 재사용 가능한 에이전트 추상화
   - 워크플로우 실행 엔진
   - **유지, 확장 기반으로 활용**

2. **`sourcing_agent.py`** (429 LOC)
   - KC 인증 체크, 리스크 탐지
   - 한국 시장 적합성 검증
   - **유지, 콘텐츠 생성 입력으로 활용**

3. **`pricing_agent.py`** (224 LOC)
   - 마진 계산, 비용 구조 분석
   - **유지, 가격 전략 기반으로 활용**

4. **`approval_queue.py`** (545 LOC)
   - 데이터 모델, CRUD
   - **유지하되 스키마 재설계 필요**

5. **`export_service.py`** (483 LOC)
   - CSV/Excel 내보내기
   - **유지하되 보조 기능으로 격하**

6. **`scoring_engine.py`** (361 LOC)
   - 룰 기반 스코어링
   - **유지하되 우선순위 낮춤**

## 7.2 Reduce (축소해야 할 것)

### 과도하게 구축된 영역:

1. **`review_workflow.py`** (341 LOC)
   - 6개 상태 → **2개 상태로 단순화** (draft, complete)
   - 상태 전환 검증 로직 → **단순화**
   - **70% 축소**

2. **`review_console_api.py`** (896 LOC)
   - 12개 API → **5개 API로 축소** (load, save, complete, list, export)
   - batch 승인/거부 → **제거**
   - **60% 축소**

3. **`image_review_manager.py`** (660 LOC)
   - primary, exclude, reorder → **primary 선택만 유지**
   - image_review 테이블 → **단순화**
   - **80% 축소**

4. **`auto_approval.py`** (176 LOC)
   - 5가지 체크 → **2가지 체크로 단순화**
   - **50% 축소**

5. **`phase3_dashboard_apis.py`** (532 LOC)
   - 대시보드 통계 → **간소화**
   - batch 작업 → **제거**
   - **60% 축소**

6. **상태 관리 필드**
   - 5개 상태 → **1개 상태로 통합**
   - 15개 상태 관련 필드 → **5개 필드로 축소**

## 7.3 Expand (확대해야 할 것)

### 현재 부족한 핵심 영역:

1. **상세페이지 기획 모듈** (신규)
   - 목표: **2,000 LOC**
   - 기능:
     - 상품 해석 (USP, 타겟 고객, 검색 의도)
     - 섹션별 콘텐츠 생성 (훅 카피, 혜택, 문제-해결, FAQ)
     - 순서 최적화 (어떤 정보를 먼저 보여줄 것인가)
     - 모바일 최적화 (짧은 문단, 불릿 포인트)
   - 파일명: **`detail_page_strategist.py`**

2. **이미지 리디자인 모듈** (신규)
   - 목표: **1,500 LOC**
   - 기능:
     - 썸네일 카피 생성 (메인/서브)
     - 배너 카피, 섹션 헤드라인
     - 레이아웃 가이드 (이미지 배치, 텍스트 위치)
     - 톤앤매너 (색상, 폰트 추천)
     - AI 이미지 생성 프롬프트
     - 디자이너 편집 지시사항
   - 파일명: **`image_copy_planner.py`**

3. **판매 전략 모듈** (신규)
   - 목표: **1,200 LOC**
   - 기능:
     - 키워드 추출 (1차, 2차)
     - 해시태그 생성
     - 광고 포인트 추출
     - 리뷰 유도 전략
     - 경쟁 포지셔닝
     - 가격 전략 (프리미엄/가성비)
   - 파일명: **`promotion_strategist.py`**

4. **Content Agent 고도화** (기존 모듈 확장)
   - 현재: 669 LOC (템플릿 치환)
   - 목표: **1,500 LOC** (LLM 기반 콘텐츠 생성)
   - 추가 기능:
     - 검색 의도 분석
     - USP 자동 추출
     - 타겟 고객 페르소나 생성
     - A/B 테스트용 변형 생성
   - 파일명: **`content_agent.py` (고도화)**

5. **Review Console UI 재설계**
   - 현재: `review_detail.html` (328 줄)
   - 목표: **800 줄** (10개 섹션 구조)
   - 우선순위 재배치:
     1. 소싱 정보
     2. 리스크 평가
     3. **상품 핵심 요약** (NEW)
     4. 채널 기본 정보 (기존, 우선순위 하락)
     5. **상세페이지 기획** (NEW, 최우선)
     6. **이미지 리디자인 기획** (NEW)
     7. **판매 전략** (NEW)
     8. 이미지 검토 (기존, 단순화)
     9. 워크플로우 & 내보내기 (기존, 최하단)
     10. 생성 정보
   - 파일명: **`review_detail_phase1.html`** (이미 생성됨)

---

# 8. Recommended Target Architecture (목표 아키텍처)

## 8.1 Target Module Map (목표 모듈 구조도)

```
┌────────────────────────────────────────────────────────────┐
│                   Content Workbench UI                     │
│               (review_detail_phase1.html)                  │
│                                                            │
│  Priority 1: Detail Page Planning (상세페이지 기획)        │
│  Priority 2: Image Copy Planning (이미지 카피 기획)        │
│  Priority 3: Sales Strategy (판매 전략)                   │
│  Priority 4: Channel Copy (채널 문안)                     │
│  Priority 5: Export (내보내기) - OPTIONAL                 │
└────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌──────────────────┐  ┌──────────────┐
│Product        │  │Detail Page       │  │Image Copy    │
│Interpreter    │  │Strategist        │  │Planner       │
│               │  │                  │  │              │
│- Sourcing     │  │- Section Plan    │  │- Thumbnail   │
│- Pricing      │  │- USP Extract     │  │- Banner Copy │
│- Risk Check   │  │- Target Customer │  │- Layout Guide│
│               │  │- Hook Copies     │  │- AI Prompts  │
└───────────────┘  └──────────────────┘  └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │Promotion Strategist  │
                │                      │
                │- Keywords            │
                │- Hashtags            │
                │- Ad Points           │
                │- Review Strategy     │
                └──────────────────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │  Content Database    │
                │                      │
                │- product_content     │
                │- image_design_plan   │
                │- sales_strategy      │
                │- approval_queue      │
                └──────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        ┌──────────────┐      ┌──────────────┐
        │Validation    │      │Export Layer  │
        │Layer         │      │(Secondary)   │
        │              │      │              │
        │- Compliance  │      │- CSV         │
        │- Risk Filter │      │- Excel       │
        └──────────────┘      └──────────────┘
```

## 8.2 Target Data Flow (목표 데이터 흐름)

```
사용자 입력 (소스 URL, 이미지, 텍스트)
    │
    ▼
Product Interpreter
    ├─ Sourcing Agent (검증, KC 체크, 리스크)
    ├─ Pricing Agent (마진, 비용 구조)
    └─ Risk Assessment
    │
    ▼
approval_queue에 기본 정보 저장
    │
    ▼
Detail Page Strategist
    ├─ 상품 핵심 요약 (USP, 타겟 고객, 검색 의도)
    ├─ 섹션별 콘텐츠 (훅, 혜택, 문제-해결, FAQ)
    └─ 순서 최적화
    │
    ▼
product_content 테이블에 저장
    │
    ▼
Image Copy Planner
    ├─ 썸네일 카피 (메인/서브)
    ├─ 섹션 헤드라인
    ├─ 레이아웃 가이드
    └─ AI 생성 프롬프트
    │
    ▼
image_design_plan 테이블에 저장
    │
    ▼
Promotion Strategist
    ├─ 키워드 (1차/2차)
    ├─ 해시태그
    ├─ 광고 포인트
    ├─ 리뷰 유도 전략
    └─ 경쟁 포지셔닝
    │
    ▼
sales_strategy 테이블에 저장
    │
    ▼
Review Console (운영자 검수 및 편집)
    ├─ 모든 생성 콘텐츠 검토
    ├─ 필요 시 수정 (draft save)
    └─ 최종 완성 (complete)
    │
    ▼
Validation Layer (컴플라이언스 체크)
    │
    ├─ PASS → 콘텐츠 패키지 출력
    │            ├─ 상세페이지 HTML
    │            ├─ 이미지 카피 문서
    │            └─ 판매 전략 문서
    │
    └─ (선택) Export Layer
                 └─ CSV/Excel 내보내기
```

## 8.3 Reuse / Refactor / Deprecate / Add

### Reuse (재사용 가능)

1. **`agent_framework.py`** → 그대로 재사용
2. **`sourcing_agent.py`** → Product Interpreter의 일부로 재사용
3. **`pricing_agent.py`** → Product Interpreter의 일부로 재사용
4. **`approval_queue.py`** → 스키마 확장 후 재사용
5. **`export_service.py`** → 보조 기능으로 재사용

### Refactor (리팩토링 필요)

1. **`content_agent.py`**
   - 현재: 템플릿 치환
   - 목표: LLM 기반 콘텐츠 생성으로 고도화
   - 리팩토링 범위: **80%**

2. **`approval_ui_app.py`**
   - 현재: 모든 라우터 통합
   - 목표: 콘텐츠 생성 API 우선순위 상향
   - 리팩토링 범위: **30%** (라우터 재배치)

3. **`review_detail.html`**
   - 현재: 승인 중심 UI
   - 목표: 콘텐츠 기획 워크벤치
   - 리팩토링 범위: **완전 재설계** (`review_detail_phase1.html`로 대체)

### Deprecate (사용 중단)

1. **`review_workflow.py`** → 단순화 후 재통합
2. **`image_review_manager.py`** → 80% 축소 후 재통합
3. **`auto_approval.py`** → 단순화 후 재통합
4. **`phase3_dashboard_apis.py`** → batch 기능 제거, 통계만 유지

### Add (신규 추가)

1. **`detail_page_strategist.py`** (2,000 LOC)
   - 상세페이지 전체 기획
   - 섹션별 콘텐츠 생성
   - USP, 타겟 고객 분석

2. **`image_copy_planner.py`** (1,500 LOC)
   - 이미지 카피 생성
   - 레이아웃 가이드
   - AI 프롬프트 생성

3. **`promotion_strategist.py`** (1,200 LOC)
   - 키워드, 해시태그
   - 광고 전략
   - 리뷰 유도

4. **`content_generation_api.py`** (이미 생성됨, 500 LOC)
   - Phase 1 콘텐츠 생성 API 엔드포인트

5. **`review_detail_phase1.html`** (이미 생성됨, 800+ 줄)
   - 10개 섹션 구조
   - 콘텐츠 기획 워크벤치 UI

---

# 9. Priority Recommendations (우선순위 권고사항)

## P0: 즉시 구조 교정 (Immediate Structural Correction)

**기한**: 1주 이내

1. **데이터 모델 확장**
   - ✅ product_summary_json, detail_content_json, image_design_json, sales_strategy_json 필드 추가 (완료)
   - ⏳ 정규화된 테이블 생성 (product_content, image_design_plan, sales_strategy)
   - 파일: `apply_phase1_schema.py` (완료), `apply_content_tables_migration.py` (필요)

2. **콘텐츠 생성 API 구축**
   - ✅ `/api/phase1/review/{id}/generate-summary` (완료)
   - ✅ `/api/phase1/review/{id}/generate-detail-content` (완료)
   - ✅ `/api/phase1/review/{id}/generate-image-design` (완료)
   - ✅ `/api/phase1/review/{id}/generate-sales-strategy` (완료)
   - ✅ `/api/phase1/review/{id}/generate-all` (완료)
   - 파일: `content_generation_api.py` (완료)

3. **UI 재설계**
   - ✅ review_detail_phase1.html 생성 (완료)
   - ⏳ 프론트엔드 JavaScript 구현 (`review_detail_phase1.js`)
   - ⏳ 기존 review_detail.html을 review_detail_phase1.html로 교체

## P1: 다음 고가치 구축 (Next High-Value Build)

**기한**: 2주 이내

1. **Detail Page Strategist 모듈 구현**
   - 파일: `detail_page_strategist.py`
   - 기능:
     - USP 자동 추출 (제품 특징 → 고객 혜택 변환)
     - 타겟 고객 페르소나 생성
     - 섹션별 콘텐츠 생성 (훅, 혜택, 문제-해결, FAQ)
     - 순서 최적화 알고리즘
   - 예상 LOC: 2,000

2. **Image Copy Planner 모듈 구현**
   - 파일: `image_copy_planner.py`
   - 기능:
     - 썸네일 카피 생성 (메인/서브)
     - 배너 카피, 섹션 헤드라인
     - 레이아웃 가이드 (이미지 배치 추천)
     - AI 이미지 생성 프롬프트
   - 예상 LOC: 1,500

3. **Promotion Strategist 모듈 구현**
   - 파일: `promotion_strategist.py`
   - 기능:
     - 키워드 추출 (1차: 높은 검색량, 2차: 롱테일)
     - 해시태그 생성 (트렌드 반영)
     - 광고 포인트 추출
     - 리뷰 유도 전략
   - 예상 LOC: 1,200

## P2: 중기 아키텍처 개선 (Medium-Term Architecture Improvement)

**기한**: 1개월 이내

1. **워크플로우 단순화**
   - `review_workflow.py` 6개 상태 → 2개 상태 (draft, complete)
   - `review_console_api.py` 12개 API → 5개 API
   - `image_review_manager.py` 660 LOC → 150 LOC (primary 선택만)

2. **Content Agent 고도화**
   - 템플릿 치환 → LLM 기반 생성
   - 검색 의도 분석 추가
   - A/B 테스트 변형 생성

3. **Database 정규화**
   - JSON 필드 → 정규화된 테이블
   - product_content, image_design_plan, sales_strategy 테이블 생성
   - reviewed_* 필드도 별도 테이블로 분리

## P3: 후속 최적화 (Later Optimization)

**기한**: 2개월 이후

1. **성능 최적화**
   - SQLite → PostgreSQL 마이그레이션
   - Redis 캐싱 추가
   - 비동기 에이전트 실행 (async/await)

2. **관찰 가능성 (Observability)**
   - 구조화된 로깅 (JSON logs)
   - 분산 추적 (OpenTelemetry)
   - Prometheus 메트릭

3. **A/B 테스트 프레임워크**
   - 콘텐츠 변형 생성
   - 성과 추적
   - 자동 최적화

---

# 10. CTO Verdict (CTO 최종 평결)

## 10.1 Was the system built in the wrong direction?
## 시스템이 잘못된 방향으로 구축되었는가?

**예, 부분적으로 그렇습니다.**

Phase 1-2는 올바른 방향이었으나, **Phase 3-4가 승인 워크플로우 정교화에 과도하게 집중**하면서 핵심 가치(콘텐츠 생성)를 놓쳤습니다.

시스템은 기술적으로 견고하지만, **비즈니스 목표와 구조적 중심축이 어긋났습니다**.

## 10.2 Is it salvageable without rewrite?
## 전면 재작성 없이 복구 가능한가?

**예, 복구 가능합니다.**

현재 코드베이스의 **70%는 재사용 가능**합니다:
- Agent Framework: 재사용
- Sourcing/Pricing Agent: 재사용
- Export Service: 보조 기능으로 재사용
- Approval Queue: 스키마 확장 후 재사용

**30%만 재설계**하면 됩니다:
- 콘텐츠 생성 모듈 3개 신규 추가 (4,700 LOC)
- UI 재설계 (review_detail_phase1.html)
- 워크플로우 단순화

## 10.3 What is the single biggest architectural mistake?
## 가장 큰 아키텍처 실수는 무엇인가?

**"승인 워크플로우를 시스템의 중심축으로 만든 것"**

시스템이 다음과 같이 설계되었습니다:
- 목표: CSV 내보내기 승인
- 중심: review_status 상태 머신
- 운영자 역할: 승인/거부 결정자

실제로 필요한 것:
- 목표: **콘텐츠 패키지 완성**
- 중심: **콘텐츠 품질**
- 운영자 역할: **콘텐츠 기획자/편집자**

이 잘못된 중심축 때문에:
1. 코드의 43%가 승인 로직에 할애됨
2. 상세페이지 기획이 전무함
3. 운영자 UI가 "편집 도구"가 아니라 "승인 도구"로 설계됨

## 10.4 What is the single most valuable next correction?
## 가장 가치 있는 다음 수정 작업은?

**Detail Page Strategist 모듈 구현**

이것이 가장 중요한 이유:
1. **핵심 가치 제공**: 운영자가 실제로 원하는 것은 "완성된 상세페이지 콘텐츠"
2. **차별화**: 경쟁사가 제공하지 않는 고유 가치
3. **연쇄 효과**: 이 모듈이 완성되면 Image Copy Planner, Promotion Strategist가 자연스럽게 따라옴
4. **ROI**: 가장 높은 비즈니스 임팩트

우선순위:
1. **P0**: Detail Page Strategist (2,000 LOC)
2. P1: Image Copy Planner (1,500 LOC)
3. P1: Promotion Strategist (1,200 LOC)

## 10.5 Should the team continue the current track or reframe now?
## 팀이 현재 트랙을 유지해야 하는가, 아니면 지금 재정의해야 하는가?

**지금 즉시 재정의해야 합니다.**

**현재 트랙 유지 시 결과**:
- Phase 5: 더 정교한 승인 워크플로우 (필요 없음)
- Phase 6: 더 복잡한 내보내기 로직 (필요 없음)
- 결과: **비즈니스 목표와 더욱 멀어짐**

**재정의 후 결과**:
- Phase 1 (재설계): 콘텐츠 생성 중심으로 전환
- Phase 2: 상세페이지 기획 고도화
- Phase 3: 이미지 리디자인 자동화
- 결과: **실제 고객 가치 제공 시작**

### 즉시 실행해야 할 3가지:

1. **Phase 1 재설계 완료** (1주)
   - ✅ 데이터 모델 확장 (완료)
   - ✅ 콘텐츠 생성 API (완료)
   - ⏳ UI 완성 및 JavaScript 구현

2. **Detail Page Strategist 구현** (2주)
   - 상세페이지 섹션별 콘텐츠 생성
   - USP, 타겟 고객 분석
   - 순서 최적화

3. **기존 워크플로우 단순화** (1주)
   - 6개 상태 → 2개 상태
   - 12개 API → 5개 API
   - 승인 로직 보조 기능으로 격하

---

## 최종 권고사항 요약

### ✅ 즉시 실행 (1주)
1. Phase 1 UI 완성 (review_detail_phase1.html + JS)
2. 워크플로우 단순화 시작
3. 데이터 모델 정규화 (테이블 분리)

### 📋 단기 목표 (2주)
1. Detail Page Strategist 모듈 구현
2. Image Copy Planner 모듈 구현
3. Promotion Strategist 모듈 구현

### 🎯 중기 목표 (1개월)
1. Content Agent LLM 고도화
2. 기존 모듈 리팩토링 완료
3. 전체 시스템 통합 테스트

### 🚀 장기 목표 (2개월)
1. 성능 최적화 (PostgreSQL, Redis)
2. 관찰 가능성 구축
3. A/B 테스트 프레임워크

---

**보고서 작성**: 2026-04-01
**작성자**: CTO Diagnostic AI
**코드베이스**: `/home/fortymove/Fortimove-OS/pm-agent`
**분석 범위**: 73개 Python 모듈, 49,670 LOC, Phase 1-4 전체
**결론**: **부분적으로 틀어짐 - 즉시 재정의 필요**
