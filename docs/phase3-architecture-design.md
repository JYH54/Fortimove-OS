# Phase 3 Architecture Design & Feasibility Analysis

**날짜**: 2026-03-31
**목표**: Daily Scout → Auto-Scoring → Approval Review → Content Generation → Upload Validation → Semi-Auto Upload

---

## 📋 요구사항 분석

### 1. Auto-Scoring Integration
**목적**: Daily Scout 크롤링 후 자동 채점 및 decision 생성

**요구사항**:
- Daily Scout가 `wellness_products`에 신규 상품 저장 시 자동 트리거
- `scoring_engine.py` 실행 → `approval_queue`에 저장
- `decision`이 `review` 또는 `auto_approve`일 때만 `content_agent` 실행
- `reject`/`hold`는 콘텐츠 생성 금지
- Retry 가능 구조

**구현 방안**:
```python
# daily_scout_integration.py 확장
def process_new_product(product_id):
    # 1. Get product from wellness_products
    product = get_wellness_product(product_id)

    # 2. Score product
    scoring_result = scoring_engine.score_product(product)

    # 3. Save to approval_queue
    review_id = approval_queue.add_item({
        "score": scoring_result['score'],
        "decision": scoring_result['decision'],
        "priority": scoring_result['priority'],
        "reasons_json": json.dumps(scoring_result['reasons'])
    })

    # 4. If decision == review or auto_approve, generate content
    if scoring_result['decision'] in ['review', 'auto_approve']:
        content_result = content_agent.execute_multichannel(product)
        # Save to channel_upload_queue
```

**에이전트 충돌 여부**: ✅ **충돌 없음** (sequential flow)

---

### 2. Dashboard Integration

**목적**: Approval Queue 및 Upload Queue 관리 UI

**필요 API 엔드포인트**:

#### Approval Queue APIs
```python
GET  /api/approval/list?status=pending&sort=priority
GET  /api/approval/{review_id}
POST /api/approval/{review_id}/approve
POST /api/approval/{review_id}/reject
POST /api/approval/{review_id}/hold
POST /api/approval/{review_id}/rescore
POST /api/approval/{review_id}/regenerate-content
```

#### Upload Queue APIs
```python
GET  /api/upload/list?channel=naver&status=pending
GET  /api/upload/{upload_id}
POST /api/upload/{upload_id}/validate
POST /api/upload/{upload_id}/retry
POST /api/upload/{upload_id}/export
```

**UI 컴포넌트**:
- Approval Queue Table (score, decision, priority, reasons, actions)
- Upload Queue Table (channel, status, retry_count, error_message)
- Detail Modal (full review data + content preview)
- Filter/Sort/Search controls

**에이전트 충돌 여부**: ✅ **충돌 없음** (UI layer만 추가)

---

### 3. Upload Validation Layer

**목적**: 채널별 업로드 전 규칙 기반 검증

**검증 항목**:

#### Naver 검증
```python
def validate_naver(content):
    errors = []

    # 제목 길이 (50자 이내)
    if len(content['title']) > 50:
        errors.append("제목 50자 초과")

    # 금지어 검사
    prohibited_words = ["의료기기", "치료", "질병", "FDA", "특허"]
    for word in prohibited_words:
        if word in content['title'] or word in content['description']:
            errors.append(f"금지어 포함: {word}")

    # 가격 (최소 1000원)
    if content['price'] < 1000:
        errors.append("최소 가격 미달")

    # 옵션 (최대 100개)
    if len(content.get('options', [])) > 100:
        errors.append("옵션 100개 초과")

    # 이미지 (최소 1장)
    if len(content.get('images', [])) < 1:
        errors.append("이미지 없음")

    return {"valid": len(errors) == 0, "errors": errors}
```

#### Coupang 검증
```python
def validate_coupang(content):
    errors = []

    # 제목 길이 (100자 이내)
    if len(content['title']) > 100:
        errors.append("제목 100자 초과")

    # 금지어 검사 (Naver와 동일)

    # 로켓배송 문구 필수
    if "오늘출발" not in content['title']:
        errors.append("배송 태그 누락")

    # 반품 정책 필수
    if not content.get('return_policy'):
        errors.append("반품 정책 누락")

    return {"valid": len(errors) == 0, "errors": errors}
```

**LLM 사용량**: 0% (100% rule-based)

**에이전트 충돌 여부**: ✅ **충돌 없음** (독립 모듈)

---

### 4. Semi-Auto Upload Flow

**목적**: 자동 업로드가 아닌 검토-승인-업로드 구조

**Flow**:
```
1. Content Generation → channel_upload_queue (status: pending)
2. Validation → status: validated / validation_failed
3. Operator Review → status: ready_to_upload
4. Export/Upload → status: uploading / completed / failed
```

