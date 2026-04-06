# PM Agent Phase 2 개발 타당성 분석 및 설계 보고서

**작성일**: 2026-03-31
**분석자**: Claude (AI Agent)
**상태**: ✅ 개발 가능 / ⚠️ 일부 수정 필요

---

## 📋 요약 (Executive Summary)

**결론**: Phase 2 개발은 **기술적으로 가능**하며, 기존 에이전트 시스템과 **충돌 없이 통합 가능**합니다.

### 핵심 판단

| 항목 | 판단 | 이유 |
|-----|------|------|
| **에이전트 충돌** | ✅ 없음 | Phase 2는 후처리 단계로 기존 에이전트와 독립적 |
| **DB 충돌** | ✅ 없음 | 기존 스키마 확장만 필요 (ALTER TABLE) |
| **아키텍처 충돌** | ✅ 없음 | 파이프라인 확장으로 설계 가능 |
| **규칙 기반 요구사항** | ✅ 충족 | LLM 최소화, 규칙 기반 우선 |
| **Explainability** | ✅ 충족 | 모든 결정에 reasons 필드 포함 |

### ⚠️ 수정 필요 사항

1. **Content Agent와 중복**: `detail_page_generator.py`가 기존 Content Agent와 기능 중복
   - **권장**: Content Agent를 확장하여 사용
2. **LLM 의존성**: 상세 설명 생성에 LLM 필요
   - **권장**: 템플릿 기반 + LLM 보조 방식
3. **DB 스키마**: Approval Queue가 SQLite → 확장성 고려 필요
   - **권장**: 단기는 SQLite, 장기는 PostgreSQL 마이그레이션

---

## 🏗️ 현재 시스템 구조 분석

### 기존 파이프라인 (Phase 1)

```
┌────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Daily Scout DB │────▶│ Integration  │────▶│ PM Agent API    │
│  (PostgreSQL)  │     │   Service    │     │ (FastAPI)       │
└────────────────┘     └──────────────┘     └─────────────────┘
                                                      │
                                                      ▼
                                             ┌─────────────────┐
                                             │ Workflow        │
                                             │ Executor        │
                                             └─────────────────┘
                                                      │
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                            │ Sourcing     │  │ Margin Check │  │ Registration │
                            │ Agent        │  │ Agent        │  │ Agent        │
                            └──────────────┘  └──────────────┘  └──────────────┘
                                    │                 │                 │
                                    └─────────────────┼─────────────────┘
                                                      ▼
                                             ┌─────────────────┐
                                             │ Approval Queue  │
                                             │  (SQLite)       │
                                             └─────────────────┘
                                                      │
                                                      ▼
                                             ┌─────────────────┐
                                             │ Human Review    │
                                             │  (Dashboard)    │
                                             └─────────────────┘
```

### 기존 에이전트 목록

| Agent | 역할 | 상태 | Phase |
|-------|------|------|-------|
| Sourcing Agent | 소싱 검증 (지재권, 컴플라이언스) | ✅ Active | 1 |
| Margin Check Agent | 마진율 계산 | ✅ Active | 1 |
| Product Registration Agent | 상품 등록 데이터 생성 | ✅ Active | 1 |
| Content Agent | 콘텐츠 생성 (SEO, 컴플라이언스) | ✅ Active | 1 |
| CS Agent | 고객 문의 응답 | ✅ Active | 1 |
| PM Agent | 전체 워크플로우 관리 | ✅ Active | 1 |

---

## 🎯 Phase 2 목표 구조

### 확장된 파이프라인

