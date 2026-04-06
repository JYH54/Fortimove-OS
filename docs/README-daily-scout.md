# Daily Wellness Scout - 완전 가이드

**버전**: 1.0.0
**상태**: ✅ Production Ready
**마지막 업데이트**: 2026-03-29

---

## 📌 시작하기

Daily Wellness Scout는 전 세계 웰니스 트렌드를 자동으로 스캔하고, AI로 한국 시장 진입 가능성을 분석하는 자동화 에이전트입니다.

### 현재 시스템 상태

| 항목 | 상태 |
|------|------|
| Docker 컨테이너 | ✅ 실행 중 |
| Anthropic Claude API | ✅ 정상 |
| Gmail 이메일 발송 | ✅ 정상 |
| Slack 알림 | ✅ 정상 |
| 데이터베이스 | ✅ 정상 |
| 자동 스케줄러 | ✅ 매일 09:00 실행 |

**다음 실행 예정**: 2026-03-29 09:00 UTC (KST 18:00)

---

## 📖 문서 구조

### 1️⃣ 빠른 시작 (이 문서)
이 문서를 읽고 있습니다 - 전체 개요와 링크 제공

### 2️⃣ [설정 완료 요약](./setup-completion-summary.md)
- 완료된 작업 전체 목록
- 실행 결과 통계
- 적용된 설정 상세
- 해결한 이슈들

### 3️⃣ [빠른 참조 가이드](./daily-scout-quick-reference.md)
- 긴급 트러블슈팅
- 데이터 조회 방법
- 테스트 명령어
- 일반적인 오류 해결

### 4️⃣ [성공 리포트](./daily-scout-success-report.md)
- 상세 기술 문서
- 시스템 아키텍처
- 성능 통계
- 향후 개선 방안

### 5️⃣ 설정 가이드
- [Anthropic API 설정](./anthropic-api-setup.md)
- [이메일/Slack 알림 설정](./notification-setup.md)
- [Slack Webhook 5분 가이드](./slack-webhook-guide.md)

---

## 🎯 Daily Wellness Scout가 하는 일

### 자동 실행 프로세스

```
09:00 UTC
  ↓
┌─────────────────────────────────────┐
│ 1. 4개 지역 스캔 (15개씩)           │
│    • 일본 (Rakuten)                 │
│    • 중국 (Xiaohongshu)             │
│    • 미국 (Amazon)                  │
│    • 영국 (Holland & Barrett)       │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ 2. Claude AI 리스크 분석            │
│    • 의료기기 오인 가능성           │
│    • 건강기능식품 인증 필요 여부    │
│    • 상표권/디자인권 침해 위험      │
│    • 통관 제한 여부                 │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ 3. 자동 분류                        │
│    • 통과: 즉시 소싱 가능           │
│    • 보류: 추가 검토 필요           │
│    • 거부: 판매 불가                │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ 4. 리포트 발송                      │
│    • 이메일: HTML 상세 리포트       │
│    • Slack: 핫 아이템 즉시 알림     │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ 5. 데이터베이스 저장                │
│    • 상품 정보 누적                 │
│    • 트렌드 분석용 통계 저장        │
└─────────────────────────────────────┘
```

---

## 📊 최근 실행 결과 (2026-03-29 00:07)

### 성과 요약
- ✅ **58개 상품** 스캔 완료
- ✅ **17분 23초** 소요
- ✅ **100% API 성공률** (모든 호출 정상)
- ✅ **10개 상품** 데이터베이스 저장
- ✅ **이메일 발송** 완료
- ✅ **Slack 알림** 완료

### 분류 결과
```
통과 (즉시 소싱 가능): 6개
보류 (추가 검토 필요): 4개
거부 (판매 불가): 48개
```

### Top 5 추천 상품
1. **옵티멈 뉴트리션 골드 스탠다드 프로틴** (미국, 94점)
2. **임팩트 웨이 프로틴 아이솔레이트** (영국, 94점)
3. **스와니 콜라겐 펩타이드** (중국, 92점)
4. **비타민 D3 4000IU** (영국, 92점)
5. **DHC 멀티비타민 미네랄** (일본, 91점)

---

## 🔧 빠른 명령어

### 시스템 상태 확인
```bash
docker ps | grep daily_scout
```

### 로그 보기
```bash
docker logs image-localization-system-daily_scout-1 --tail 50
```

### 데이터베이스 조회
```bash
docker exec image-localization-system-daily_scout-1 python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/wellness_trends.db')
cursor = conn.cursor()
cursor.execute('SELECT product_name, region, risk_status FROM products ORDER BY created_at DESC LIMIT 10')
for row in cursor.fetchall():
    print(f'{row[1]} | {row[0][:40]} | {row[2]}')
conn.close()
"
```

### 컨테이너 재시작
```bash
docker-compose restart daily_scout
```

---

## 📧 알림 받는 방법

### 이메일
- **수신 계정**: `dydgh595942yy@gmail.com`
- **제목 형식**: `[Fortimove] Daily Wellness Scout - YYYY-MM-DD`
- **내용**: HTML 리포트 (상품 목록, 리스크 분석, 통계)

