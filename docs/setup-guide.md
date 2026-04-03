# Fortimove OS 설정 완료 가이드

## 시스템 구성

현재 Fortimove OS는 **2개의 주요 시스템**으로 구성되어 있습니다:

### 1. Image Localization System (이미지 현지화)
- **포트**: http://localhost:3000 (프론트엔드), http://localhost:8000 (API)
- **기능**:
  - 중국 상품 이미지 업로드
  - OCR로 중국어 텍스트 추출
  - AI 번역 (중국어 → 한국어)
  - 리스크 이미지 감지 (아기, 얼굴, 브랜드 로고)
  - 처리된 이미지 다운로드

### 2. Daily Wellness Scout (자동 트렌드 모니터링)
- **실행 방식**: 백그라운드 자동 실행
- **스케줄**: 매일 오전 9시
- **기능**:
  - 4개 지역 웰니스 상품 트렌드 스캔 (일본, 중국, 미국, 영국)
  - AI 리스크 필터링 (의료기기 오인, 건기식 인증, 금지성분, 지재권)
  - 이메일 리포트 자동 발송
  - Slack 알림 (일반 + 긴급)
  - 장기 트렌드 데이터 누적

---

## 빠른 시작

### 1단계: 전체 시스템 시작

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# 모든 서비스 시작
docker-compose up -d

