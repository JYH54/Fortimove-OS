# Slack Webhook URL 생성 가이드 (5분 완성)

## 현재 상황

제공하신 토큰 `xoxe.xoxp-1-...`은 **OAuth 토큰**이며, Daily Scout에 필요한 **Incoming Webhook URL**과는 다릅니다.

필요한 형식: `https://hooks.slack.com/services/T.../B.../...`

---

## 빠른 설정 (5분)

### 1단계: Slack 워크스페이스 접속

기존 워크스페이스 또는 새로 생성: https://slack.com

### 2단계: Incoming Webhooks 앱 추가

**방법 A: 직접 링크** (가장 빠름)
1. https://api.slack.com/apps 접속
2. "Create New App" 클릭
3. "From scratch" 선택
4. App Name: `Daily Wellness Scout`
5. Workspace 선택 후 "Create App"

**방법 B: 워크스페이스에서**
1. Slack 워크스페이스 좌측 하단 "앱" 클릭
2. "앱 찾아보기" → 검색창에 "Incoming Webhooks" 입력
3. "Slack에 추가" 클릭

### 3단계: Webhook 활성화

1. 앱 설정 페이지에서 좌측 메뉴 "Incoming Webhooks" 클릭
2. **"Activate Incoming Webhooks"** 토글을 **ON**으로 변경
3. 페이지 하단 "Add New Webhook to Workspace" 버튼 클릭

### 4단계: 채널 선택

1. 알림을 받을 채널 선택 (예: `#daily-wellness-report`)
   - 채널이 없으면 먼저 Slack에서 채널 생성
2. "Allow" 버튼 클릭

### 5단계: Webhook URL 복사

```
Webhook URL 예시:
https://hooks.slack.com/services/T01234567/B01234567/abcdefghijklmnopqrstuvwx
```

이 URL을 복사하세요! (한 번만 표시될 수 있음)

### 6단계: 긴급 알림용 Webhook 추가 (선택사항)

트렌드 점수 90+ 아이템 전용 알림:

1. 같은 페이지에서 "Add New Webhook to Workspace" 다시 클릭
2. 다른 채널 선택 (예: `#urgent-wellness-alerts`)
3. "Allow" 클릭
4. 두 번째 Webhook URL 복사

---

## .env 파일 업데이트

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system
nano .env
```

다음 줄을 수정:
```bash
# 일반 리포트용 (필수)
SCOUT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T01234567/B01234567/복사한URL

# 긴급 알림용 (선택사항)
SCOUT_SLACK_URGENT_WEBHOOK_URL=https://hooks.slack.com/services/T11111111/B11111111/복사한URL
```

저장 후:
```bash
docker-compose restart daily_scout
```

---

## 테스트

### 터미널에서 즉시 테스트

```bash
# Webhook URL을 변수로 설정
WEBHOOK_URL="복사한_Webhook_URL"

# 테스트 메시지 발송
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "✅ Daily Wellness Scout 연동 테스트 성공!"
  }'
```

**성공 응답**: `ok`
**실패 응답**: `invalid_payload` 또는 `404`

### Daily Scout로 전체 테스트

```bash
# .env에서 SCOUT_RUN_IMMEDIATELY=true 확인
docker-compose restart daily_scout

# 로그 확인
docker logs image-localization-system-daily_scout-1 -f
```

---

## 자주 하는 실수

### ❌ OAuth 토큰 사용
```
잘못된 예: xoxe.xoxp-1-...
```
→ 이것은 OAuth 토큰이며, Webhook URL이 아닙니다.

### ✅ 올바른 Webhook URL
```
올바른 예: https://hooks.slack.com/services/T.../B.../...
```

---

## Slack 채널 권장 구조

```
#daily-wellness-report     → 일반 리포트 (매일 오전 9시)
#urgent-wellness-alerts    → 긴급 알림 (트렌드 점수 90+)
```

---

## 문제 해결

### "Channel not found" 에러
→ Slack에서 먼저 채널 생성 후 Webhook 재설정

### "No service" 에러
→ Webhook이 삭제됨, 새로 생성 필요

### 알림이 안 옴
→ `.env` 파일의 Webhook URL 다시 확인
→ `docker-compose restart daily_scout` 실행 확인

---

## 완료 후 다음 단계

Webhook URL 설정 완료 후:

1. `.env` 파일 저장
2. `docker-compose restart daily_scout`
3. `docker logs image-localization-system-daily_scout-1 -f`로 로그 확인
4. Slack 채널에서 알림 수신 확인

**예상 로그**:
```
2026-03-28 09:00:32,678 - __main__ - INFO - 📢 슬랙 알림 발송 완료
```

---

## 현재 설정 상태 요약

| 항목 | 상태 | 값 |
|------|------|-----|
| Anthropic API | ⚠️ 모델 접근 불가 | 크레딧 확인 필요 |
| Gmail | ✅ 설정 완료 | dydgh595942yy@gmail.com |
| Slack | ❌ 설정 필요 | Webhook URL 생성 필요 |

위 가이드에 따라 Slack Webhook URL만 추가하면 완료됩니다!
