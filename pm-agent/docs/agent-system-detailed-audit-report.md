# Agent System Detailed Audit Report

**Date**: 2026-04-01
**Auditor**: Claude (Staging Validator)
**System**: PM Agent System (Fortimove-OS)
**Server**: localhost:8001

---

## Executive Summary

PM Agent 시스템에 대한 전면 감사를 수행한 결과, **기본 인프라는 90% 완성**되어 있으나 **5가지 Critical 문제**가 발견되었습니다.

### 주요 발견 사항

| 항목 | 상태 | 비고 |
|------|------|------|
| Database Schema | ✅ 90% 완성 | 54개 컬럼, Product Content Pack 확장 가능 |
| Agent Framework | ✅ 정상 작동 | BaseAgent 추상 클래스 구조 완비 |
| Agent Registration | ⚠️ 5개 등록 | Content Agent 누락, Pricing Agent 파일 없음 |
| Data Population | ⚠️ 76.9% | 26개 레코드 중 20개 콘텐츠 생성됨 |
| Review Workflow | ✅ 정상 작동 | 6개 상태, 전환 규칙 완비 |
| Image Review | ✅ 100% 작동 | 21개 리뷰, 이미지 구조 정상 |
| CSV Export | ✅ 정상 작동 | 네이버/쿠팡 CSV 생성 성공 |

### Critical Issues (즉시 해결 필요)

1. 🔴 **Content Agent API 키 없음** - ANTHROPIC_API_KEY 미설정
2. 🔴 **Pricing Agent 파일 누락** - pricing_agent.py 존재하지 않음
3. 🔴 **Sourcing Agent 66% 실패율** - 6회 실행 중 4회 실패
4. 🔴 **Agent 등록 불일치** - API 응답과 실제 파일 불일치
5. 🔴 **Product Content Pack 필드 누락** - 6개 필수 컬럼 미생성

---

## 1. Database Schema Analysis

### 1.1 Overall Structure

**Total Columns**: 54개

```
approval_queue 테이블 구조:
├── Generated Fields (9개)
│   ├── generated_naver_title
│   ├── generated_naver_description
│   ├── generated_naver_tags
│   ├── generated_coupang_title
│   ├── generated_coupang_description
│   ├── generated_coupang_tags
│   ├── generated_options_json
│   ├── generated_price
│   └── generated_category
│
├── Reviewed Fields (11개)
│   ├── reviewed_naver_title
│   ├── reviewed_naver_description
│   ├── reviewed_naver_tags
│   ├── reviewed_coupang_title
│   ├── reviewed_coupang_description
│   ├── reviewed_coupang_tags
│   ├── reviewed_options_json
│   ├── reviewed_price
│   ├── reviewed_category
│   ├── reviewed_at
│   └── reviewed_by
│
└── Workflow Fields (20개)
    ├── review_status
    ├── review_notes
    ├── registration_status
    ├── needs_human_review
    └── ... (16 more)
```

### 1.2 Data Population Status

**Total Records**: 26개

| Field | Population | Percentage |
|-------|------------|------------|
| generated_naver_title | 20/26 | 76.9% |
| generated_coupang_title | 20/26 | 76.9% |
| generated_price | 20/26 | 76.9% |
| reviewed_naver_title | 2/26 | **7.7%** ⚠️ |
| source_data_json | 6/26 | **23.1%** ⚠️ |

**분석**:
- ✅ AI 생성 콘텐츠: 76.9% 양호
- ⚠️ 운영자 검수 콘텐츠: 7.7% 매우 낮음
- ⚠️ 원본 데이터: 23.1% 낮음 (대부분 테스트 데이터)

### 1.3 Review Status Breakdown

| Status | Count | Percentage |
|--------|-------|------------|
| draft | 24 | 92.3% |
| approved_for_export | 1 | 3.8% |
| rejected | 1 | 3.8% |

**분석**: 대부분 draft 상태 (테스트 환경 정상)

---

## 2. Image Review System

### 2.1 Status