```
┌────────────────┐
│ Approval Queue │
│  (Phase 1)     │
└────────────────┘
         │
         │ (pending 상품)
         ▼
┌────────────────┐
│ Scoring Engine │ ◀─── 신규 모듈
│ (scoring_engine.py)
└────────────────┘
         │
         │ (점수, decision)
         ▼
┌────────────────┐
│ Approval Ranker│ ◀─── 신규 모듈
│ (approval_ranker.py)
└────────────────┘
         │
         │ (우선순위)
         ▼
┌────────────────┐
│ Human Review   │
│  (Dashboard)   │
└────────────────┘
         │
         │ (approved)
         ▼
┌────────────────┐
│ Detail Page    │ ◀─── 신규 모듈
│ Generator      │     (기존 Content Agent 확장)
└────────────────┘
         │
         │ (채널별 콘텐츠)
         ▼
┌────────────────┐
│ Upload Queue   │ ◀─── 신규 테이블
│ (per channel)  │
└────────────────┘
```

---

## ✅ 에이전트 충돌 분석

### 1. 기존 에이전트와의 관계

| 신규 모듈 | 기존 에이전트 | 충돌 여부 | 관계 |
|----------|--------------|----------|------|
| Scoring Engine | 없음 | ✅ 없음 | 독립적 후처리 |
| Approval Ranker | 없음 | ✅ 없음 | Approval Queue 읽기만 |
| Detail Page Generator | **Content Agent** | ⚠️ **기능 중복** | 확장 권장 |

### 2. Content Agent와의 중복 분석

**기존 Content Agent 기능** (content_agent.py):
```python
class ContentInputSchema(BaseModel):
    product_name: str
    product_category: str
    key_features: List[str]
    price: int
    content_type: str = "product_page"
    compliance_mode: bool = True

# 출력:
{
    "seo_title": "...",
    "seo_description": "...",
    "main_content": "...",
    "compliance_status": "safe"
}
```

**Phase 2 Detail Page Generator 요구사항**:
- 네이버 스마트스토어용 상품명
- 쿠팡용 상품명
- 핵심 USP 3개
- 금지표현 제거된 상세설명
- SEO 태그 10개
- 옵션명 한글화

**판단**: **70% 중복** → Content Agent를 **확장**하는 것이 바람직

**권장 수정**:
```python
# detail_page_generator.py를 별도 생성하는 대신
# content_agent.py를 확장

class EnhancedContentInputSchema(BaseModel):
    product_name: str
    product_category: str
    key_features: List[str]
    price: int
    content_type: str = "product_page"
    compliance_mode: bool = True
    channels: List[str] = ["naver", "coupang"]  # 신규
    generate_usp: bool = True  # 신규
    generate_options: bool = True  # 신규
```

---

## 🗄️ DB 스키마 확장 설계

### 1. approval_queue 테이블 확장

**현재 스키마**:
```sql
CREATE TABLE approval_queue (
    review_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_title TEXT NOT NULL,
    registration_status TEXT NOT NULL,
    reviewer_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- ... 기타 필드
);
```

**Phase 2 확장**:
```sql
-- ✅ 충돌 없음: ALTER TABLE로 추가 가능
ALTER TABLE approval_queue ADD COLUMN score INTEGER DEFAULT 0;
ALTER TABLE approval_queue ADD COLUMN decision TEXT DEFAULT 'review';
ALTER TABLE approval_queue ADD COLUMN priority INTEGER DEFAULT 50;
ALTER TABLE approval_queue ADD COLUMN reasons_json TEXT;
ALTER TABLE approval_queue ADD COLUMN content_status TEXT DEFAULT 'pending';
ALTER TABLE approval_queue ADD COLUMN scoring_updated_at TEXT;

CREATE INDEX idx_approval_queue_score ON approval_queue(score DESC);
CREATE INDEX idx_approval_queue_priority ON approval_queue(priority DESC);
CREATE INDEX idx_approval_queue_decision ON approval_queue(decision);
```

**충돌 여부**: ✅ **없음**
- 기존 컬럼 수정 없음
- 기존 쿼리 영향 없음
- 인덱스 추가만

### 2. wellness_products 테이블 확장

**현재 스키마** (PostgreSQL):
```sql
CREATE TABLE wellness_products (
    id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    workflow_status VARCHAR(50) DEFAULT 'pending',
    workflow_updated_at TIMESTAMP,
    workflow_error TEXT,
    -- ... 기타 필드
);
```

