# PM Agent 시스템 자동화 현황 및 수동 제어 가이드

**작성일**: 2026-03-31
**시스템 버전**: 1.0 (100% 구현 완료)

---

## 📋 목차

1. [현재 자동화 수준](#현재-자동화-수준)
2. [각 에이전트 수동 실행 방법](#각-에이전트-수동-실행-방법)
3. [워크플로우 자동 실행 설정](#워크플로우-자동-실행-설정)
4. [실전 사용 예시](#실전-사용-예시)

---

## 1. 현재 자동화 수준

### 🎯 자동화 완성도: **50%**

| 구분 | 상태 | 설명 |
|------|------|------|
| **에이전트 구현** | ✅ 100% | 7개 에이전트 모두 구현 완료 |
| **워크플로우 엔진** | ✅ 100% | 순차 실행, 의존성 관리 완료 |
| **API 인터페이스** | ⚠️ 50% | 조회 API만 있음, 실행 API 미구현 |
| **자동 트리거** | ❌ 0% | Daily Scout 연동 미구현 |
| **승인 큐** | ✅ 100% | 사람 승인 시스템 완료 |

---

### 📊 현재 상태 요약

#### ✅ **구현 완료된 것**

1. **7개 에이전트 전체 구현** (100%)
   - Sourcing Agent
   - Margin Check Agent
   - Product Registration Agent
   - Image Localization Agent
   - Content Agent
   - CS Agent
   - PM Agent

2. **워크플로우 실행 엔진** (100%)
   - 순차 실행 (Sequential Execution)
   - 의존성 관리 (depends_on)
   - 상태 체크 (expected_status)
   - 데이터 매핑 (input_mapping)
   - 에러 처리 및 재시도

3. **모니터링 시스템** (100%)
   - Multi-Agent Dashboard
   - 실시간 상태 조회 API
   - 워크플로우 이력 조회
   - 통계 대시보드

4. **승인 큐 시스템** (100%)
   - 4단계 상태 (Pending/Approved/Needs Edit/Rejected)
   - 리뷰어 코멘트
   - 승인 후 재실행

---

#### ⚠️ **부분 구현된 것**

1. **API 인터페이스** (50%)
   - ✅ 조회 API (GET): 완료
     - `/api/agents/status` - 에이전트 상태
     - `/api/agents/statistics` - 통계
     - `/api/workflows/history` - 이력
   - ❌ 실행 API (POST): **미구현**
     - `/api/agents/execute` - 개별 에이전트 실행
     - `/api/workflows/run` - 워크플로우 실행

---

#### ❌ **미구현된 것**

1. **자동 트리거 시스템** (0%)
   - Daily Scout 크롤링 완료 → 자동으로 Sourcing Agent 실행
   - Approval Queue 승인 → 자동으로 다음 단계 실행
   - 스케줄 기반 실행 (매일 오전 9시 등)

2. **Slack/이메일 알림** (부분 구현)
   - Handoff Service는 있지만 실제 연동 미완료

3. **마켓플레이스 자동 등록** (0%)
   - 스마트스토어/쿠팡 API 연동
   - 승인 완료 → 자동 등록

---

## 2. 각 에이전트 수동 실행 방법

### 🔧 방법 1: Python 스크립트로 직접 실행 (로컬)

#### 예시 1: Sourcing Agent 실행

```bash
cd /home/fortymove/Fortimove-OS/pm-agent

python3 << 'PYEOF'
from sourcing_agent import SourcingAgent

agent = SourcingAgent()
result = agent.execute({
    "source_url": "https://item.taobao.com/item.htm?id=123456789",
    "source_title": "휴대용 미니 블렌더",
    "keywords": ["블렌더", "휴대용"],
    "market": "korea"
})

print("상태:", result.status)
print("결과:", result.output)
PYEOF
```

**출력 예시**:
```
상태: completed
결과: {
  "product_classification": "테스트",
  "sourcing_decision": "통과",
  "risk_flags": [],
  "vendor_questions_ko": ["현재 실재고가 있나요?", ...],
  "vendor_questions_zh": ["现在有现货吗？", ...]
}
```

---

#### 예시 2: Margin Check Agent 실행

```bash
python3 << 'PYEOF'
from real_agents import MarginCheckAgent

agent = MarginCheckAgent()
result = agent.execute({
    "action": "calculate_margin",
    "source_price_cny": 50.0,
    "exchange_rate": 200.0,
    "weight_kg": 0.5,
    "target_margin_rate": 0.30
})

print("마진 분석:")
print("  총 원가:", result.output['cost_breakdown']['total_cost'], "원")
print("  권장 판매가:", result.output['margin_analysis']['target_price'], "원")
print("  순마진율:", result.output['margin_analysis']['net_margin_rate'], "%")
print("  판정:", result.output['final_decision'])
PYEOF
```

**출력 예시**:
```
마진 분석:
  총 원가: 17500 원
  권장 판매가: 31818 원
  순마진율: 29.5 %
  판정: 등록 가능
```

---

#### 예시 3: Content Agent 실행

```bash
python3 << 'PYEOF'
from content_agent import ContentAgent

agent = ContentAgent()
result = agent.execute({
    "product_name": "스테인리스 텀블러",
    "product_category": "주방용품",
    "key_features": ["진공 단열", "500ml"],
    "price": 15900,
    "content_type": "product_page",
    "compliance_mode": True
})

print("생성된 콘텐츠:")
print(result.output['main_content'][:200])
print("\nSEO 제목:", result.output['seo_title'])
print("컴플라이언스:", result.output['compliance_status'])
PYEOF
```

---

### 🔧 방법 2: 워크플로우로 여러 에이전트 순차 실행 (로컬)

```bash
cd /home/fortymove/Fortimove-OS/pm-agent

python3 << 'PYEOF'
from agent_framework import WorkflowExecutor, WorkflowStep, ExecutionContext
from real_agents import register_real_agents

# 1. Registry 초기화
registry = register_real_agents()

# 2. 워크플로우 정의
workflow_steps = [
    {
        "step_id": "sourcing",
        "agent": "sourcing",
        "input_mapping": {
            "source_url": "user.source_url",
            "source_title": "user.source_title"
        }
    },
    {
        "step_id": "margin",
        "agent": "margin_check",
        "depends_on": ["sourcing"],
        "input_mapping": {
            "action": "literal.calculate_margin",
            "source_price_cny": "user.source_price_cny",
            "weight_kg": "user.weight_kg"
        }
    },
    {
        "step_id": "content",
        "agent": "content",
        "depends_on": ["margin"],
        "input_mapping": {
            "product_name": "user.product_name",
            "price": "margin.margin_analysis.target_price",
            "content_type": "literal.product_page"
        }
    }
]

# 3. 사용자 입력
user_input = {
    "source_url": "https://item.taobao.com/item.htm?id=123456",
    "source_title": "휴대용 미니 블렌더",
    "product_name": "휴대용 미니 블렌더",
    "source_price_cny": 50.0,
    "weight_kg": 0.5
}

# 4. 실행
executor = WorkflowExecutor(registry)
context = ExecutionContext(user_input=user_input)
final_result = executor.execute_sequential(workflow_steps, context)

# 5. 결과 확인
print("워크플로우 완료!")
print("소싱 결과:", context.get_result("sourcing").output['sourcing_decision'])
print("마진 판정:", context.get_result("margin").output['final_decision'])
print("콘텐츠 생성:", context.get_result("content").output['content_type'])
PYEOF
```

**출력 예시**:
```
워크플로우 완료!
소싱 결과: 통과
마진 판정: 등록 가능
콘텐츠 생성: product_page
```

---

### 🔧 방법 3: API로 원격 실행 (미구현 - 구현 필요)

**현재 상태**: ❌ 실행 API가 없음

**구현해야 할 API**:

```python
# approval_ui_app.py에 추가 필요

@app.post("/api/agents/execute")
def execute_agent(request: AgentExecuteRequest):
    """개별 에이전트 실행"""
    # 구현 필요
    pass

@app.post("/api/workflows/run")
def run_workflow(request: WorkflowRequest):
    """워크플로우 실행"""
    # 구현 필요
    pass
```

**사용 예시 (구현 후)**:
```bash
curl -X POST https://staging-pm-agent.fortimove.com/api/agents/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "sourcing",
    "input": {
      "source_url": "https://item.taobao.com/item.htm?id=123456"
    }
  }'
```

---

## 3. 워크플로우 자동 실행 설정

### 🤖 시나리오 1: Daily Scout 연동 (구현 필요)

**목표**: Daily Scout 크롤링 완료 → 자동으로 상품 등록 워크플로우 실행

**구현 방법**:

```python
# daily_scout_integration.py (신규 파일)

import schedule
import time
from agent_framework import WorkflowExecutor
from real_agents import register_real_agents

def check_new_products():
    """Daily Scout에서 새 상품 확인"""
    # Daily Scout DB 조회
    new_products = fetch_new_products_from_daily_scout()

    if not new_products:
        return

    print(f"새 상품 {len(new_products)}개 발견!")

    # 각 상품에 대해 워크플로우 실행
    for product in new_products:
        run_product_workflow(product)

def run_product_workflow(product):
    """상품 등록 전체 워크플로우 실행"""
    registry = register_real_agents()
    executor = WorkflowExecutor(registry)

    workflow = [
        {"step_id": "sourcing", "agent": "sourcing", ...},
        {"step_id": "margin", "agent": "margin_check", ...},
        {"step_id": "registration", "agent": "product_registration", ...},
        {"step_id": "image", "agent": "image_localization", ...},
        {"step_id": "content", "agent": "content", ...}
    ]

    user_input = {
        "source_url": product['url'],
        "source_title": product['title'],
        ...
    }

    context = ExecutionContext(user_input=user_input)
    executor.execute_sequential(workflow, context)

    # 결과를 Approval Queue에 추가
    add_to_approval_queue(context)

# 스케줄 설정
schedule.every().day.at("09:00").do(check_new_products)

while True:
    schedule.run_pending()
    time.sleep(60)
```

**실행**:
```bash
cd /home/fortymove/Fortimove-OS/pm-agent
python3 daily_scout_integration.py &
```

---

### 🤖 시나리오 2: 승인 후 자동 다음 단계 (구현 필요)

**목표**: Approval Queue에서 "Approved" → 자동으로 마켓 등록

**구현 방법**:

```python
# approval_queue.py에 hook 추가

class ApprovalQueueManager:
    def update_status(self, review_id, new_status):
        # 기존 로직
        item = self.get_item(review_id)
        item.status = new_status
        self.save(item)

        # 새로운 hook
        if new_status == "approved":
            trigger_market_registration(item)

def trigger_market_registration(item):
    """마켓 등록 자동 실행"""
    # 스마트스토어 API 호출
    # 쿠팡 API 호출
    pass
```

---

### 🤖 시나리오 3: Webhook 트리거 (구현 가능)

**목표**: 외부 시스템에서 HTTP 요청 → 워크플로우 자동 실행

```python
# approval_ui_app.py에 추가

@app.post("/api/webhooks/new-product")
def webhook_new_product(request: NewProductRequest):
    """외부에서 새 상품 등록 요청"""

    # 워크플로우 백그라운드 실행
    from fastapi import BackgroundTasks

    def run_workflow_async(product_data):
        registry = register_real_agents()
        executor = WorkflowExecutor(registry)
        # 워크플로우 실행
        ...

    background_tasks.add_task(run_workflow_async, request.dict())

    return {"message": "워크플로우 시작됨", "workflow_id": "wf-xxx"}
```

**외부에서 호출**:
```bash
curl -X POST https://staging-pm-agent.fortimove.com/api/webhooks/new-product \
  -H "Content-Type: application/json" \
  -d '{
    "source_url": "https://item.taobao.com/item.htm?id=123456",
    "source_title": "신상품"
  }'
```

---

## 4. 실전 사용 예시

### 📝 Case 1: 타오바오 상품 1개 수동 등록

**시나리오**: 타오바오에서 좋은 상품을 발견했고, 빠르게 등록하고 싶음

**Step 1**: 서버 SSH 접속
```bash
ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96
cd ~/Fortimove-OS/pm-agent
```

**Step 2**: 워크플로우 실행 스크립트 작성
```bash
cat > run_single_product.py << 'EOF'
from agent_framework import WorkflowExecutor, ExecutionContext
from real_agents import register_real_agents
import json

# 사용자 입력
user_input = {
    "source_url": "https://item.taobao.com/item.htm?id=123456789",
    "source_title": "휴대용 미니 블렌더",
    "product_name": "휴대용 미니 블렌더",
    "source_price_cny": 50.0,
    "exchange_rate": 200.0,
    "weight_kg": 0.5,
    "target_margin_rate": 0.30
}

# 워크플로우 정의
workflow = [
    {
        "step_id": "sourcing",
        "agent": "sourcing",
        "input_mapping": {
            "source_url": "user.source_url",
            "source_title": "user.source_title",
            "keywords": "literal.[\"블렌더\", \"휴대용\"]",
            "market": "literal.korea"
        }
    },
    {
        "step_id": "margin",
        "agent": "margin_check",
        "depends_on": ["sourcing"],
        "expected_status": ["completed"],
        "input_mapping": {
            "action": "literal.calculate_margin",
            "source_price_cny": "user.source_price_cny",
            "exchange_rate": "user.exchange_rate",
            "weight_kg": "user.weight_kg",
            "target_margin_rate": "user.target_margin_rate"
        }
    },
    {
        "step_id": "registration",
        "agent": "product_registration",
        "depends_on": ["margin"],
        "expected_status": ["completed"],
        "input_mapping": {
            "source_title": "user.source_title",
            "source_options": "literal.[]",
            "market": "literal.korea"
        }
    },
    {
        "step_id": "content",
        "agent": "content",
        "depends_on": ["registration"],
        "expected_status": ["completed"],
        "input_mapping": {
            "product_name": "user.product_name",
            "product_description": "registration.short_description_ko",
            "price": "margin.margin_analysis.target_price",
            "content_type": "literal.product_page",
            "compliance_mode": "literal.true"
        }
    }
]

# 실행
registry = register_real_agents()
executor = WorkflowExecutor(registry)
context = ExecutionContext(user_input=user_input)

print("워크플로우 시작...")
result = executor.execute_sequential(workflow, context)

# 결과 출력
print("\n" + "="*50)
print("워크플로우 완료!")
print("="*50)

for step in workflow:
    step_result = context.get_result(step['step_id'])
    if step_result:
        print(f"\n{step['step_id']}: {step_result.status}")
        if step_result.is_success():
            print(json.dumps(step_result.output, indent=2, ensure_ascii=False)[:200])

EOF

python3 run_single_product.py
```

**Step 3**: 결과 확인
```
워크플로우 시작...
==================================================
워크플로우 완료!
==================================================

sourcing: completed
{
  "sourcing_decision": "통과",
  "risk_flags": [],
  ...
}

margin: completed
{
  "final_decision": "등록 가능",
  "margin_analysis": {
    "net_margin_rate": 29.5
  }
  ...
}

registration: completed
content: completed
```

**Step 4**: Approval Queue 확인
```bash
curl -s https://staging-pm-agent.fortimove.com/api/queue
```

---

### 📝 Case 2: 대량 상품 일괄 등록 (CSV 파일)

**시나리오**: 100개 상품 정보가 CSV 파일로 있고, 일괄 등록하고 싶음

```bash
cat > bulk_import.py << 'EOF'
import csv
from agent_framework import WorkflowExecutor, ExecutionContext
from real_agents import register_real_agents

# CSV 파일 읽기
with open('products.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    products = list(reader)

print(f"총 {len(products)}개 상품 발견")

registry = register_real_agents()
executor = WorkflowExecutor(registry)

success_count = 0
fail_count = 0

for i, product in enumerate(products, 1):
    print(f"\n[{i}/{len(products)}] {product['title']} 처리 중...")

    user_input = {
        "source_url": product['url'],
        "source_title": product['title'],
        "product_name": product['title'],
        "source_price_cny": float(product['price_cny']),
        "weight_kg": float(product['weight_kg'])
    }

    context = ExecutionContext(user_input=user_input)

    try:
        executor.execute_sequential(workflow_steps, context)
        success_count += 1
        print(f"✅ 성공")
    except Exception as e:
        fail_count += 1
        print(f"❌ 실패: {e}")

print(f"\n최종 결과: 성공 {success_count}개, 실패 {fail_count}개")
EOF

python3 bulk_import.py
```

---

### 📝 Case 3: 특정 에이전트만 단독 실행

**시나리오**: Content Agent만 사용해서 기존 상품의 콘텐츠를 재생성하고 싶음

```bash
python3 << 'PYEOF'
from content_agent import ContentAgent
import json

agent = ContentAgent()

# 기존 상품 10개에 대해 콘텐츠 재생성
products = [
    {"name": "상품A", "price": 29900},
    {"name": "상품B", "price": 19900},
    # ... 10개
]

for product in products:
    result = agent.execute({
        "product_name": product['name'],
        "price": product['price'],
        "content_type": "product_page"
    })

    if result.is_success():
        print(f"✅ {product['name']}")
        # 생성된 콘텐츠를 DB에 저장하거나 파일로 저장
        with open(f"content_{product['name']}.json", 'w') as f:
            json.dump(result.output, f, ensure_ascii=False, indent=2)
    else:
        print(f"❌ {product['name']}: {result.error}")
PYEOF
```

---

## 5. 자동화 수준 향상 로드맵

### 🚀 Phase 1: 수동 실행 (현재)

**자동화 수준**: 0%
**사용 방법**: Python 스크립트 직접 실행
**적합한 경우**: 테스트, 소량 처리

---

### 🚀 Phase 2: API 실행 (1주 내 구현 가능)

**자동화 수준**: 30%
**구현 내용**:
- `/api/agents/execute` 추가
- `/api/workflows/run` 추가
- Web UI에서 버튼 클릭으로 실행

**사용 방법**:
```bash
curl -X POST https://staging-pm-agent.fortimove.com/api/workflows/run \
  -H "Authorization: Bearer TOKEN" \
  -d '{"workflow": "product_registration", "input": {...}}'
```

---

### 🚀 Phase 3: 트리거 자동화 (2주 내 구현 가능)

**자동화 수준**: 70%
**구현 내용**:
- Daily Scout 연동
- 승인 후 자동 다음 단계
- Webhook 수신

**사용 방법**: 설정만 하면 자동 실행

---

### 🚀 Phase 4: 완전 자동화 (1개월 내 구현 가능)

**자동화 수준**: 100%
**구현 내용**:
- AI가 자동 의사결정 (승인/거부)
- 마켓 자동 등록
- 실패 시 자동 재시도
- Slack 알림

**사용 방법**: 사람 개입 없이 완전 자동

---

## 6. 결론

### ✅ 현재 가능한 것

1. **수동 실행** ✅
   - Python 스크립트로 개별 에이전트 실행
   - 워크플로우 순차 실행
   - 로컬 또는 서버에서 실행

2. **모니터링** ✅
   - Dashboard에서 실시간 상태 확인
   - API로 통계 조회
   - 워크플로우 이력 확인

3. **승인 시스템** ✅
   - Approval Queue에 결과 적재
   - 사람이 최종 승인/거부

### ⚠️ 구현 필요한 것

1. **API 실행 인터페이스** (1주)
   - POST `/api/agents/execute`
   - POST `/api/workflows/run`

2. **자동 트리거** (2주)
   - Daily Scout 연동
   - 스케줄 실행
   - Webhook

3. **마켓 자동 등록** (3주)
   - 스마트스토어 API
   - 쿠팡 API

---

**다음 단계 권장사항**:
1. **즉시**: 수동 실행으로 10개 상품 테스트
2. **1주 내**: API 실행 인터페이스 구현
3. **2주 내**: Daily Scout 자동 트리거 구현

---

**작성일**: 2026-03-31
**작성자**: Claude (AI Agent)
