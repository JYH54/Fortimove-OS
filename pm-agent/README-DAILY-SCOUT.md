# Daily Scout Integration Quick Start Guide

## 🚀 빠른 시작

### 1. 단일 배치 실행 (테스트)

```bash
cd /home/fortymove/Fortimove-OS/pm-agent
./run_daily_scout_once.sh
```

**처리 내용**:
- 1개 상품만 처리
- DB 상태 업데이트
- Approval Queue 저장
- 즉시 종료

### 2. 연속 실행 (프로덕션)

```bash
cd /home/fortymove/Fortimove-OS/pm-agent
./run_daily_scout_continuous.sh
```

**처리 내용**:
- 5분마다 폴링
- 배치당 5개 상품 처리
- 무한 반복 (Ctrl+C로 종료)

### 3. 백그라운드 실행

```bash
cd /home/fortymove/Fortimove-OS/pm-agent
nohup ./run_daily_scout_continuous.sh > daily_scout.log 2>&1 &

# 로그 확인
tail -f daily_scout.log

# 프로세스 종료
ps aux | grep daily_scout
kill <PID>
```

---

## 📊 상태 확인

### DB 상태 확인

```bash
# Pending 상품 수
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
SELECT workflow_status, COUNT(*)
FROM wellness_products
GROUP BY workflow_status;
"

# 최근 처리된 상품
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
SELECT id, product_name, workflow_status, workflow_updated_at
FROM wellness_products
WHERE workflow_updated_at IS NOT NULL
ORDER BY workflow_updated_at DESC
LIMIT 5;
"
```

### Approval Queue 상태 확인

```bash
# API로 확인
curl -s https://staging-pm-agent.fortimove.com/api/stats | python3 -m json.tool

# 대시보드 접속
https://staging-pm-agent.fortimove.com/admin
```

---

## ⚙️ 환경 변수

| 변수 | 기본값 | 설명 |
|-----|--------|------|
| `RUN_MODE` | continuous | `once` 또는 `continuous` |
| `DB_HOST` | localhost | PostgreSQL 호스트 |
| `DB_PORT` | 5432 | PostgreSQL 포트 |
| `DB_NAME` | fortimove_images | 데이터베이스 이름 |
| `DB_USER` | fortimove | DB 사용자 |
| `DB_PASSWORD` | fortimove123 | DB 비밀번호 |
| `PM_AGENT_API_URL` | https://staging-pm-agent.fortimove.com | API URL |
| `BATCH_SIZE` | 5 | 한 번에 처리할 상품 수 |
| `POLLING_INTERVAL` | 300 | 폴링 간격 (초) |

### 환경 변수 오버라이드

```bash
# 배치 크기 10개로 변경
export BATCH_SIZE=10
./run_daily_scout_continuous.sh

# 폴링 간격 10분으로 변경
export POLLING_INTERVAL=600
./run_daily_scout_continuous.sh
```

---

## 🔍 트러블슈팅

### 1. DB 연결 실패

**증상**:
```
psycopg2.OperationalError: connection refused
```

**해결**:
```bash
# PostgreSQL 컨테이너 확인
docker ps | grep postgres

# 포트 확인
docker ps | grep 5432

# 연결 테스트
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "SELECT 1;"
```

### 2. API 호출 실패

**증상**:
```
requests.exceptions.RequestException
```

**해결**:
```bash
# API 상태 확인
curl -s https://staging-pm-agent.fortimove.com/health

# 워크플로우 목록 확인
curl -s https://staging-pm-agent.fortimove.com/api/workflows/list
```

### 3. Workflow 실패

**증상**:
```
[Product #XX] ❌ API 실행 실패
```