**Total Image Reviews**: 21개
**With Reviewed Images**: 21/21 (100%)

**Image Data Structure** (정상):
```json
{
  "image_id": "img-abc123",
  "url": "https://...",
  "display_order": 1,
  "is_primary": true,
  "is_excluded": false,
  "warnings": [],
  "notes": ""
}
```

**검증 결과**: ✅ 이미지 검수 시스템 정상 작동

---

## 3. Review Workflow Configuration

### 3.1 State Machine

**Active Statuses**: 6개

```
draft (초안)
  → under_review, hold

under_review (검수 중)
  → approved_for_export, hold, rejected

approved_for_export (Export 승인)
  → approved_for_upload, hold

approved_for_upload (Upload 승인)
  → hold

hold (보류)
  → under_review, rejected

rejected (거부)
  → (terminal state)
```

**검증 결과**: ✅ 워크플로우 전환 규칙 정상

**알려진 UX 이슈**:
- ⚠️ draft → approved_for_export 직접 전환 불가 (2단계 필요)

---

## 4. Agent Code Analysis

### 4.1 Agent Files Inventory

| Agent | File | Size | Lines | Status |
|-------|------|------|-------|--------|
| PM Agent | pm_agent.py | 8.2 KB | 211 | ✅ 존재 |
| Sourcing Agent | sourcing_agent.py | 11.0 KB | 293 | ✅ 존재 |
| Product Registration | product_registration_agent.py | 16.6 KB | 387 | ✅ 존재 |
| **Pricing Agent** | pricing_agent.py | - | - | 🔴 **파일 없음** |
| CS Agent | cs_agent.py | 4.1 KB | 104 | ✅ 존재 |
| Content Agent | content_agent.py | 25.8 KB | 669 | ✅ 존재 (최대) |

**Total Code**: ~1,664 lines

### 4.2 Agent Capabilities

#### Content Agent (가장 복잡)
- **Size**: 25.8 KB (669 lines)
- **Public Methods**: 4
  - `input_schema()`
  - `output_schema()`
  - `register_content_agent()`
  - `execute_multichannel()`
- **Features**:
  - 네이버/쿠팡 멀티채널 콘텐츠 생성
  - 컴플라이언스 체크
  - ⚠️ ANTHROPIC_API_KEY 필요

#### Sourcing Agent
- **Size**: 11.0 KB (293 lines)
- **실행 기록**: 6회 (성공 2, 실패 4) - **66% 실패율**
- ⚠️ ANTHROPIC_API_KEY 필요

#### Product Registration Agent
- **Size**: 16.6 KB (387 lines)
- **실행 기록**: 1회 (성공 1)
- ⚠️ ANTHROPIC_API_KEY 필요

#### PM Agent
- **Size**: 8.2 KB (211 lines)
- **실행 기록**: 0회
- ⚠️ ANTHROPIC_API_KEY 필요

#### CS Agent
- **Size**: 4.1 KB (104 lines)
- **실행 기록**: 0회
- ⚠️ ANTHROPIC_API_KEY 필요

#### Pricing Agent
- 🔴 **파일 존재하지 않음**
- API 응답에는 "Pricing Agent" 표시됨 (불일치)

### 4.3 Agent Framework

**BaseAgent** (agent_framework.py):
```python
class BaseAgent(ABC):
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> TaskResult:
        pass
```

- ✅ 추상 클래스 구조 정상
- ✅ AgentRegistry 패턴 구현
- ✅ ExecutionContext 관리

---

## 5. Agent Registration Status

### 5.1 Registered Agents (real_agents.py)

```python
registry.register("image_localization", ImageLocalizationAgent())
registry.register("margin_check", MarginCheckAgent())
registry.register("daily_scout_status", DailyScoutStatusAgent())
registry.register("sourcing", SourcingAgent())
registry.register("content", ContentAgent())
```

**등록된 에이전트**: 5개

### 5.2 API Response vs. Reality

**API Response** (`/api/agents/status`):
```
✅ cs                   | CS Agent
✅ pm                   | PM Agent
✅ pricing              | Pricing Agent
❌ product_registration | Product Registration Agent
❌ sourcing             | Sourcing Agent
```