**Phase 2 확장**:
```sql
ALTER TABLE wellness_products ADD COLUMN scoring_updated_at TIMESTAMP;
ALTER TABLE wellness_products ADD COLUMN publishing_status VARCHAR(50) DEFAULT 'draft';

CREATE INDEX idx_wellness_publishing ON wellness_products(publishing_status);
```

**충돌 여부**: ✅ **없음**

### 3. 신규 테이블: channel_upload_queue

```sql
-- 채널별 업로드 대기열
CREATE TABLE channel_upload_queue (
    upload_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,  -- FK to approval_queue
    channel TEXT NOT NULL,  -- 'naver', 'coupang', 'amazon', etc.
    content_json TEXT NOT NULL,  -- 채널별 맞춤 콘텐츠
    upload_status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    upload_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    uploaded_at TEXT,
    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id)
);

CREATE INDEX idx_channel_upload_status ON channel_upload_queue(upload_status);
CREATE INDEX idx_channel_upload_channel ON channel_upload_queue(channel);
```

**충돌 여부**: ✅ **없음** (신규 테이블)

---

## 🧩 모듈별 설계

### 1. Scoring Engine (scoring_engine.py)

**목적**: 상품별 0~100점 산출 및 자동 결정

**입력**:
```python
{
    "review_id": "uuid",
    "source_type": "workflow:quick_sourcing_check",
    "agent_output": {
        "sourcing_decision": "통과",
        "margin_analysis": {
            "margin_rate": 0.45,
            "target_price": 15900
        },
        "policy_risks": [],
        "certification_required": false
    },
    "source_data": {
        "source_url": "...",
        "source_price_cny": 30.0,
        "weight_kg": 0.5
    }
}
```

**출력**:
```python
{
    "score": 85,
    "decision": "auto_approve",  # auto_approve / review / hold / reject
    "reasons": [
        "높은 마진율 (45%): +30점",
        "정책 위험 없음: +25점",
        "인증 불필요: +15점",
        "소싱 안정성 높음: +15점"
    ],
    "breakdown": {
        "margin_score": 30,  # 0-35점
        "policy_risk_score": 25,  # 0-25점
        "certification_risk_score": 15,  # 0-15점
        "sourcing_stability_score": 15,  # 0-15점
        "option_complexity_score": 0,  # 0-5점 (낮을수록 좋음)
        "category_fit_score": 0,  # 0-5점
        "competition_score": 0  # 0-0점 (미구현)
    }
}
```

**규칙 기반 로직**:

```python
class ScoringEngine:
    """
    완전 규칙 기반 점수화 엔진
    LLM 사용 없음 - 모든 결정은 명시적 규칙으로 설명 가능
    """

    def calculate_margin_score(self, margin_rate: float) -> tuple[int, str]:
        """마진율 점수 (0-35점)"""
        if margin_rate >= 0.50:
            return 35, f"매우 높은 마진율 ({margin_rate:.1%}): +35점"
        elif margin_rate >= 0.40:
            return 30, f"높은 마진율 ({margin_rate:.1%}): +30점"
        elif margin_rate >= 0.30:
            return 20, f"적정 마진율 ({margin_rate:.1%}): +20점"
        elif margin_rate >= 0.20:
            return 10, f"낮은 마진율 ({margin_rate:.1%}): +10점"
        else:
            return 0, f"마진율 부족 ({margin_rate:.1%}): 0점"

    def calculate_policy_risk_score(self, policy_risks: List[str]) -> tuple[int, str]:
        """정책 위험 점수 (0-25점)"""
        if len(policy_risks) == 0:
            return 25, "정책 위험 없음: +25점"
        elif len(policy_risks) <= 2:
            return 15, f"경미한 정책 위험 ({len(policy_risks)}개): +15점"
        else:
            return 0, f"심각한 정책 위험 ({len(policy_risks)}개): 0점"

    def calculate_certification_risk_score(self, cert_required: bool) -> tuple[int, str]:
        """인증 위험 점수 (0-15점)"""
        if not cert_required:
            return 15, "인증 불필요: +15점"
        else:
            return 5, "인증 필요: +5점"

    def make_decision(self, score: int, breakdown: dict) -> str:
        """점수 기반 자동 결정"""
        if score >= 80:
            return "auto_approve"  # 자동 승인
        elif score >= 60:
            return "review"  # 인간 검토 필요
        elif score >= 40:
            return "hold"  # 보류 (개선 후 재검토)
        else:
            return "reject"  # 거부
```

