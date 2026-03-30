# PM/기획 에이전트 (Project Manager Agent)

Fortimove 에이전트 시스템의 **컨트롤 타워**

## 역할

PM 에이전트는 사용자의 무작위한 요청을 분석하여 적절한 후속 에이전트로 자동 라우팅하는 컨트롤 타워입니다.

### 핵심 기능

1. **요청 자동 분류**: 소싱/등록/마진/CS 등 작업 유형 자동 판별
2. **작업 분해**: 복합 요청을 단위 작업으로 분해
3. **우선순위 지정**: P0(긴급) ~ P3(낮음) 자동 할당
4. **에이전트 라우팅**: 6개 전문 에이전트로 자동 핸드오프
5. **워크플로우 설계**: 순차/병렬 실행 경로 자동 생성

## 설치

```bash
cd /home/fortymove/Fortimove-OS/pm-agent
pip install -r requirements.txt
```

## 환경 변수 설정

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## 사용법

### CLI 모드

```bash
python pm_agent.py "타오바오 무선 이어폰 링크 분석해줘"
```

### Python 모듈로 사용

```python
from pm_agent import PMAgent

pm = PMAgent()

# 요청 분석
result = pm.execute_workflow("고객이 배송 지연 클레임 넣었어")

# 결과 출력
print(pm.format_output(result))
```

## 사용 예시

### 예시 1: 신규 소싱

**입력**:
```
타오바오 링크: https://item.taobao.com/item.htm?id=123456
이 상품 소싱 가능한지 확인해줘. 원가는 30위안이야.
```

**PM 분석 결과**:
```json
{
  "task_type": "sourcing",
  "summary": "타오바오 상품 소싱 가능성 검토 및 마진 계산",
  "subtasks": [
    {
      "task_id": "T001",
      "agent": "sourcing",
      "priority": "p1",
      "description": "리스크 1차 필터링 (통관/지재권/의료기기)"
    },
    {
      "task_id": "T002",
      "agent": "margin",
      "priority": "p1",
      "description": "수익성 검증 (원가 30위안 기준)"
    }
  ],
  "workflow": [
    {"step": 1, "agent": "sourcing", "condition": "항상"},
    {"step": 2, "agent": "margin", "condition": "소싱 통과 시"}
  ]
}
```

**실행 순서**:
1. `sourcing` 에이전트 → 리스크 판정
2. `margin` 에이전트 → 마진 계산 (소싱 통과 시)

---

### 예시 2: 고객 클레임

**입력**:
```
고객이 배송 지연 클레임 넣었어. 벤더가 연락 안 받고 있어.
```

**PM 분석 결과**:
```json
{
  "task_type": "cs_response",
  "summary": "배송 지연 클레임 대응 및 벤더 항의",
  "subtasks": [
    {
      "task_id": "T001",
      "agent": "cs",
      "priority": "p0",
      "description": "고객 안심 템플릿 작성"
    },
    {
      "task_id": "T002",
      "agent": "cs",
      "priority": "p0",
      "description": "벤더 항의 중국어 템플릿 작성"
    }
  ]
}
```

**실행 순서**:
1. `cs` 에이전트 → 고객 응대 템플릿 + 벤더 항의 문구 동시 생성

---

### 예시 3: 복합 작업

**입력**:
```
타오바오 타월 상품 이미지 5장 현지화하고,
SEO 상품명도 만들고, 블로그 홍보 글도 써줘.
```

**PM 분석 결과**:
```json
{
  "task_type": "complex",
  "summary": "이미지 현지화 → 상품 등록 → 콘텐츠 제작 파이프라인",
  "subtasks": [
    {
      "task_id": "T001",
      "agent": "image",
      "priority": "p1",
      "description": "타오바오 이미지 5장 한국어 번역 및 리스크 제거"
    },
    {
      "task_id": "T002",
      "agent": "product_registration",
      "priority": "p2",
      "description": "SEO 최적화 상품명 3안 생성"
    },
    {
      "task_id": "T003",
      "agent": "content",
      "priority": "p3",
      "description": "블로그 홍보 글 초안 작성"
    }
  ],
  "workflow": [
    {"step": 1, "agent": "image", "condition": "항상"},
    {"step": 2, "agent": "product_registration", "condition": "이미지 완료 시"},
    {"step": 3, "agent": "content", "condition": "등록 완료 시"}
  ]
}
```

**실행 순서**:
1. `image` 에이전트 → 이미지 재가공
2. `product_registration` 에이전트 → SEO 상품명 (이미지 메타데이터 활용)
3. `content` 에이전트 → 블로그 글 (상품 정보 활용)

---

## 지원 작업 유형

| 작업 유형 | 설명 | 라우팅 에이전트 |
|:---|:---|:---|
| `sourcing` | 신규 상품 소싱, 벤더 발굴 | sourcing → margin |
| `product_registration` | SEO 상품명, 옵션명 정규화 | product_registration |
| `margin_check` | 원가 계산, 수익성 검증 | margin |
| `image_localization` | 이미지 한국어 번역 | image → product_registration |
| `content_creation` | 블로그/SNS 홍보 | content |
| `cs_response` | 고객 클레임, 벤더 분쟁 | cs |
| `complex` | 위 작업의 조합 | 순차/병렬 실행 |

---

## 우선순위 레벨