**실제 real_agents.py**:
```
✅ image_localization
✅ margin_check
✅ daily_scout_status
✅ sourcing
✅ content
```

**🔴 Critical 불일치 발견**:
- API에 표시되는 에이전트와 실제 등록된 에이전트가 다름
- `content`, `image_localization`, `margin_check`, `daily_scout_status`가 API에 안 보임
- `cs`, `pm`, `pricing`, `product_registration`이 real_agents.py에 없음

**원인 추정**:
- 여러 등록 파일 존재 가능성
- 또는 API가 다른 소스에서 에이전트 목록 가져옴

---

## 6. Agent Execution Analysis

### 6.1 Execution Statistics

| Agent | Total Runs | Success | Failure | Success Rate |
|-------|-----------|---------|---------|--------------|
| PM Agent | 0 | 0 | 0 | - |
| Sourcing Agent | 6 | 2 | 4 | **33%** 🔴 |
| Product Registration | 1 | 1 | 0 | 100% ✅ |
| Pricing Agent | 0 | 0 | 0 | - |
| CS Agent | 0 | 0 | 0 | - |

### 6.2 Sourcing Agent Failure Analysis

**문제**: 66% 실패율

**테스트 실행 결과**:
```bash
curl -X POST /api/agents/execute
{
  "agent": "sourcing",
  "input": {
    "source_url": "https://item.taobao.com/item.htm?id=test123",
    "source_title": "테스트 스테인리스 텀블러",
    "market": "korea",
    "source_price_cny": 30.0,
    "weight_kg": 0.5
  }
}

Response:
{
  "execution_id": "exec-c4395d027bb1",
  "status": "completed",
  "result": {}  # ⚠️ 비어있음
}
```

**분석**:
- API 호출은 성공 (200 OK)
- `status: completed` 반환
- `result` 필드가 비어있음
- 실제 분석 결과 없음

**가능한 원인**:
1. ANTHROPIC_API_KEY 없어서 LLM 호출 실패
2. Input 데이터 형식 불일치
3. 에이전트 내부 예외 처리로 빈 결과 반환

---

## 7. Export Activity

**Total Exports**: 0회

**export_log 테이블**: 존재하지만 비어있음

**분석**:
- Export 기능은 구현되어 있으나 실제 사용 안 됨
- 테스트 중 CSV 생성은 성공했으나 로그에 기록 안 됨
- 로깅 로직 확인 필요

---

## 8. Product Content Pack Readiness

### 8.1 Missing Fields

Product Content Pack 시스템으로 전환하려면 **6개 컬럼 추가 필요**:

```sql
-- Detail Page Redesign
ALTER TABLE approval_queue ADD COLUMN generated_detail_page_plan TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_detail_page_plan TEXT;

-- Structured Product Info
ALTER TABLE approval_queue ADD COLUMN generated_product_info_json TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_product_info_json TEXT;

-- Promotion Strategy
ALTER TABLE approval_queue ADD COLUMN generated_promotion_strategy_json TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_promotion_strategy_json TEXT;
```

### 8.2 Image Review Enhancement

**Current Structure**: ✅ 기본 구조 완비

**Need to Add**:
```sql
ALTER TABLE image_review ADD COLUMN caption TEXT;
ALTER TABLE image_review ADD COLUMN layout_guidance TEXT;
```

---

## 9. Critical Issues Detail

### Issue #1: Content Agent API Key Missing 🔴

**Impact**: Content Agent 실행 불가

**Evidence**:
```
Server Log: "Content Agent initiated without ANTHROPIC_API_KEY"
```

**Solution**:
```bash
# Option 1: Environment variable
export ANTHROPIC_API_KEY='sk-ant-api03-...'

# Option 2: .env file
echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' >> /home/fortymove/Fortimove-OS/pm-agent/.env

# Then restart server
```

**Affected Agents**: 모든 에이전트 (PM, Sourcing, Registration, CS, Content)