**상태 전이 규칙**:
```
pending → validating → validated → ready_to_upload → uploading → completed
          ↓                 ↓              ↓              ↓
      validation_failed   hold          cancelled      failed → retry
```

**에이전트 충돌 여부**: ✅ **충돌 없음** (state machine)

---

### 5. DB Schema 확장

**approval_queue 확장**:
```sql
ALTER TABLE approval_queue ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE approval_queue ADD COLUMN last_error TEXT;
ALTER TABLE approval_queue ADD COLUMN validated_at TEXT;
ALTER TABLE approval_queue ADD COLUMN approved_at TEXT;
ALTER TABLE approval_queue ADD COLUMN approved_by TEXT;
ALTER TABLE approval_queue ADD COLUMN audit_trail TEXT; -- JSON array
```

**channel_upload_queue 확장**:
```sql
ALTER TABLE channel_upload_queue ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE channel_upload_queue ADD COLUMN last_error TEXT;
ALTER TABLE channel_upload_queue ADD COLUMN validation_status TEXT DEFAULT 'pending';
ALTER TABLE channel_upload_queue ADD COLUMN validation_errors TEXT; -- JSON array
ALTER TABLE channel_upload_queue ADD COLUMN validated_at TEXT;
ALTER TABLE channel_upload_queue ADD COLUMN ready_at TEXT;
ALTER TABLE channel_upload_queue ADD COLUMN export_data TEXT; -- JSON for export
```

**audit_log 테이블 (신규)**:
```sql
CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- 'approval', 'upload'
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'approve', 'reject', 'rescore', 'validate', etc.
    old_status TEXT,
    new_status TEXT,
    actor TEXT,  -- 'system' or user_id
    reason TEXT,
    metadata TEXT,  -- JSON
    created_at TEXT NOT NULL
);
```

**DB 충돌 여부**: ✅ **충돌 없음** (ALTER TABLE만 사용)

---

## 🏗️ 시스템 아키텍처

### 전체 파이프라인
```
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 3 PIPELINE                             │
└─────────────────────────────────────────────────────────────────────┘

[1] Daily Scout Crawler
          ↓
    wellness_products DB
          ↓
[2] Auto-Scoring Trigger ← scoring_engine.py
          ↓
    approval_queue (score, decision, priority)
          ↓
    ┌────────────────────────┐
    │  decision check        │
    ├────────────────────────┤
    │ reject/hold → STOP     │
    │ review/auto_approve →  │
    └────────────────────────┘
          ↓
[3] Content Agent (Multi-Channel) ← content_agent.py
          ↓
    channel_upload_queue (pending)
          ↓
[4] Upload Validation ← upload_validator.py
          ↓
    validation_status: validated / validation_failed
          ↓
[5] Dashboard Review
          ↓
    Operator Action: approve → ready_to_upload
          ↓
[6] Export or API Upload
          ↓
    status: uploading → completed / failed
```

### 모듈 구조
```
pm-agent/
├── scoring_engine.py          (Phase 2) ✅
├── approval_ranker.py         (Phase 2) ✅
├── content_agent.py           (Phase 2) ✅
├── channel_upload_manager.py  (Phase 2) ✅
│
├── auto_scoring_trigger.py    (Phase 3) ← NEW
├── upload_validator.py        (Phase 3) ← NEW
├── semi_auto_uploader.py      (Phase 3) ← NEW
├── approval_ui_app.py         (확장)
│
└── migrations/
    └── 003_phase3_schema.sql  (Phase 3) ← NEW
```

---

## 🔄 데이터 흐름

### 1. Auto-Scoring Flow
```python
# daily_scout_integration.py
def on_new_product_saved(product_id):
    try:
        # Get product data
        product = db.get_wellness_product(product_id)

        # Transform to review format
        review_data = transform_to_review_format(product)

        # Score it
        scoring_result = scoring_engine.score_product(review_data)

        # Save to approval_queue
        review_id = approval_queue.add_item({
            "source_id": product_id,
            "source_type": "wellness_products",
            "score": scoring_result['score'],
            "decision": scoring_result['decision'],
            "priority": scoring_result['priority'],
            "reasons_json": json.dumps(scoring_result['reasons']),
            "scoring_updated_at": datetime.now().isoformat()
        })

        # Log audit
        audit_log.log("approval", review_id, "auto_scored", actor="system")

        # If decision allows content generation
        if scoring_result['decision'] in ['review', 'auto_approve']:
            generate_content_async(review_id, product)

        # Update wellness_products status
        db.update_wellness_product(product_id, {
            "workflow_status": "scored",
            "review_id": review_id
        })

    except Exception as e:
        logger.error(f"Auto-scoring failed for {product_id}: {e}")
        # Retry logic
        retry_queue.add(product_id, retry_count=1)
```

