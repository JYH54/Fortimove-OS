# Daily Wellness Scout

매일 자동으로 일본, 중국, 미국, 영국에서 뜨고 있는 구매대행 가능한 웰니스 및 헬스케어 상품을 발굴하는 AI 에이전트입니다.

## 주요 기능

### 1. 자동 트렌드 모니터링
- **지역**: 일본(Rakuten), 중국(Taobao/RED), 미국(iHerb/Amazon), 영국(Holland&Barrett)
- **실행 시간**: 매일 오전 9시 (설정 변경 가능)
- **분석 대상**: 웰니스, 헬스케어, 건강기능식품, 뷰티 케어 카테고리

### 2. AI 기반 리스크 필터링
Claude AI가 각 상품을 4가지 기준으로 평가:
- ✅ **의료기기 오인 여부**: 식약처 규제 회피
- ✅ **건기식 인증 여부**: 한국 통관 가능성
- ✅ **금지 성분 포함 여부**: 스테로이드, 처방 성분 체크
- ✅ **지재권 침해 여부**: 디자인권, 상표권 문제

### 3. 자동 리포트 및 알림
- **이메일 리포트**: HTML 형식의 상세 일일 리포트
- **Slack 알림**: 실시간 요약 및 긴급 알림
- **긴급 알림**: 트렌드 점수 90+ 아이템 즉시 통보

### 4. 장기 트렌드 분석
- **데이터베이스 저장**: SQLite 기반 모든 데이터 누적
- **30일 분석**: 카테고리별/지역별 트렌드 통계
- **인사이트 제공**: AI 기반 트렌드 인사이트

## 설치 및 실행

### 1. 환경 변수 설정

`.env` 파일 생성 (`.env.example` 참고):

```bash
# Claude AI API
ANTHROPIC_API_KEY=sk-ant-api03-...

# 스케줄 설정
SCOUT_SCHEDULE_TIME=09:00
SCOUT_RUN_IMMEDIATELY=false

# 이메일 리포트
SCOUT_EMAIL_SENDER=your-email@gmail.com
SCOUT_EMAIL_PASSWORD=your-app-password
SCOUT_EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com

# Slack 알림
SCOUT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SCOUT_SLACK_URGENT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/URGENT/URL
```

### 2. Docker Compose로 실행

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# 빌드 및 백그라운드 실행
docker-compose up -d daily_scout

# 로그 확인
docker logs image-localization-system-daily_scout-1 -f

# 중지
docker-compose stop daily_scout
```

### 3. 즉시 테스트 실행

`.env` 파일에서 `SCOUT_RUN_IMMEDIATELY=true`로 설정하면 컨테이너 시작 시 즉시 스캔을 실행합니다.

```bash
# 환경 변수 수정 후
docker-compose restart daily_scout
```

## 출력 결과

### 1. 데이터베이스
- **위치**: `/app/data/wellness_trends.db` (Docker volume: `scout_data`)
- **테이블**:
  - `products`: 개별 상품 데이터 (지역, 브랜드, 가격, 트렌드 점수, 리스크 상태 등)
  - `daily_stats`: 일일 집계 통계

### 2. 이메일 리포트
HTML 형식으로 다음 정보 포함:
- 일일 요약 통계
- 상품 카드 (이미지, 가격, 트렌드 점수, 구매 링크)
- 리스크 상태 표시
- 지역별 카테고리별 분류

### 3. Slack 알림
- **일반 채널**: 일일 요약 (총 개수, 통과/보류/제외 비율, 주요 카테고리)
- **긴급 채널**: 트렌드 점수 90+ 아이템 즉시 알림

## 로그 확인

```bash
# 실시간 로그
docker logs image-localization-system-daily_scout-1 -f

# 최근 50줄
docker logs image-localization-system-daily_scout-1 --tail 50

# 로그 파일 직접 확인 (Docker volume)
docker exec image-localization-system-daily_scout-1 ls -la /app/logs/
```

## 데이터베이스 조회

```bash
# SQLite 접속
docker exec -it image-localization-system-daily_scout-1 sqlite3 /app/data/wellness_trends.db

# 테이블 확인
.tables

# 최근 10개 상품
SELECT date, region, product_name, trend_score, risk_status FROM products ORDER BY created_at DESC LIMIT 10;

# 통계 조회
SELECT * FROM daily_stats ORDER BY date DESC LIMIT 7;

# 종료
.quit
```

## 주의사항

### 1. API 키 관리
- ANTHROPIC_API_KEY는 반드시 `.env` 파일에서 관리
- GitHub에 커밋하지 말 것 (`.gitignore`에 추가됨)

### 2. Gmail 앱 비밀번호
- Gmail 2단계 인증 활성화 후 앱 비밀번호 생성 필요
- 일반 비밀번호로는 SMTP 접속 불가

### 3. Slack Webhook
- Slack 워크스페이스에서 Incoming Webhook 생성
- 채널별로 다른 Webhook URL 사용 가능

### 4. Claude API 모델 접근
- 현재 API 키는 모델 접근 권한 없음 (404 에러)
- Anthropic 콘솔에서 모델 접근 권한 확인 필요
- 모델 버전: `claude-3-5-sonnet-20241022` (daily_scout.py 23번째 줄에서 변경 가능)

## 커스터마이징

### 1. 스캔 시간 변경
`.env` 파일:
```bash
SCOUT_SCHEDULE_TIME=14:30  # 오후 2시 30분
```

### 2. 지역 추가/제거
[daily_scout.py](app/daily_scout.py) 27-65번째 줄에서 `self.regions` 수정

### 3. 리스크 기준 조정
[daily_scout.py](app/daily_scout.py) 175-261번째 줄의 `check_wellness_risks()` 함수 수정

### 4. 트렌드 점수 임계값
[daily_scout.py](app/daily_scout.py) 460번째 줄:
```python
if product["trend_score"] >= 90:  # 90 → 원하는 값으로 변경
```

## 문제 해결

### 1. 컨테이너가 계속 재시작됨
```bash
docker logs image-localization-system-daily_scout-1 --tail 100
```
로그에서 Python 에러 확인

### 2. 이메일이 발송되지 않음
- Gmail 앱 비밀번호 확인
- SMTP 방화벽 확인 (포트 587)
- `.env` 파일의 이메일 설정 확인

### 3. Slack 알림이 오지 않음
- Webhook URL이 올바른지 확인
- Slack 채널 권한 확인
- 로그에서 404 에러 확인

### 4. API 404 에러
- Anthropic API 키 확인
- 모델 접근 권한 확인
- API 크레딧 잔액 확인

## 시스템 요구사항

- Docker 20.10+
- Docker Compose 2.0+
- 디스크 여유 공간: 최소 1GB (로그 및 데이터베이스)
- 메모리: 최소 512MB

## 라이선스

Fortimove Internal Use Only