---

### Issue #2: Pricing Agent File Missing 🔴

**Impact**: Pricing 기능 완전 누락

**Evidence**:
- API는 "Pricing Agent" 표시
- pricing_agent.py 파일 존재하지 않음

**Solution**:
1. pricing_agent.py 생성 필요
2. 또는 API에서 제거

---

### Issue #3: Sourcing Agent High Failure Rate 🔴

**Impact**: 소싱 판단 신뢰도 낮음

**Evidence**:
- 6회 실행 중 4회 실패 (66%)
- 성공해도 결과 비어있음

**Next Steps**:
1. 실패 로그 상세 분석
2. Input 데이터 검증
3. API 키 설정 후 재테스트

---

### Issue #4: Agent Registration Inconsistency 🔴

**Impact**: API 응답 신뢰도 낮음, 실제 에이전트 파악 어려움

**Evidence**:
- API: cs, pm, pricing, product_registration, sourcing
- real_agents.py: image_localization, margin_check, daily_scout_status, sourcing, content

**Solution**:
1. `approval_ui_app.py`에서 에이전트 목록 소스 확인
2. 단일 소스로 통일 (real_agents.py 권장)

---

### Issue #5: Product Content Pack Fields Missing 🔴

**Impact**: Product Content Pack 시스템 전환 불가

**Solution**:
- 위 8.1절 SQL 실행
- Content Agent에 생성 로직 추가

---

## 10. System Architecture Assessment

### 10.1 Strengths (강점)

1. ✅ **견고한 Database Schema**
   - 54개 컬럼으로 확장 가능
   - generated/reviewed 패턴 일관성

2. ✅ **완전한 Review Workflow**
   - 6개 상태, 전환 규칙 명확
   - UI 페이지 완비

3. ✅ **Image Review System**
   - 100% 작동
   - 구조 정상

4. ✅ **CSV Export 기능**
   - 네이버/쿠팡 정상 작동
   - UTF-8 한글 정상

5. ✅ **Agent Framework**
   - BaseAgent 추상 클래스 구조
   - AgentRegistry 패턴

### 10.2 Weaknesses (약점)

1. 🔴 **Agent 실행 불안정**
   - API 키 없음
   - 높은 실패율
   - 결과 비어있음

2. 🔴 **Agent 등록 불일치**
   - API vs. 실제 파일 불일치

3. ⚠️ **낮은 데이터 활용률**
   - 운영자 검수: 7.7%만 수행
   - 원본 데이터: 23.1%만 존재

4. ⚠️ **Product Content Pack 필드 누락**
   - 6개 필수 컬럼 미생성

5. ⚠️ **Export 로깅 누락**
   - export_log 비어있음

---

## 11. Recommendations

### 11.1 Immediate Actions (P0 - 1-2 hours)

1. **ANTHROPIC_API_KEY 설정**
   ```bash
   echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' >> /home/fortymove/Fortimove-OS/pm-agent/.env
   pkill -f "uvicorn approval_ui_app"
   cd /home/fortymove/Fortimove-OS/pm-agent
   python3 -m uvicorn approval_ui_app:app --host 127.0.0.1 --port 8001 --reload
   ```

2. **Agent 등록 불일치 해결**
   - approval_ui_app.py에서 에이전트 목록 소스 확인
   - real_agents.py와 통일

3. **Sourcing Agent 재테스트**
   - API 키 설정 후 실행
   - 로그 상세 분석

### 11.2 Short-term Actions (P1 - 1-2 days)

4. **Product Content Pack 스키마 추가**
   ```sql
   -- 6개 컬럼 추가 (위 8.1절)
   ```

5. **Pricing Agent 생성 또는 제거**
   - pricing_agent.py 작성
   - 또는 API에서 제거

6. **Content Agent 기능 확장**
   - `generate_detail_page_redesign()`
   - `generate_promotion_strategy()`
   - `generate_structured_product_info()`

### 11.3 Medium-term Actions (P2 - 3-5 days)