### 2. Content Generation Flow
```python
def generate_content_async(review_id, product):
    try:
        # Get approval queue item
        review = approval_queue.get_item(review_id)

        # Generate content
        content_input = {
            "product_name": product['product_name'],
            "product_category": product.get('category'),
            "key_features": extract_features(product),
            "price": product.get('price'),
            "channels": ["naver", "coupang"],
            "compliance_mode": True
        }

        content_result = content_agent.execute_multichannel(content_input)

        # Create upload queue items for each channel
        for channel in ["naver", "coupang"]:
            upload_manager.add_upload_item(
                review_id=review_id,
                channel=channel,
                content={
                    f"{channel}_title": content_result[f"{channel}_title"],
                    "description": content_result.get('detail_description'),
                    "usp_points": content_result.get('usp_points'),
                    "seo_tags": content_result.get('seo_tags'),
                    "images": product.get('images', []),
                    "price": product.get('price'),
                    "options": product.get('options', [])
                }
            )

        # Update approval_queue content_status
        approval_queue.update_item(review_id, {
            "content_status": "completed"
        })

        # Log audit
        audit_log.log("approval", review_id, "content_generated", actor="system")

    except Exception as e:
        logger.error(f"Content generation failed for {review_id}: {e}")
        approval_queue.update_item(review_id, {
            "content_status": "failed",
            "last_error": str(e)
        })
```

### 3. Validation Flow
```python
def validate_upload_item(upload_id):
    try:
        # Get upload item
        item = upload_manager.get_upload_by_id(upload_id)
        channel = item['channel']
        content = json.loads(item['content_json'])

        # Validate
        validator = UploadValidator()
        validation_result = validator.validate(channel, content)

        # Update status
        upload_manager.update_validation_status(
            upload_id,
            status="validated" if validation_result['valid'] else "validation_failed",
            errors=validation_result.get('errors', [])
        )

        # Log audit
        audit_log.log("upload", upload_id, "validated",
                     metadata={"valid": validation_result['valid']})

        return validation_result

    except Exception as e:
        logger.error(f"Validation failed for {upload_id}: {e}")
        upload_manager.update_validation_status(upload_id, "validation_error", [str(e)])
```

---

## 🛡️ Fail-Safe & Retry Strategy

### 1. Scoring Retry
```python
def retry_scoring(review_id, max_retries=3):
    review = approval_queue.get_item(review_id)

    if review['retry_count'] >= max_retries:
        logger.error(f"Max retries reached for {review_id}")
        approval_queue.update_item(review_id, {
            "decision": "hold",
            "last_error": "Max retries exceeded"
        })
        return

    try:
        scoring_result = scoring_engine.score_product(review)
        approval_queue.update_item(review_id, {
            "score": scoring_result['score'],
            "decision": scoring_result['decision'],
            "retry_count": review['retry_count'] + 1,
            "last_error": None
        })
    except Exception as e:
        approval_queue.update_item(review_id, {
            "retry_count": review['retry_count'] + 1,
            "last_error": str(e)
        })
```

### 2. Content Generation Retry
```python
def retry_content_generation(review_id, max_retries=3):
    review = approval_queue.get_item(review_id)

    if review['retry_count'] >= max_retries:
        approval_queue.update_item(review_id, {
            "content_status": "failed_permanent",
            "last_error": "Max retries exceeded"
        })
        return

    try:
        generate_content_async(review_id, review)
    except Exception as e:
        approval_queue.update_item(review_id, {
            "retry_count": review['retry_count'] + 1,
            "last_error": str(e)
        })
```

### 3. Upload Retry
```python
def retry_upload(upload_id, max_retries=5):
    item = upload_manager.get_upload_by_id(upload_id)

    if item['retry_count'] >= max_retries:
        upload_manager.update_status(upload_id, "failed_permanent",
                                     error="Max retries exceeded")
        return

    try:
        # Re-validate first
        validation_result = validate_upload_item(upload_id)

        if not validation_result['valid']:
            upload_manager.update_status(upload_id, "validation_failed",
                                        error=validation_result['errors'])
            return

        # Attempt upload (export or API)
        upload_result = perform_upload(upload_id)

        upload_manager.update_status(upload_id, "completed")

    except Exception as e:
        upload_manager.update_status(upload_id, "failed", error=str(e))
        upload_manager.increment_retry_count(upload_id)
```

---

## 📊 Implementation Plan

### Phase 3.1: DB Schema & Infrastructure (Day 1)
- [ ] `migrations/003_phase3_schema.sql` 작성
- [ ] `audit_log` 테이블 생성
- [ ] `approval_queue`, `channel_upload_queue` 확장
- [ ] Migration 실행 및 검증

