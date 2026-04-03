# 🌐 PM Agent 서비스 접속 정보

**서버**: stg-pm-agent-01 (1.201.124.96)
**상태**: ✅ Production Running

---

## 📍 주요 서비스 URL

### 1️⃣ 메인 대시보드 (Admin UI)
**URL**: http://1.201.124.96/

**기능**:
- 승인 대기열 실시간 조회
- 상품 승인/거부 관리
- Batch Export (JSON/CSV)
- Handoff 실행 (Slack/Email)

**접속 방법**:
- 브라우저에서 http://1.201.124.96/ 접속
- 페이지 로드 시 자동으로 대시보드 표시
- 좌측: 대기열 목록
- 우측: 상세 정보 및 액션

---

### 2️⃣ Health Check API
**URL**: http://1.201.124.96/health

**응답 예시**:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-30T17:46:21.981423"
}
```

**용도**:
- 서비스 상태 모니터링
- Uptime 체크
- 헬스체크 엔드포인트

---

### 3️⃣ API 문서 (Swagger UI)
**URL**: http://1.201.124.96/docs

**기능**:
- 전체 API 엔드포인트 목록
- 실시간 API 테스트 (Try it out)
- Request/Response 스키마 확인
- 인증 토큰 입력 가능

**사용 방법**:
1. http://1.201.124.96/docs 접속
2. 우측 상단 "Authorize" 클릭
3. Token 입력: `def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95`
4. 각 엔드포인트에서 "Try it out" 클릭하여 테스트

---

### 4️⃣ OpenAPI Schema
**URL**: http://1.201.124.96/openapi.json

**용도**:
- API 스키마 정의 (JSON 형식)
- 자동 코드 생성 도구 연동
- API 클라이언트 생성

---

## 🔐 인증 정보

### ADMIN_TOKEN
```
def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95
```

### 사용 방법

#### 1. API 호출 시 (curl)
```bash
curl -H "Authorization: Bearer def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95" \
     http://1.201.124.96/api/queue
```

#### 2. Swagger UI에서
1. http://1.201.124.96/docs 접속
2. 우측 상단 "Authorize" 버튼 클릭
3. Token 입력 후 "Authorize" 클릭

---

## 📋 사용 가능한 API 엔드포인트

### 공개 엔드포인트 (인증 불필요)
| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 서비스 상태 확인 |
| GET | `/` | Admin UI (메인 대시보드) |

### 인증 필요 엔드포인트
| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/queue` | 승인 대기열 목록 조회 |
| GET | `/api/queue/{review_id}` | 특정 항목 상세 조회 |
| PATCH | `/api/queue/{review_id}` | 승인/거부 처리 |
| POST | `/api/queue/{review_id}/retry` | 항목 재시도 |
| GET | `/api/queue/{review_id}/revisions` | 수정 이력 조회 |
| GET | `/api/queue/{review_id}/export/json` | 개별 JSON Export |
| GET | `/api/queue/{review_id}/export/csv` | 개별 CSV Export |
| GET | `/api/exports/approved/json` | 승인 항목 일괄 JSON Export |
| GET | `/api/exports/approved/csv` | 승인 항목 일괄 CSV Export |
| GET | `/api/handoff/status` | Handoff 상태 조회 |
| GET | `/api/handoff/runs` | Handoff 실행 이력 |
| GET | `/api/handoff/verify` | Slack/Email 채널 검증 |
| POST | `/api/handoff/run` | Handoff 실행 (알림 전송) |

---

## 🖥️ 브라우저 접속 테스트

### 즉시 확인 가능한 페이지

1. **메인 대시보드**:
   - URL: http://1.201.124.96/
   - 승인 대기열 관리 UI

2. **Health Check**:
   - URL: http://1.201.124.96/health
   - JSON 응답 확인

3. **API 문서**:
   - URL: http://1.201.124.96/docs
   - Swagger UI 인터페이스

4. **OpenAPI Schema**:
   - URL: http://1.201.124.96/openapi.json
   - JSON 스키마 다운로드

---

## 🧪 API 테스트 예시

### 1. Health Check
```bash
curl http://1.201.124.96/health
```

**응답**:
```json
{"status":"healthy","timestamp":"2026-03-30T..."}
```

### 2. 승인 대기열 조회 (인증 필요)
```bash
curl -H "Authorization: Bearer def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95" \
     http://1.201.124.96/api/queue?status=pending
```

### 3. 승인 처리
```bash
curl -X PATCH \
     -H "Authorization: Bearer def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95" \
     -H "Content-Type: application/json" \
     -d '{"action":"approve","notes":"승인합니다"}' \
     http://1.201.124.96/api/queue/{review_id}
```

### 4. Handoff 실행 (Slack/Email 알림)
```bash
curl -X POST \
     -H "Authorization: Bearer def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95" \
     http://1.201.124.96/api/handoff/run
```

---

## 📊 대시보드 기능

### 좌측 사이드바
- **Status Filter**: Pending/Approved/Needs Edit/Rejected 필터링
- **Item List**: 승인 대기 항목 목록
- **Batch Operations**:
  - Export Batch JSON
  - Export Batch CSV
  - 🚀 Run Handoff (Slack/Email)

### 우측 메인 영역
- **상세 정보**: 선택한 항목의 전체 데이터
- **Actions**:
  - ✅ Approve (승인)
  - 🔄 Request Edit (수정 요청)
  - ❌ Reject (거부)
  - 💾 Export JSON
  - 📄 Export CSV

---

## 🔧 트러블슈팅

### 문제 1: 페이지가 로드되지 않음
```bash
# 서비스 상태 확인
ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96
sudo systemctl status pm-agent
```

### 문제 2: API 인증 실패
- ADMIN_TOKEN 재확인
- Authorization 헤더 형식: `Bearer {token}`

### 문제 3: 데이터가 보이지 않음
- 현재 승인 대기열이 비어있을 수 있음
- Agent 실행 후 데이터 생성 필요

---

## 📞 추가 정보

**배포 서버**: stg-pm-agent-01 (1.201.124.96)
**SSH 접속**: `ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96`
**서비스 로그**: `sudo journalctl -u pm-agent -f`

**관련 문서**:
- [deployment-completion-report.md](./deployment-completion-report.md)
- [deployment-status-report.md](./deployment-status-report.md)
- [pm-agent/DEPLOYMENT.md](../pm-agent/DEPLOYMENT.md)

---

**업데이트**: 2026-03-31 02:50 KST
**상태**: ✅ All Systems Operational