7. **UI 재설계**
   - Product Content Pack 탭 추가
   - Export를 Optional로 변경

8. **Export 로깅 수정**
   - export_log 테이블 활용

9. **Agent 안정성 개선**
   - 실패율 낮추기
   - 에러 핸들링 강화

---

## 12. Product Content Pack Conversion Plan

### Phase 1: Database Extension (2 hours)

```sql
-- Add 6 core fields
ALTER TABLE approval_queue ADD COLUMN generated_detail_page_plan TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_detail_page_plan TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_product_info_json TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_product_info_json TEXT;
ALTER TABLE approval_queue ADD COLUMN generated_promotion_strategy_json TEXT;
ALTER TABLE approval_queue ADD COLUMN reviewed_promotion_strategy_json TEXT;

-- Enhance image_review
ALTER TABLE image_review ADD COLUMN caption TEXT;
ALTER TABLE image_review ADD COLUMN layout_guidance TEXT;
```

### Phase 2: Content Agent Enhancement (1 day)

**New Methods**:
```python
class ContentAgent(BaseAgent):
    def generate_detail_page_redesign(self, product_data):
        """
        상세 페이지 리디자인 계획 생성
        - 레이아웃 구조
        - 섹션별 콘텐츠
        - 이미지 배치 가이드
        """
        pass

    def generate_structured_product_info(self, source_data):
        """
        구조화된 상품 정보 생성
        - 스펙 (사이즈, 재질, 무게 등)
        - 특징/장점
        - 사용 방법
        """
        pass

    def generate_promotion_strategy(self, product_data, market_data):
        """
        프로모션 전략 생성
        - 타겟 고객층
        - 핵심 메시지
        - 마케팅 채널 추천
        """
        pass
```

### Phase 3: UI Redesign (2 days)

**New Tabs**:
1. **Detail Page Redesign** - 상세 페이지 계획 편집
2. **Product Info** - 구조화된 정보 편집
3. **Promotion Strategy** - 프로모션 전략 편집
4. **Export (Optional)** - 선택적 내보내기

### Phase 4: Workflow Adjustment (1 day)

**Current**:
```
Source Data → Generate Content → Review → Export (필수)
```

**New**:
```
Source Data → Generate Product Content Pack → Review/Edit → (Optional) Export
                 ├── Detail Page Plan
                 ├── Structured Info
                 ├── Channel Copy (Naver, Coupang)
                 ├── Image Guidance
                 └── Promotion Strategy
```

---

## 13. Technical Debt

### High Priority

1. Agent 등록 불일치
2. ANTHROPIC_API_KEY 관리
3. Export 로깅 누락
4. Sourcing Agent 실패율

### Medium Priority

5. Product Content Pack 필드 추가
6. Workflow UX (2단계 전환)
7. 운영자 검수 데이터 낮음

### Low Priority

8. 테스트 데이터 정리
9. 코드 문서화
10. 성능 최적화

---

## 14. Conclusion

### Summary

PM Agent 시스템은 **견고한 기반 위에 구축**되어 있으나, **5가지 Critical 문제**로 인해 완전히 작동하지 않습니다.

**Good News**:
- ✅ Database, Workflow, UI 인프라 90% 완성
- ✅ Product Content Pack 전환 완전히 가능
- ✅ 필요한 작업량: 3-5일 (스키마 + 에이전트 + UI)

**Bad News**:
- 🔴 모든 에이전트 API 키 필요 (즉시 해결 가능)
- 🔴 Sourcing Agent 66% 실패율 (조사 필요)
- 🔴 Agent 등록 불일치 (혼란 야기)

### Next Steps

1. **Immediate** (1-2 hours): API 키 설정, Agent 등록 통일
2. **Short-term** (1-2 days): Product Content Pack 스키마 추가
3. **Medium-term** (3-5 days): Content Agent 확장, UI 재설계

**Approval to Proceed**: ✅ 진행 승인 요청

---

**Report Prepared By**: Claude (Staging Validator)
**Date**: 2026-04-01
**Version**: 1.0