**해결**:
```bash
# DB에서 에러 메시지 확인
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
SELECT id, product_name, workflow_error
FROM wellness_products
WHERE workflow_status = 'failed'
ORDER BY workflow_updated_at DESC
LIMIT 5;
"

# 수동으로 재시도
curl -X POST https://staging-pm-agent.fortimove.com/api/workflows/run \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "quick_sourcing_check",
    "user_input": {
      "source_url": "...",
      "source_title": "...",
      "market": "korea",
      "source_price_cny": 30.0,
      "weight_kg": 0.5
    },
    "save_to_queue": true
  }'
```

---

## 📈 성능 튜닝

### 배치 크기 조정

```bash
# 소량 테스트 (1-3개)
export BATCH_SIZE=1

# 일반 운영 (5-10개)
export BATCH_SIZE=5

# 대량 처리 (10-20개)
export BATCH_SIZE=10
```

**권장 설정**:
- 신규 상품 < 20개/일: BATCH_SIZE=5, POLLING_INTERVAL=300 (5분)
- 신규 상품 20-50개/일: BATCH_SIZE=10, POLLING_INTERVAL=180 (3분)
- 신규 상품 > 50개/일: BATCH_SIZE=20, POLLING_INTERVAL=120 (2분)

### 폴링 간격 조정

```bash
# 빠른 처리 (2분)
export POLLING_INTERVAL=120

# 일반 운영 (5분)
export POLLING_INTERVAL=300

# 야간 모드 (10분)
export POLLING_INTERVAL=600
```

---

## 📊 모니터링

### 실시간 로그 확인

```bash
# Docker 로그
docker logs -f daily-scout-integration

# 파일 로그 (백그라운드 실행 시)
tail -f daily_scout.log
```

### 처리 통계

```bash
# 오늘 처리된 상품 수
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
SELECT
    workflow_status,
    COUNT(*) as count
FROM wellness_products
WHERE DATE(workflow_updated_at) = CURRENT_DATE
GROUP BY workflow_status;
"

# 시간대별 처리 통계
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
SELECT
    DATE_TRUNC('hour', workflow_updated_at) as hour,
    COUNT(*) as processed_count,
    SUM(CASE WHEN workflow_status = 'completed' THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN workflow_status = 'failed' THEN 1 ELSE 0 END) as failed_count
FROM wellness_products
WHERE workflow_updated_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;
"
```

---

## 🔧 유지보수

### Pending 상품 재설정

```bash
# Failed 상품을 Pending으로 재설정
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
UPDATE wellness_products
SET workflow_status = 'pending',
    workflow_error = NULL,
    workflow_updated_at = CURRENT_TIMESTAMP
WHERE workflow_status = 'failed'
  AND workflow_updated_at < NOW() - INTERVAL '1 hour';
"
```

### 에러 로그 정리

```bash
# 오래된 에러 로그 삭제 (30일 이상)
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
UPDATE wellness_products
SET workflow_error = NULL
WHERE workflow_status = 'failed'
  AND workflow_updated_at < NOW() - INTERVAL '30 days';
"
```

---

## 🚨 긴급 상황 대응

### 시스템 과부하

```bash
# 1. Integration 중지
docker stop daily-scout-integration

# 2. Pending 상품 수 확인
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
SELECT COUNT(*) FROM wellness_products WHERE workflow_status = 'pending';
"

# 3. 배치 크기 줄이고 재시작
export BATCH_SIZE=1
export POLLING_INTERVAL=600
./run_daily_scout_continuous.sh
```

### API 장애

```bash
# 1. API 상태 확인
curl -s https://staging-pm-agent.fortimove.com/health

# 2. 서버 재시작 (필요 시)
ssh ubuntu@1.201.124.96 "sudo systemctl restart pm-agent"

# 3. Integration 재시작
docker stop daily-scout-integration
./run_daily_scout_continuous.sh
```

---

## 📝 추가 정보

- **API 문서**: https://staging-pm-agent.fortimove.com/docs
- **대시보드**: https://staging-pm-agent.fortimove.com/admin
- **상세 문서**: [docs/api-execution-daily-scout-integration-complete.md](../docs/api-execution-daily-scout-integration-complete.md)
