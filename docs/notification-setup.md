# 알림 설정 가이드 (이메일 + Slack)

Daily Wellness Scout의 자동 리포트 및 알림을 받기 위한 설정 가이드입니다.

## 1. Gmail 이메일 리포트 설정

### A. Gmail 앱 비밀번호 생성 (필수)

Gmail은 보안상 일반 비밀번호로 SMTP 접속을 차단합니다. **앱 비밀번호**를 생성해야 합니다.

#### 1단계: Google 2단계 인증 활성화

1. **Google 계정 관리 페이지 접속**
   - https://myaccount.google.com/security

2. **2단계 인증 활성화**
   - "Google에 로그인" 섹션 → "2단계 인증" 클릭
   - "시작하기" 버튼 클릭
   - 휴대폰 번호 입력 및 인증
   - 완료

#### 2단계: 앱 비밀번호 생성

1. **앱 비밀번호 페이지 접속**
   - https://myaccount.google.com/apppasswords
   - 또는 "보안" → "Google에 로그인" → "앱 비밀번호"

2. **새 앱 비밀번호 생성**
   - "앱 선택" → "기타(맞춤 이름)"
   - 이름 입력: "Fortimove Daily Scout"
   - "생성" 클릭

3. **16자리 비밀번호 복사**
   - 예: `abcd efgh ijkl mnop`
   - 공백 제거: `abcdefghijklmnop`
   - **주의**: 이 비밀번호는 한 번만 표시되므로 즉시 복사!

#### 3단계: .env 파일에 설정

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# .env 파일 수정
nano .env
```

다음 항목 수정:
```bash
# 발송 계정 (Gmail 주소)
SCOUT_EMAIL_SENDER=your-email@gmail.com

# 앱 비밀번호 (16자리, 공백 제거)
SCOUT_EMAIL_PASSWORD=abcdefghijklmnop

# 수신자 (쉼표로 구분, 여러 명 가능)
SCOUT_EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com,recipient3@example.com
```

#### 4단계: 테스트

```bash
# Daily Scout 재시작
docker-compose restart daily_scout

# 즉시 실행으로 테스트
# .env에서 SCOUT_RUN_IMMEDIATELY=true 설정 후
docker-compose restart daily_scout

# 로그 확인 (이메일 발송 성공 여부)
docker logs image-localization-system-daily_scout-1 --tail 50
```

**성공 로그 예시**:
```
2026-03-28 09:00:15,123 - __main__ - INFO - 📧 이메일 리포트 발송 완료
```

**실패 로그 예시**:
```
2026-03-28 09:00:15,123 - __main__ - ERROR - 이메일 발송 실패: [Errno 535] Authentication failed
```

### B. 이메일 발송 문제 해결

#### 문제 1: "Authentication failed (535)"
- **원인**: 앱 비밀번호가 아닌 일반 비밀번호 사용
- **해결**: 위의 "앱 비밀번호 생성" 단계 수행

#### 문제 2: "SMTP AUTH extension not supported (538)"
- **원인**: 2단계 인증 미활성화
- **해결**: Google 2단계 인증 먼저 활성화

#### 문제 3: "Connection timed out"
- **원인**: 방화벽이 포트 587 차단
- **해결**:
  ```bash
  # 포트 확인
  telnet smtp.gmail.com 587
  # 연결되면 Ctrl+C로 종료
  ```

#### 문제 4: "Recipient address rejected"
- **원인**: 수신자 이메일 주소 오타
- **해결**: `.env`의 `SCOUT_EMAIL_RECIPIENTS` 다시 확인

### C. Gmail 외 다른 이메일 서비스

#### Naver Mail
```bash
SCOUT_EMAIL_SENDER=your-id@naver.com
SCOUT_EMAIL_PASSWORD=your-naver-password
```

`daily_scout.py` 수정 (385-396번째 줄):
```python
async def send_email_report(self, html_content: str):
    server = aiosmtplib.SMTP(
        hostname="smtp.naver.com",  # 변경
        port=587,
        use_tls=True
    )
```

#### Outlook/Hotmail
```bash
SCOUT_EMAIL_SENDER=your-email@outlook.com
SCOUT_EMAIL_PASSWORD=your-outlook-password
```

`daily_scout.py` 수정:
```python
    server = aiosmtplib.SMTP(
        hostname="smtp-mail.outlook.com",  # 변경
        port=587,
        use_tls=True
    )