# 상태 확인
docker-compose ps
```

**예상 결과**:
```
✅ backend       - UP (http://localhost:8000)
✅ frontend      - UP (http://localhost:3000)
✅ db            - UP (healthy)
✅ redis         - UP (healthy)
✅ daily_scout   - UP (백그라운드 실행 중)
```

### 2단계: Image Localization 사용

1. 브라우저에서 http://localhost:3000 접속
2. 중국 상품 이미지 드래그 앤 드롭 또는 선택
3. "이미지 처리 시작" 버튼 클릭
4. 결과 확인 및 다운로드

### 3단계: Daily Scout 설정

현재 **API 접근 문제**로 즉시 사용 불가합니다. 다음 설정 필요:

#### 필수 설정:
1. **Anthropic API 키** 수정 → [anthropic-api-setup.md](./anthropic-api-setup.md) 참고
2. **Gmail 앱 비밀번호** 생성 → [notification-setup.md](./notification-setup.md#1-gmail-이메일-리포트-설정) 참고
3. **Slack Webhook** 생성 → [notification-setup.md](./notification-setup.md#2-slack-webhook-알림-설정) 참고

#### 설정 후:
```bash
# .env 파일 수정
nano /home/fortymove/Fortimove-OS/image-localization-system/.env

# 재시작
docker-compose restart daily_scout

# 로그 확인
docker logs image-localization-system-daily_scout-1 -f
```

---

## 상세 문서

### 시스템별 가이드

1. **Image Localization**
   - 사용법: 브라우저에서 http://localhost:3000 접속
   - API 문서: http://localhost:8000/docs

2. **Daily Wellness Scout**
   - README: [daily-scout/README.md](../daily-scout/README.md)
   - 데이터베이스 위치: `/app/data/wellness_trends.db` (Docker volume)

### 설정 가이드

1. **Anthropic API 설정**
   - [docs/anthropic-api-setup.md](./anthropic-api-setup.md)
   - API 키 권한 확인
   - 모델 접근 권한 부여
   - 크레딧 충전

2. **알림 설정**
   - [docs/notification-setup.md](./notification-setup.md)
   - Gmail 앱 비밀번호 생성
   - Slack Webhook 설정
   - 테스트 방법

3. **API 키 진단**
   - [docs/api-key-diagnosis.md](./api-key-diagnosis.md)
   - 현재 문제 상황
   - 해결 방법
   - 임시 Mock 모드 설정

---

## 현재 알려진 이슈

### ⚠️ Claude API 접근 불가 (높은 우선순위)

**문제**:
```
Error code: 404 - not_found_error
message: model: claude-3-5-sonnet-20241022
```

**영향**:
- Image Localization: **번역 기능 동작 안 함** (OCR은 작동, Fallback 번역 사용 중)
- Daily Scout: **트렌드 스캔 불가** (0개 상품 반환)

**해결 필요**:
1. Anthropic Console에서 API 키 권한 확인
2. 크레딧 잔액 확인 및 충전
3. 새 API 키 발급 고려

**상세**: [docs/api-key-diagnosis.md](./api-key-diagnosis.md)

---

## 데이터 및 로그

### 로그 확인

```bash
# 전체 서비스 로그
docker-compose logs -f

# 개별 서비스 로그
docker logs image-localization-system-backend-1 -f
docker logs image-localization-system-daily_scout-1 -f
docker logs image-localization-system-frontend-1 -f
```

### 데이터 위치

| 서비스 | 데이터 | 위치 |
|--------|--------|------|
| Image Localization | 처리된 이미지 | `/tmp/fortimove-images` (volume: `image_storage`) |
| Daily Scout | SQLite DB | `/app/data/wellness_trends.db` (volume: `scout_data`) |
| Daily Scout | 로그 파일 | `/app/logs/` (volume: `scout_logs`) |

### 데이터베이스 접근

```bash
# Image Localization (PostgreSQL)
docker exec -it image-localization-system-db-1 psql -U fortimove -d fortimove_images

# Daily Scout (SQLite)
docker exec -it image-localization-system-daily_scout-1 sqlite3 /app/data/wellness_trends.db
```

---

## 문제 해결

### 컨테이너가 시작되지 않음

```bash
# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs <service_name>

# 재빌드
docker-compose build <service_name>
docker-compose up -d <service_name>
```

### 포트 충돌

```bash
# 사용 중인 포트 확인
sudo lsof -i :3000
sudo lsof -i :8000

# 다른 프로세스가 사용 중이면 종료 또는 docker-compose.yml에서 포트 변경
```

### 디스크 공간 부족

```bash
# Docker 리소스 정리
docker system prune -a --volumes

# 주의: 모든 사용하지 않는 이미지, 컨테이너, 볼륨 삭제됨
```

### API 키 문제

[docs/api-key-diagnosis.md](./api-key-diagnosis.md) 참고

---

## 운영 체크리스트

시스템을 실제 운영하기 전 확인:

### Image Localization
- [ ] http://localhost:3000 접속 가능
- [ ] 이미지 업로드 테스트 완료
- [ ] OCR 텍스트 추출 확인
- [ ] 번역 결과 확인 (현재: Fallback 모드)
- [ ] 처리된 이미지 다운로드 확인

### Daily Wellness Scout
- [ ] Anthropic API 키 정상화 (현재: 불가)
- [ ] Gmail 앱 비밀번호 설정
- [ ] Slack Webhook URL 설정
- [ ] `.env` 파일 모든 변수 입력 완료
- [ ] 즉시 실행 테스트 (`SCOUT_RUN_IMMEDIATELY=true`)
- [ ] 이메일 리포트 수신 확인
- [ ] Slack 알림 수신 확인
- [ ] 스케줄 시간 설정 (`SCOUT_SCHEDULE_TIME=09:00`)
- [ ] 정상 운영 모드 전환 (`SCOUT_RUN_IMMEDIATELY=false`)

### 모니터링
- [ ] 로그 정기 확인 설정 (cron 또는 로그 모니터링 도구)
- [ ] 디스크 사용량 모니터링
- [ ] API 크레딧 잔액 모니터링

---

## 다음 단계

### 즉시 해결 필요
1. **Anthropic API 키 문제 해결** (최우선)
   - Console 접속 → 크레딧 확인 → 필요시 충전
   - 새 API 키 발급 고려

2. **알림 설정 완료**
   - Gmail 앱 비밀번호 생성
   - Slack Webhook 생성

### 향후 개선 사항
1. **Image Localization**
   - 더 정확한 OCR 모델 (Tesseract 추가)
   - 배치 처리 기능
   - 이미지 편집 기능 (텍스트 제거 후 재배치)

2. **Daily Scout**
   - 더 많은 지역 추가 (한국, 호주 등)
   - 카테고리 커스터마이징
   - 웹 대시보드 추가 (현재는 이메일/Slack만)

3. **통합**
   - 단일 웹 인터페이스에서 두 시스템 통합 관리
   - 사용자 인증 및 권한 관리
   - 클라우드 배포 (AWS, GCP 등)

---

## 지원

### 문의
- Fortimove 내부: [대표 또는 개발팀]
- Anthropic API: support@anthropic.com
- Claude Code: https://github.com/anthropics/claude-code/issues

### 유용한 링크
- Anthropic Console: https://console.anthropic.com
- Docker 문서: https://docs.docker.com
- FastAPI 문서: https://fastapi.tiangolo.com
- Slack API: https://api.slack.com

---

**마지막 업데이트**: 2026-03-28
**시스템 버전**: 1.0.0
**상태**: 부분 운영 (Image Localization: OK, Daily Scout: API 설정 필요)