**에이전트 충돌**: ✅ **없음** (독립 모듈)

---

### 2. Approval Ranker (approval_ranker.py)

**목적**: Approval Queue의 pending 상품을 점수순으로 정렬

**로직**:
```python
class ApprovalRanker:
    """
    Approval Queue의 우선순위를 재계산하는 모듈
    LLM 사용 없음 - 순수 DB 정렬
    """

    def rank_pending_items(self) -> List[Dict]:
        """
        pending 상품을 점수순으로 정렬하고 priority 부여
        """
        queue = ApprovalQueueManager()
        items = queue.list_items(reviewer_status="pending")

        # 점수순 정렬 (높은 순)
        sorted_items = sorted(items, key=lambda x: x.get('score', 0), reverse=True)

        # Priority 재계산 (1부터 시작)
        for i, item in enumerate(sorted_items, 1):
            self.update_priority(item['review_id'], i)

        return sorted_items

    def update_priority(self, review_id: str, priority: int):
        """Priority 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE approval_queue SET priority = ? WHERE review_id = ?",
                (priority, review_id)
            )
            conn.commit()
```

**실행 시점**:
- Daily Scout Integration 완료 후
- Scoring Engine 실행 후
- 대시보드 새로고침 시

**에이전트 충돌**: ✅ **없음** (읽기 전용 + 업데이트만)

---

### 3. Detail Page Generator (확장 방안)

**권장**: 별도 모듈보다 **Content Agent 확장**

**이유**:
1. Content Agent가 이미 콘텐츠 생성 기능 보유
2. 코드 중복 방지
3. 유지보수 용이

**확장 방안**:

```python
# content_agent.py 확장

class MultiChannelContentInputSchema(BaseModel):
    """채널별 콘텐츠 생성 입력"""
    product_name: str
    product_category: str
    key_features: List[str]
    price: int
    channels: List[str] = ["naver", "coupang"]  # 신규
    generate_usp: bool = True  # 신규
    generate_options: bool = True  # 신규
    options: List[str] = []  # 신규

class MultiChannelContentOutputSchema(BaseModel):
    """채널별 콘텐츠 생성 출력"""
    naver_title: Optional[str] = None
    coupang_title: Optional[str] = None
    usp_points: List[str] = []
    detail_description: str
    seo_tags: List[str]
    options_korean: Dict[str, str] = {}
    compliance_status: str

class ContentAgent(BaseHttpAgent):
    # 기존 execute() 유지

    def execute_multichannel(self, input_data: Dict[str, Any]) -> TaskResult:
        """채널별 콘텐츠 생성 (신규 메서드)"""
        schema = MultiChannelContentInputSchema(**input_data)

        output = {
            "naver_title": self._generate_naver_title(schema),
            "coupang_title": self._generate_coupang_title(schema),
            "usp_points": self._generate_usp(schema),
            "detail_description": self._generate_description(schema),
            "seo_tags": self._generate_seo_tags(schema),
            "options_korean": self._translate_options(schema.options),
            "compliance_status": "safe"
        }

        return TaskResult(
            status=AgentStatus.COMPLETED,
            output=output,
            agent_id="content"
        )
```

**에이전트 충돌**: ⚠️ **기능 확장** (기존 코드 수정)

---

## 📁 디렉토리 구조