```

---

## 2. Slack Webhook 알림 설정

### A. Slack Webhook URL 생성

#### 1단계: Slack 워크스페이스 준비

1. **Slack 워크스페이스 로그인**
   - 기존 워크스페이스 사용 또는
   - 새 워크스페이스 생성: https://slack.com/create

2. **알림 받을 채널 생성**
   - 일반 리포트용: `#daily-wellness-report`
   - 긴급 알림용: `#urgent-wellness-alerts` (선택사항)

#### 2단계: Incoming Webhook 앱 추가

1. **Slack App Directory 접속**
   - https://api.slack.com/apps
   - 또는 Slack 워크스페이스 → "앱" → "앱 관리" → "Browse App Directory"

2. **새 앱 생성**
   - "Create New App" 클릭
   - "From scratch" 선택
   - App Name: "Daily Wellness Scout"
   - Workspace 선택
   - "Create App" 클릭

3. **Incoming Webhooks 활성화**
   - 좌측 메뉴 "Incoming Webhooks" 클릭
   - "Activate Incoming Webhooks" 토글 ON
   - "Add New Webhook to Workspace" 클릭

4. **채널 선택 및 허용**
   - 일반 리포트용 채널 선택 (예: `#daily-wellness-report`)
   - "Allow" 클릭
   - Webhook URL 복사 (예: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX`)

5. **긴급 알림용 Webhook 추가 (선택사항)**
   - 다시 "Add New Webhook to Workspace" 클릭
   - 긴급 알림용 채널 선택 (예: `#urgent-wellness-alerts`)
   - "Allow" 클릭
   - Webhook URL 복사

#### 3단계: .env 파일에 설정

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# .env 파일 수정
nano .env
```

다음 항목 수정:
```bash
# 일반 리포트용 Webhook (필수)
SCOUT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX

# 긴급 알림용 Webhook (선택사항, 미입력시 일반 채널 사용)
SCOUT_SLACK_URGENT_WEBHOOK_URL=https://hooks.slack.com/services/T11111111/B11111111/YYYYYYYYYYYY
```

#### 4단계: 테스트

```bash
# Daily Scout 재시작
docker-compose restart daily_scout

# 로그 확인
docker logs image-localization-system-daily_scout-1 --tail 50
```

**성공 로그 예시**:
```
2026-03-28 09:00:20,456 - __main__ - INFO - 📢 슬랙 알림 발송 완료
```

**실패 로그 예시**:
```
2026-03-28 09:00:20,456 - __main__ - ERROR - 슬랙 알림 실패: 404
```

### B. Webhook URL 직접 테스트

터미널에서 바로 테스트:

```bash
# Webhook URL을 변수로 설정
WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# 테스트 메시지 발송
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "🧪 Daily Wellness Scout 테스트 알림입니다!",
    "blocks": [
      {
        "type": "header",
        "text": {
          "type": "plain_text",
          "text": "✅ 연동 테스트 성공"
        }
      },
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "Slack Webhook이 정상적으로 설정되었습니다."
        }
      }
    ]
  }'
```

**성공 응답**: `ok`
**실패 응답**: `invalid_payload` 또는 `404`

### C. Slack 알림 문제 해결

#### 문제 1: 404 Not Found
- **원인**: Webhook URL 오류 또는 만료
- **해결**:
  1. Slack App 설정 페이지에서 URL 재확인
  2. 필요시 Webhook 재생성

#### 문제 2: 401 Unauthorized
- **원인**: Webhook이 삭제되었거나 권한 취소됨
- **해결**: 새 Webhook 생성

#### 문제 3: 알림이 중복으로 옴
- **원인**: 컨테이너가 여러 번 재시작되며 중복 실행
- **해결**:
  ```bash
  # 실행 중인 컨테이너 확인
  docker ps | grep daily_scout

  # 중복 컨테이너 제거
  docker-compose down daily_scout
  docker-compose up -d daily_scout
  ```

#### 문제 4: 채널에 알림이 안 보임
- **원인**: 봇이 채널에 참여하지 않음
- **해결**: Slack 채널에서 `/invite @Daily Wellness Scout` 입력

---

## 3. 통합 테스트

### 전체 설정 완료 후 테스트

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# .env 파일 최종 확인
cat .env | grep SCOUT_

# 즉시 실행으로 테스트
# .env 수정
nano .env
# SCOUT_RUN_IMMEDIATELY=true로 변경

# 재시작
docker-compose restart daily_scout

# 실시간 로그 확인
docker logs image-localization-system-daily_scout-1 -f
```