### Slack
- **워크스페이스**: Fortimove
- **알림 형식**:
  ```
  📊 Daily Wellness Scout 완료
  • 통과: X개
  • 보류: X개
  • Top 카테고리: XXX

  🔥 핫 아이템 X개 발견!
  ```

---

## 🛠️ 트러블슈팅

### 이메일이 안 오는 경우
1. Gmail 스팸함 확인
2. 로그 확인: `docker logs ... | grep 이메일`
3. SMTP 설정 확인: [빠른 참조 가이드](./daily-scout-quick-reference.md#-현재-인증-정보)

### Slack 알림이 안 오는 경우
1. Webhook URL 확인
2. 로그 확인: `docker logs ... | grep 슬랙`
3. 테스트: [빠른 참조 가이드](./daily-scout-quick-reference.md#수동-테스트-방법)

### 시스템이 실행 안 되는 경우
1. 컨테이너 상태: `docker ps | grep daily_scout`
2. 재시작: `docker-compose restart daily_scout`
3. 로그 확인: `docker logs ... --tail 100`

**더 자세한 트러블슈팅**: [빠른 참조 가이드](./daily-scout-quick-reference.md#-긴급-트러블슈팅)

---

## 📈 데이터 활용하기

### 데이터베이스 구조
- **products**: 스캔된 모든 상품 정보
- **daily_stats**: 일별 통계 및 인사이트

### 트렌드 분석 예제
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('/app/data/wellness_trends.db')

# 카테고리별 통과율
df = pd.read_sql_query('''
    SELECT category,
           COUNT(*) as total,
           SUM(CASE WHEN risk_status='통과' THEN 1 ELSE 0 END) as passed
    FROM products
    GROUP BY category
''', conn)

print(df)
conn.close()
```

---

## 🚀 다음 단계

### 즉시 할 수 있는 것
1. ✅ 이메일 받은 것 확인하기
2. ✅ Slack 알림 확인하기
3. ✅ 추천 상품 검토하기
4. ✅ 내일 09:00 다시 리포트 받기

### 향후 개선 계획
1. **대시보드 구축**
   - Grafana/Metabase 연동
   - 트렌드 시각화
   - 주간/월간 리포트

2. **지역 확장**
   - 한국 (Coupang, Naver)
   - 호주 (Chemist Warehouse)
   - 캐나다 (Shoppers Drug Mart)

3. **카테고리 확장**
   - 뷰티/화장품
   - 홈케어
   - 펫케어

---

## 📚 전체 문서 목록

### 사용자 가이드
1. [README-daily-scout.md](./README-daily-scout.md) ← 현재 문서
2. [설정 완료 요약](./setup-completion-summary.md)
3. [빠른 참조 가이드](./daily-scout-quick-reference.md)

### 기술 문서
4. [성공 리포트](./daily-scout-success-report.md)
5. [Anthropic API 설정](./anthropic-api-setup.md)
6. [알림 설정 가이드](./notification-setup.md)
7. [Slack Webhook 가이드](./slack-webhook-guide.md)

### 소스 코드
- [daily_scout.py](../daily-scout/app/daily_scout.py)
- [docker-compose.yml](../image-localization-system/docker-compose.yml)
- [.env](../image-localization-system/.env)

---

## 💡 유용한 팁

### 1. 스케줄 변경하기
`.env` 파일에서 `SCOUT_SCHEDULE_TIME=09:00`을 원하는 시간으로 변경

### 2. 즉시 실행 비활성화
`.env` 파일에서 `SCOUT_RUN_IMMEDIATELY=false`로 변경 (안정화 후)

### 3. 수신자 추가
`.env` 파일에서 `SCOUT_EMAIL_RECIPIENTS`에 쉼표로 구분하여 추가
```bash
SCOUT_EMAIL_RECIPIENTS=email1@example.com,email2@example.com
```

### 4. 데이터 백업
```bash
docker cp image-localization-system-daily_scout-1:/app/data/wellness_trends.db ./backup/
```

---

## 🎉 성공 지표

### 시스템 안정성
- ✅ **3회 연속 성공** (2026-03-28 23:04, 23:21, 2026-03-29 00:07)
- ✅ **100% API 성공률**
- ✅ **100% 이메일 발송 성공**
- ✅ **100% Slack 알림 성공**

### 처리 성능
- ⏱️ **평균 실행 시간**: 17분
- 📦 **평균 스캔 상품**: 58개/회
- 💾 **데이터 저장률**: 17% (10/58)
- 🎯 **통과율**: 60% (6/10 저장 상품 중)

---

## 📞 지원

### 문의하기
- **Email**: dydgh595942yy@gmail.com
- **Slack**: Fortimove Workspace

### 긴급 상황
1. [빠른 참조 가이드](./daily-scout-quick-reference.md) 먼저 확인
2. 로그 수집: `docker logs ... --tail 200 > error.log`
3. 이메일로 로그 파일 전송

---

**🎊 Daily Wellness Scout가 성공적으로 가동되고 있습니다!**

**다음 리포트 예정**: 2026-03-29 09:00 UTC (KST 18:00)

---

*마지막 업데이트: 2026-03-29 00:23 UTC*