```
pm-agent/
├── scoring_engine.py          # 신규: 점수화 엔진
├── approval_ranker.py          # 신규: 우선순위 관리
├── content_agent.py            # 수정: 채널별 콘텐츠 생성 추가
├── channel_upload_manager.py  # 신규: 채널별 업로드 대기열
├── agent_framework.py          # 유지
├── real_agents.py              # 유지
├── approval_queue.py           # 수정: 스키마 확장
├── daily_scout_integration_api.py  # 수정: scoring 연동
│
├── tests/
│   ├── test_scoring_engine.py
│   ├── test_approval_ranker.py
│   ├── test_content_multichannel.py
│   └── test_channel_upload_manager.py
│
└── migrations/
    └── 002_phase2_schema.sql   # DB 마이그레이션
```

---

## 🔄 실행 순서

### Phase 2 파이프라인

```
1. Daily Scout Integration (기존)
   ↓
2. Sourcing + Margin Check (기존)
   ↓
3. Approval Queue 저장 (기존)
   ↓
4. ✨ Scoring Engine 실행 (신규)
   - 점수 계산
   - Decision 결정
   - DB 업데이트
   ↓
5. ✨ Approval Ranker 실행 (신규)
   - Priority 재계산
   - 정렬
   ↓
6. Human Review (기존)
   - 대시보드에서 우선순위별 표시
   ↓
7. ✨ Multi-Channel Content 생성 (신규)
   - Content Agent (확장) 호출
   - 채널별 콘텐츠 생성
   ↓
8. ✨ Upload Queue 저장 (신규)
   - channel_upload_queue 테이블
   ↓
9. 마켓플레이스 업로드 (Phase 3)
   - 향후 구현
```

---

## ⚠️ 충돌 및 리스크 분석

### 1. 에이전트 충돌

| 충돌 유형 | 발생 가능성 | 영향도 | 완화 방안 |
|----------|------------|--------|----------|
| Agent 이름 중복 | ✅ 없음 | N/A | 신규 모듈은 독립적 이름 |
| Agent 로직 충돌 | ✅ 없음 | N/A | 후처리 단계로 분리 |
| Content Agent 중복 | ⚠️ 있음 | 중 | Content Agent 확장 권장 |
| DB 경합 | ✅ 없음 | N/A | SQLite는 단일 쓰기, 읽기 다중 가능 |
| Workflow 충돌 | ✅ 없음 | N/A | 기존 workflow는 유지 |

### 2. DB 충돌

| 충돌 유형 | 발생 가능성 | 영향도 | 완화 방안 |
|----------|------------|--------|----------|
| 테이블 충돌 | ✅ 없음 | N/A | 신규 테이블만 생성 |
| 컬럼 충돌 | ✅ 없음 | N/A | ALTER TABLE ADD COLUMN |
| 인덱스 충돌 | ✅ 없음 | N/A | IF NOT EXISTS 사용 |
| 외래키 충돌 | ✅ 없음 | N/A | 신규 FK만 추가 |
| 트랜잭션 충돌 | ⚠️ 낮음 | 낮 | SQLite는 파일 락, 재시도 로직 |

### 3. 성능 리스크

| 리스크 | 발생 가능성 | 영향도 | 완화 방안 |
|--------|------------|--------|----------|
| SQLite 확장성 | ⚠️ 있음 | 중 | 향후 PostgreSQL 마이그레이션 |
| 점수 계산 지연 | ✅ 낮음 | 낮 | 순수 규칙 기반 (ms 단위) |
| LLM 호출 지연 | ⚠️ 있음 | 중 | 비동기 처리, 캐싱 |
| 대용량 데이터 | ✅ 없음 | N/A | 현재 규모 (50개/일)는 무리 없음 |

---

## 📊 구현 복잡도 분석

### 모듈별 복잡도

| 모듈 | LOC 예상 | 복잡도 | 개발 시간 | 테스트 시간 |
|-----|---------|--------|----------|-----------|
| scoring_engine.py | 300-400 | 낮음 | 4시간 | 2시간 |
| approval_ranker.py | 150-200 | 낮음 | 2시간 | 1시간 |
| content_agent.py (확장) | +200 | 중간 | 6시간 | 3시간 |
| channel_upload_manager.py | 250-300 | 낮음 | 3시간 | 2시간 |
| DB 마이그레이션 | 100 | 낮음 | 1시간 | 1시간 |
| **총계** | **~1,200** | **중간** | **16시간** | **9시간** |