**예상 로그 흐름**:
```
2026-03-28 09:00:10,123 - __main__ - INFO - 🚀 즉시 테스트 실행 시작...
2026-03-28 09:00:10,124 - __main__ - INFO - 🔍 Daily Wellness Scan 시작
2026-03-28 09:00:11,234 - __main__ - INFO -    🇯🇵 일본 트렌드 스캔 중...
2026-03-28 09:00:15,345 - __main__ - INFO -    → 5개 상품 발견
2026-03-28 09:00:15,346 - __main__ - INFO -    🇨🇳 중국 트렌드 스캔 중...
...
2026-03-28 09:00:30,456 - __main__ - INFO - 💾 데이터베이스 저장 완료: 18개 상품
2026-03-28 09:00:31,567 - __main__ - INFO - 📧 이메일 리포트 발송 완료
2026-03-28 09:00:32,678 - __main__ - INFO - 📢 슬랙 알림 발송 완료
2026-03-28 09:00:32,789 - __main__ - INFO - ✅ Daily Wellness Scan 완료 (22.7초)
```

### 수신 확인

1. **이메일**: `SCOUT_EMAIL_RECIPIENTS`에 지정한 주소로 HTML 리포트 수신
2. **Slack**: `#daily-wellness-report` 채널에 요약 알림
3. **Slack (긴급)**: 트렌드 점수 90+ 아이템이 있으면 `#urgent-wellness-alerts` 채널에 즉시 알림

---

## 4. 설정 체크리스트

실제 운영 전 체크:

- [ ] Google 2단계 인증 활성화됨
- [ ] Gmail 앱 비밀번호 생성 및 `.env`에 입력됨
- [ ] Slack Webhook URL 2개 생성됨 (일반 + 긴급)
- [ ] `.env` 파일에 모든 URL 입력됨
- [ ] `SCOUT_RUN_IMMEDIATELY=true`로 즉시 테스트 완료
- [ ] 이메일 수신 확인됨
- [ ] Slack 일반 채널 알림 확인됨
- [ ] Slack 긴급 채널 알림 확인됨 (90+ 아이템 있을 경우)
- [ ] `SCOUT_RUN_IMMEDIATELY=false`로 변경 후 재시작
- [ ] `SCOUT_SCHEDULE_TIME=09:00` 설정 확인

운영 시작!

```bash
# 최종 설정으로 재시작
docker-compose restart daily_scout

# 매일 오전 9시에 자동 실행됨
```

---

## 5. 알림 예시

### 이메일 리포트 (HTML)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Daily Wellness Trend Report
   2026-03-28
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 일일 요약
  총 분석: 32개
  ✅ 통과: 18개
  ⚠️ 보류: 9개
  ❌ 제외: 5개

🔥 주요 카테고리: 프로바이오틱스

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[상품 카드 이미지]
🇯🇵 일본 | Rakuten
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
유산균 프리미엄 30일분
¥3,980
트렌드 점수: 87/100
✅ 통과 (안전)

[구매 링크] [상세보기]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
...
```

### Slack 알림 (일반)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Daily Wellness Report (2026-03-28)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

총 32개 상품 분석
✅ 통과: 18개 (56%)
⚠️ 보류: 9개 (28%)
❌ 제외: 5개 (16%)

🔥 주요 카테고리: 프로바이오틱스

🇯🇵 일본: 8개
🇨🇳 중국: 12개
🇺🇸 미국: 7개
🇬🇧 영국: 5개
```

### Slack 알림 (긴급)

```
🚨 긴급 트렌드 알림!

트렌드 점수 90+ 핫 아이템 발견

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🇯🇵 콜라겐 젤리 스틱 30개입
¥2,980 | 트렌드: 95/100
카테고리: 뷰티 케어
상태: ✅ 통과

[즉시 확인] → https://...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
