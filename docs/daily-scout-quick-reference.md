# Daily Wellness Scout - 빠른 참조 가이드

**마지막 업데이트**: 2026-03-29

---

## 🚨 긴급 트러블슈팅

### 시스템이 작동하지 않을 때

```bash
# 1. 컨테이너 상태 확인
docker ps | grep daily_scout

# 2. 로그 확인 (최근 50줄)
docker logs image-localization-system-daily_scout-1 --tail 50

# 3. 컨테이너 재시작
docker-compose restart daily_scout

# 4. 전체 재빌드 (설정 변경 시)
docker-compose build --no-cache daily_scout
docker-compose up -d daily_scout
```

---

## ⚙️ 설정 파일 위치

| 항목 | 경로 |
|------|------|
| 환경 변수 | `/home/fortymove/Fortimove-OS/image-localization-system/.env` |
| 소스 코드 | `/home/fortymove/Fortimove-OS/daily-scout/app/daily_scout.py` |
| Docker 설정 | `/home/fortymove/Fortimove-OS/image-localization-system/docker-compose.yml` |
| 데이터베이스 | `/app/data/wellness_trends.db` (컨테이너 내부) |

---

## 🔑 현재 인증 정보

### Anthropic Claude API
```bash
API_KEY=sk-ant-api03-YOUR_API_KEY_HERE
MODEL=claude-sonnet-4-5-20250929
```

### Gmail SMTP
```bash
EMAIL_SENDER=dydgh595942yy@gmail.com
EMAIL_PASSWORD=YOUR_APP_PASSWORD_HERE
EMAIL_RECIPIENTS=dydgh595942yy@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

### Slack Webhook
```bash
WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## 📊 데이터 조회 방법

### 최근 저장된 상품 확인
```bash
docker exec image-localization-system-daily_scout-1 python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/wellness_trends.db')
cursor = conn.cursor()
cursor.execute('SELECT product_name, region, risk_status, trend_score FROM products ORDER BY created_at DESC LIMIT 10')
for row in cursor.fetchall():
    print(f'{row[1]} | {row[0][:30]} | {row[2]} | {row[3]}')
conn.close()
"
```

### 일별 통계 확인
```bash
docker exec image-localization-system-daily_scout-1 python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/wellness_trends.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM daily_stats ORDER BY created_at DESC LIMIT 5')
for row in cursor.fetchall():
    print(f'{row[1]} | 분석:{row[2]} | 통과:{row[3]} | 보류:{row[4]}')
conn.close()
"
```

---

## 🧪 수동 테스트 방법

### API 키 테스트
```bash
curl -s https://api.anthropic.com/v1/messages \
  -H "x-api-key: sk-ant-api03-YOUR_API_KEY_HERE" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```

### Slack Webhook 테스트
```bash
curl -X POST "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  -H "Content-Type: application/json" \
  -d '{"text":"테스트 메시지입니다"}'
```

### Gmail SMTP 테스트
```python
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("테스트 메시지")
msg['Subject'] = "테스트"
msg['From'] = "dydgh595942yy@gmail.com"
msg['To'] = "dydgh595942yy@gmail.com"

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login("dydgh595942yy@gmail.com", "YOUR_APP_PASSWORD_HERE")
server.send_message(msg)
server.quit()
print("✅ 이메일 발송 성공")
```

---

## 🔄 스케줄 변경 방법

### `.env` 파일 수정
```bash
# 실행 시간 변경 (예: 오전 6시로 변경)
SCOUT_SCHEDULE_TIME=06:00

# 즉시 실행 비활성화 (테스트 후)
SCOUT_RUN_IMMEDIATELY=false
```

### 변경 사항 적용
```bash
docker-compose restart daily_scout
```

---

## 📈 성능 모니터링

### 리소스 사용량 확인
```bash
docker stats image-localization-system-daily_scout-1 --no-stream
```

### 실행 중인 프로세스 확인
```bash
docker exec image-localization-system-daily_scout-1 ps aux
```

### 디스크 사용량 확인
```bash
docker exec image-localization-system-daily_scout-1 du -sh /app/data/
```

---

## 🐛 일반적인 오류와 해결책

### Error: "404 not_found_error" (API)
**원인**: API 키 만료 또는 Spending cap 도달
**해결**:
1. Anthropic Console에서 크레딧 확인
2. 새 API 키 생성
3. `.env` 파일 업데이트
4. `docker-compose restart daily_scout`

### Error: "535 Authentication failed" (Gmail)
**원인**: 앱 비밀번호 오류
**해결**:
1. Google 계정 → 보안 → 2단계 인증
2. 앱 비밀번호 재생성
3. `.env` 파일 업데이트 (공백 제거)
4. `docker-compose restart daily_scout`

### Error: "404 invalid_webhook_url" (Slack)
**원인**: Webhook URL 오류
**해결**:
1. Slack Workspace → 앱 관리
2. Incoming Webhooks 설정 확인
3. URL이 `https://hooks.slack.com/services/...` 형식인지 확인
4. `.env` 파일 업데이트
5. `docker-compose restart daily_scout`

### Error: "JSON parsing error"
**원인**: Claude가 잘못된 JSON 생성 (5-10% 발생)
**영향**: 일부 상품만 실패, 나머지는 정상 처리
**해결**: 현재 자동 처리됨 (try-catch로 graceful degradation)

---

## 📋 체크리스트

### 매일 확인할 것
- [ ] 이메일 리포트 수신 확인 (`dydgh595942yy@gmail.com`)
- [ ] Slack 알림 확인
- [ ] 통과 상품 리스트 검토
- [ ] 보류 상품 리스크 요인 파악

### 주간 확인할 것
- [ ] 데이터베이스 크기 확인
- [ ] 트렌드 분석 (카테고리별 통계)
- [ ] API 사용량 확인 (Anthropic Console)
- [ ] 시스템 로그 검토

### 월간 확인할 것
- [ ] API 키 만료일 확인
- [ ] Gmail 앱 비밀번호 유효성 확인
- [ ] Slack Webhook 상태 확인
- [ ] 스케줄 최적화 검토

---

## 🆘 긴급 연락처

**시스템 관련 문의**:
- GitHub Issues: [Fortimove-OS Repository](https://github.com/fortymove/fortimove-os)
- Email: dydgh595942yy@gmail.com

**서비스 제공자**:
- Anthropic Support: https://support.anthropic.com
- Google Workspace Support: https://support.google.com
- Slack Support: https://slack.com/help

---

## 📚 추가 문서

1. [설정 완료 요약](./setup-completion-summary.md) - 전체 개요
2. [성공 리포트](./daily-scout-success-report.md) - 상세 기술 문서
3. [Anthropic API 가이드](./anthropic-api-setup.md)
4. [알림 설정 가이드](./notification-setup.md)
5. [Slack Webhook 가이드](./slack-webhook-guide.md)

---

**💡 Tip**: 이 문서를 북마크하고 문제 발생 시 먼저 확인하세요!