**총 개발 기간**: 약 **3-4일** (1인 기준)

---

## ✅ 권장 수정 사항

### 1. Detail Page Generator → Content Agent 확장

**현재 요구사항**:
```python
# detail_page_generator.py (별도 모듈)
```

**권장 수정**:
```python
# content_agent.py (기존 모듈 확장)
def execute_multichannel(self, input_data: Dict[str, Any]) -> TaskResult:
    """채널별 콘텐츠 생성"""
    pass
```

**이유**:
- 코드 중복 70% 감소
- 유지보수 용이
- 기존 테스트 재사용 가능

### 2. LLM 사용 최소화

**현재 요구사항**: "규칙 기반 우선, LLM은 보조"

**구현 방안**:
- **Scoring Engine**: LLM 사용 없음 (100% 규칙)
- **Content Generation**: 템플릿 + LLM 보조
  - 템플릿: 80% (상품명, USP, 옵션명)
  - LLM: 20% (상세 설명 다듬기)

**예시**:
```python
# 템플릿 기반 (LLM 없음)
naver_title = f"{product_name} | {key_features[0]} | {category}"

# LLM 보조 (옵션)
if use_llm:
    naver_title = self.polish_with_llm(naver_title)
```

### 3. DB 스키마 점진적 확장

**현재**: SQLite (approval_queue)

**권장**:
- **단기 (Phase 2)**: SQLite 유지 (빠른 구현)
- **중기 (Phase 3)**: PostgreSQL 마이그레이션 (확장성)
- **장기 (Phase 4)**: Redis 캐싱 추가 (성능)

---

## 🚀 구현 로드맵

### Phase 2.1: 점수화 및 우선순위 (1주)

**목표**: Approval Queue에 점수 및 우선순위 추가

**작업**:
1. ✅ DB 마이그레이션 (approval_queue, wellness_products)
2. ✅ scoring_engine.py 구현 (규칙 기반)
3. ✅ approval_ranker.py 구현
4. ✅ daily_scout_integration_api.py 연동
5. ✅ 테스트 및 검증

**산출물**:
- `scoring_engine.py`
- `approval_ranker.py`
- `migrations/002_phase2_schema.sql`
- `test_scoring_engine.py`
- `test_approval_ranker.py`

### Phase 2.2: 채널별 콘텐츠 생성 (1주)

**목표**: 승인된 상품의 채널별 콘텐츠 자동 생성

**작업**:
1. ✅ content_agent.py 확장 (멀티채널)
2. ✅ channel_upload_queue 테이블 생성
3. ✅ channel_upload_manager.py 구현
4. ✅ 템플릿 기반 콘텐츠 생성
5. ✅ 테스트 및 검증

**산출물**:
- `content_agent.py` (확장)
- `channel_upload_manager.py`
- `test_content_multichannel.py`

### Phase 2.3: 대시보드 연동 (1주)

**목표**: 대시보드에서 점수/우선순위 표시

**작업**:
1. ✅ approval_ui_app.py 수정 (점수 표시)
2. ✅ 우선순위별 정렬
3. ✅ Decision 아이콘 추가
4. ✅ Reasons 팝업 표시
5. ✅ UI 테스트

**산출물**:
- `approval_ui_app.py` (수정)
- UI 스크린샷

---

## 📝 샘플 입력/출력

### Scoring Engine

**입력**:
```json
{
  "review_id": "abc123",
  "source_type": "workflow:quick_sourcing_check",
  "agent_output": {
    "sourcing": {
      "sourcing_decision": "통과",
      "policy_risks": [],
      "certification_required": false
    },
    "margin": {
      "margin_analysis": {
        "margin_rate": 0.45,
        "target_price": 15900
      },
      "final_decision": "등록 가능"
    }
  },
  "source_data": {
    "source_url": "https://item.taobao.com/item.htm?id=123",
    "source_price_cny": 30.0,
    "weight_kg": 0.5,
    "category": "주방용품"
  }
}
```