| 레벨 | 아이콘 | 설명 | 예시 |
|:---:|:---:|:---|:---|
| **P0** | 🔥 | 긴급 (즉시 처리) | 고객 클레임, 계정 제재 위험 |
| **P1** | ⚠️ | 높음 | 신규 소싱, 마진 검수 |
| **P2** | 📌 | 보통 | 상품 등록, 이미지 현지화 |
| **P3** | 💡 | 낮음 | 콘텐츠 제작, 홍보 글 |

---

## 에이전트 목록

PM 에이전트가 라우팅할 수 있는 6개 전문 에이전트:

1. **sourcing**: 소싱/상품 발굴
   - 리스크 필터링 (통관/지재권/의료기기)
   - 벤더 질문 템플릿 생성

2. **product_registration**: 상품 등록/정규화
   - SEO 상품명 3안
   - 옵션명 한글화

3. **margin**: 마진/리스크 검수
   - 손익분기 판매가
   - 순이익률 계산

4. **content**: 콘텐츠/홍보
   - 블로그/SNS 카피
   - 채널별 최적화

5. **cs**: 운영/CS
   - 고객 응대 템플릿
   - 벤더 항의 중국어 문구

6. **image**: 이미지 현지화
   - 중국어 → 한국어 번역
   - 유아/인물 리스크 제거

---

## 제한 사항

### PM 에이전트가 **하지 않는** 일

1. ❌ 직접 상세페이지 작성
2. ❌ 원가 계산
3. ❌ 소싱 통과 여부 확정
4. ❌ CS 답변 작성
5. ❌ 마케팅 카피 작성

→ **PM은 라우터 역할**입니다. 실행은 후속 에이전트가 담당합니다.

---

## API 레퍼런스

### PMAgent 클래스

#### `analyze_request(user_request: str) -> Dict`

사용자 요청을 분석하여 JSON 형식으로 반환합니다.

**Parameters**:
- `user_request` (str): 사용자의 원본 요청 텍스트

**Returns**:
- `Dict`: 작업 분석 결과
  - `task_type` (str): 작업 유형
  - `summary` (str): 요청 요약
  - `subtasks` (List[Dict]): 하위 작업 목록
  - `workflow` (List[Dict]): 실행 순서

**Example**:
```python
pm = PMAgent()
result = pm.analyze_request("타오바오 링크 분석해줘")
print(result['task_type'])  # "sourcing"
```

---

#### `route_to_agent(analysis: Dict) -> List[Dict]`

분석 결과를 기반으로 에이전트 라우팅 큐를 생성합니다.

**Parameters**:
- `analysis` (Dict): `analyze_request()`의 결과

**Returns**:
- `List[Dict]`: 실행할 에이전트 목록

**Example**:
```python
agent_queue = pm.route_to_agent(analysis)
for agent in agent_queue:
    print(f"{agent['agent']}: {agent['description']}")
```

---

#### `execute_workflow(user_request: str, auto_execute: bool = False) -> Dict`

전체 워크플로우를 실행합니다.

**Parameters**:
- `user_request` (str): 사용자 요청
- `auto_execute` (bool): True면 자동 실행, False면 계획만 수립 (기본값: False)

**Returns**:
- `Dict`: 워크플로우 실행 결과
  - `request` (str): 원본 요청
  - `analysis` (Dict): 분석 결과
  - `agent_queue` (List[Dict]): 에이전트 큐
  - `status` (str): 실행 상태

**Example**:
```python
# 계획만 수립
plan = pm.execute_workflow("고객 클레임 처리해줘", auto_execute=False)

# 자동 실행 (구현 예정)
result = pm.execute_workflow("고객 클레임 처리해줘", auto_execute=True)
```

---

#### `format_output(workflow_result: Dict) -> str`

결과를 마크다운 형식으로 변환합니다.

**Parameters**:
- `workflow_result` (Dict): `execute_workflow()`의 결과

**Returns**:
- `str`: 마크다운 형식 출력

**Example**:
```python
output = pm.format_output(workflow_result)
print(output)
```

---

## 개발 로드맵

### ✅ Phase 1: 기본 기능 (완료)
- [x] 요청 자동 분류
- [x] 작업 분해
- [x] 우선순위 지정
- [x] 에이전트 라우팅

### 🚧 Phase 2: 자동 실행 (진행 중)
- [ ] 에이전트 간 데이터 전달
- [ ] 순차 실행 로직
- [ ] 병렬 실행 지원
- [ ] 실행 상태 추적

### 📅 Phase 3: 고급 기능 (예정)
- [ ] 에이전트 실행 결과 수집
- [ ] 오류 복구 로직
- [ ] 재시도 메커니즘
- [ ] 실행 이력 저장

---

## 트러블슈팅

### Q1. "ANTHROPIC_API_KEY not found" 오류

**원인**: 환경 변수 미설정

**해결**:
```bash
export ANTHROPIC_API_KEY="your-key"
```

---

### Q2. JSON 파싱 오류

**원인**: Claude API 응답이 JSON이 아닌 경우

**해결**: 로그에서 원본 응답 확인
```bash
python pm_agent.py "요청" 2>&1 | grep "원본 응답"
```

---

### Q3. 자동 실행이 안 됨

**현재 상태**: Phase 2 개발 중

**임시 해결**: 수동으로 각 에이전트 호출
```python
# PM이 추천한 순서대로 수동 실행
# 1. sourcing 에이전트
# 2. margin 에이전트
# 3. product_registration 에이전트
```

---

## 라이선스

Internal use only - Fortimove Global

## 버전

- **v1.0** (2026-03-29): 초기 릴리스
  - 요청 분류 및 라우팅 기능
  - 6개 에이전트 지원
  - CLI 인터페이스