### Phase 3.2: Auto-Scoring Integration (Day 2)
- [ ] `auto_scoring_trigger.py` 구현
- [ ] Daily Scout integration 수정
- [ ] Retry logic 구현
- [ ] 단위 테스트

### Phase 3.3: Upload Validation (Day 2-3)
- [ ] `upload_validator.py` 구현
- [ ] Naver 검증 규칙
- [ ] Coupang 검증 규칙
- [ ] 금지어 DB 구축
- [ ] 단위 테스트

### Phase 3.4: Dashboard APIs (Day 3-4)
- [ ] Approval Queue APIs (list, get, approve, reject, rescore)
- [ ] Upload Queue APIs (list, get, validate, retry, export)
- [ ] Filter/Sort/Search 구현
- [ ] API 테스트

### Phase 3.5: Semi-Auto Upload Flow (Day 4-5)
- [ ] `semi_auto_uploader.py` 구현
- [ ] Export to CSV/Excel
- [ ] State machine 구현
- [ ] Audit logging
- [ ] 통합 테스트

### Phase 3.6: End-to-End Testing (Day 5-6)
- [ ] Daily Scout → Auto-Scoring 테스트
- [ ] Approval Review 테스트
- [ ] Content Generation 테스트
- [ ] Validation 테스트
- [ ] Upload Export 테스트
- [ ] Retry scenarios 테스트

---

## ⚠️ 리스크 및 완화 방안

### Risk 1: Daily Scout와 Scoring Engine 동기화
**리스크**: Daily Scout가 대량 크롤링 시 scoring engine 병목

**완화 방안**:
- Celery 또는 asyncio 기반 비동기 처리
- Batch scoring (10개씩 묶어서 처리)
- Rate limiting (초당 5개)

### Risk 2: Content Generation 실패
**리스크**: LLM API 장애 또는 rate limit

**완화 방안**:
- 80% 템플릿 기반으로 LLM 의존도 최소화
- Retry with exponential backoff
- Fallback to template-only mode

### Risk 3: Validation 규칙 변경
**리스크**: Naver/Coupang 정책 변경

**완화 방안**:
- 검증 규칙을 `channel_configs` 테이블에 JSON으로 저장
- Hot reload 지원 (재배포 없이 규칙 변경)
- Version control for rules

### Risk 4: 수동 승인 병목
**리스크**: 운영자가 모든 항목을 수동 승인하면 업로드 지연

**완화 방안**:
- `auto_approve` decision (score 80+)은 자동 ready_to_upload
- `review` decision만 수동 검토 필요
- Batch approve 기능 (한 번에 10개 승인)

---

## 🎯 Success Metrics

### Performance Metrics
- Auto-scoring 처리 속도: 평균 100ms 이내
- Content generation 처리 속도: 평균 500ms 이내 (템플릿 모드)
- Validation 처리 속도: 평균 50ms 이내
- End-to-end latency: Daily Scout → Ready to Upload < 5초

### Quality Metrics
- Scoring accuracy: 수동 검증 대비 85% 일치
- Validation error rate: < 5%
- Retry success rate: > 90% (2회 이내)

### Operational Metrics
- Auto-approve rate: 30-40% (score 80+)
- Manual review rate: 50-60% (score 60-79)
- Reject rate: < 10% (score < 60)

---

## ✅ Feasibility Assessment

| 요구사항 | 실현 가능성 | 복잡도 | 예상 소요 시간 |
|---------|-----------|--------|--------------|
| Auto-Scoring Integration | ✅ High | Medium | 1일 |
| Dashboard APIs | ✅ High | Medium | 1.5일 |
| Upload Validation | ✅ High | Low | 1일 |
| Semi-Auto Upload | ✅ High | Medium | 1.5일 |
| DB Schema 확장 | ✅ High | Low | 0.5일 |
| End-to-End Testing | ✅ High | High | 1.5일 |

**Total Estimated Time**: 6-7 working days

**에이전트 충돌**: ✅ **없음** (모두 sequential flow 또는 독립 모듈)

**LLM 의존도**: ✅ **최소화** (Auto-scoring 0%, Validation 0%, Content 20%)

**Fail-Safe**: ✅ **보장** (retry logic + state machine)

**Explainability**: ✅ **보장** (audit_log + reasons_json)

---

## 🚀 Recommendation

**Phase 3 개발 진행 권장사항**: ✅ **즉시 시작 가능**

**우선순위**:
1. DB Schema 확장 (필수 인프라)
2. Auto-Scoring Integration (핵심 기능)
3. Upload Validation (품질 보증)
4. Dashboard APIs (운영 효율성)
5. Semi-Auto Upload (최종 단계)

**개발 순서**: 위 순서대로 sequential 진행 (병렬 불가능)

---

**작성일**: 2026-03-31
**작성자**: Claude (PM Agent System)
**문서 버전**: 1.0