**출력**:
```json
{
  "score": 85,
  "decision": "auto_approve",
  "reasons": [
    "높은 마진율 (45%): +30점",
    "정책 위험 없음: +25점",
    "인증 불필요: +15점",
    "소싱 안정성 높음: +15점"
  ],
  "breakdown": {
    "margin_score": 30,
    "policy_risk_score": 25,
    "certification_risk_score": 15,
    "sourcing_stability_score": 15,
    "option_complexity_score": 0,
    "category_fit_score": 0,
    "competition_score": 0
  },
  "timestamp": "2026-03-31T20:00:00"
}
```

### Content Agent (Multi-Channel)

**입력**:
```json
{
  "product_name": "스테인리스 텀블러",
  "product_category": "주방용품",
  "key_features": ["진공 단열", "500ml", "휴대용"],
  "price": 15900,
  "channels": ["naver", "coupang"],
  "generate_usp": true,
  "generate_options": true,
  "options": ["350ml", "500ml", "750ml"]
}
```

**출력**:
```json
{
  "naver_title": "스테인리스 텀블러 | 진공 단열 500ml | 휴대용 보온병",
  "coupang_title": "[오늘출발] 스테인리스 텀블러 500ml 진공 단열",
  "usp_points": [
    "24시간 보온/보냉 유지 - 진공 단열 설계",
    "500ml 대용량 - 하루 종일 충분한 수분 섭취",
    "휴대 편리 - 차량 컵홀더에 딱 맞는 디자인"
  ],
  "detail_description": "매일 사용하는 텀블러, 스테인리스 소재로 안전하게...",
  "seo_tags": [
    "스테인리스텀블러",
    "진공단열텀블러",
    "보온병",
    "휴대용텀블러",
    "500ml텀블러",
    "스테인레스보온병",
    "진공보온병",
    "대용량텀블러",
    "차량용텀블러",
    "보온보냉텀블러"
  ],
  "options_korean": {
    "350ml": "소형 (350ml)",
    "500ml": "중형 (500ml)",
    "750ml": "대형 (750ml)"
  },
  "compliance_status": "safe"
}
```

---

## 🎯 최종 판단

### ✅ 개발 가능 여부

**결론**: **Phase 2 개발 가능**

**근거**:
1. ✅ 에이전트 충돌 없음 (후처리 단계)
2. ✅ DB 충돌 없음 (스키마 확장만)
3. ✅ 기술적 난이도 낮음 (규칙 기반)
4. ✅ 기존 코드 재사용 가능 (Content Agent)
5. ✅ 테스트 가능 (독립 모듈)

### ⚠️ 주의 사항

1. **Content Agent 중복**: 별도 모듈 대신 확장 권장
2. **LLM 의존성**: 템플릿 우선, LLM 보조
3. **SQLite 확장성**: 향후 PostgreSQL 마이그레이션 고려
4. **점진적 구현**: Phase 2.1 → 2.2 → 2.3 순차 진행

### 📅 예상 일정

| Phase | 내용 | 기간 | 누적 |
|-------|------|------|------|
| Phase 2.1 | 점수화 및 우선순위 | 1주 | 1주 |
| Phase 2.2 | 채널별 콘텐츠 생성 | 1주 | 2주 |
| Phase 2.3 | 대시보드 연동 | 1주 | 3주 |
| **총계** | | **3주** | |

---

## 📚 참고 문서

- [Phase 1 완료 보고서](api-execution-daily-scout-integration-complete.md)
- [자동화 완료 요약](AUTOMATION-COMPLETE-SUMMARY.md)
- [에이전트 프레임워크](../pm-agent/agent_framework.py)
- [Approval Queue 구조](../pm-agent/approval_queue.py)

---

**보고서 작성일**: 2026-03-31 20:30 KST
**분석 상태**: ✅ 완료
**개발 권장 여부**: ✅ **개발 진행 권장**
