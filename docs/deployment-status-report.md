# PM Agent Production 배포 상태 보고서

**배포 일시**: 2026-03-31 01:15 KST
**배포 서버**: stg-pm-agent-01 (Gabia Cloud)
**배포 상태**: ✅ 80% 완료 (API 키 설정 및 SSL 발급 대기)

---

## 1. 완료된 작업 ✅

### 1-1. 서버 기본 인프라
- [x] SSH 접속 및 PEM 키 설정 완료
- [x] Ubuntu 22.04 시스템 업데이트 (127개 패키지)
- [x] 필수 패키지 설치 (nginx, certbot, python3, git 등 90개)
- [x] UFW 방화벽 설정 (22/80/443 포트 허용)

### 1-2. 애플리케이션 배포
- [x] Git 저장소 클론 (`JYH54/Fortimove-OS`)
- [x] pm-agent 디렉토리 서버에 복사 (1.9MB)
- [x] Python 3.10 가상환경 생성
- [x] 패키지 설치 (anthropic==0.30.0, fastapi, uvicorn 등)

### 1-3. 환경 설정
- [x] `.env` 파일 생성
- [x] **ADMIN_TOKEN 생성**: `def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95`
- [x] 데이터 디렉토리 생성 (`/home/ubuntu/pm-agent-data`)
- [x] 권한 설정 (700)

### 1-4. 서비스 등록
- [x] systemd 서비스 파일 생성 (`/etc/systemd/system/pm-agent.service`)
- [x] 서비스 활성화 (부팅 시 자동 시작 설정)
- [x] Nginx 리버스 프록시 설정 (`/etc/nginx/sites-available/pm-agent`)
- [x] Nginx 설정 활성화 및 재로드

---

## 2. 대기 중인 작업 ⏳

### 2-1. 필수 작업 (서비스 시작 전)

#### ① ANTHROPIC_API_KEY 설정
**현재 상태**: 플레이스홀더 (`sk-ant-REPLACE_WITH_YOUR_ACTUAL_KEY`)

**설정 방법**:
```bash
# 서버 접속
ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96

# .env 파일 편집
nano ~/Fortimove-OS/pm-agent/.env

# ANTHROPIC_API_KEY 라인을 실제 키로 교체:
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_ACTUAL_KEY_HERE

# 저장 후 서비스 시작
sudo systemctl start pm-agent
sudo systemctl status pm-agent
```

#### ② 도메인 DNS 설정
**현재 상태**: Nginx는 임시 설정 (`server_name _`)으로 동작 중

**설정 방법**:
1. Gabia DNS 관리 페이지 접속
2. A 레코드 추가:
   - 호스트명: `@` (또는 서브도메인, 예: `agent`)
   - 레코드 타입: A
   - 값: `1.201.124.96`
   - TTL: 3600
3. DNS 전파 확인 (5-30분 소요):
   ```bash
   nslookup your-domain.com
   # 1.201.124.96이 응답하는지 확인
   ```

#### ③ Nginx 도메인 설정 업데이트
**DNS 전파 완료 후 실행**:
```bash
# 서버 접속
ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96

# Nginx 설정 파일 편집
sudo nano /etc/nginx/sites-available/pm-agent

# server_name _; 라인을 실제 도메인으로 변경:
server_name your-domain.com;  # 예: pm-agent.fortimove.com

# Nginx 재시작
sudo nginx -t
sudo systemctl reload nginx
```

---

### 2-2. 보안 작업 (Production 필수)

#### ④ SSL 인증서 발급 (Let's Encrypt)
**전제 조건**: DNS 설정 완료 및 전파 확인

**발급 방법**:
```bash
# 서버 접속
ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96

# Let's Encrypt 인증서 자동 발급
sudo certbot --nginx -d your-domain.com

# 프롬프트에서:
# - 이메일 입력: admin@fortimove.com
# - 약관 동의: Y
# - HTTPS 리다이렉트 설정: 2 (Redirect)

# 자동 갱신 테스트
sudo certbot renew --dry-run
```

**예상 결과**:
- HTTP (80) → HTTPS (443) 자동 리다이렉트
- 90일마다 자동 갱신 (cron 자동 설정)

---

## 3. 배포 검증 체크리스트

### Step 1: 로컬 서비스 테스트
```bash
# 서버 내부에서 서비스 확인
ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96

# 서비스 시작
sudo systemctl start pm-agent
sudo systemctl status pm-agent

# Health Check
curl http://127.0.0.1:8000/health

# 예상 응답:
# {"status":"healthy","timestamp":"2026-03-31T..."}
```

### Step 2: 외부 접속 테스트 (HTTP)
```bash
# 로컬에서 실행
curl http://1.201.124.96/health

# 도메인 설정 완료 후:
curl http://your-domain.com/health
```

### Step 3: HTTPS 테스트 (SSL 발급 후)
```bash
# 브라우저에서 접속
https://your-domain.com/health

# 또는 curl로:
curl https://your-domain.com/health
```

### Step 4: Admin UI 접속
```bash
# 브라우저에서:
https://your-domain.com/admin

# ADMIN_TOKEN 입력:
def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95
```

---

## 4. 서버 정보 요약

| 항목 | 값 |
|------|-----|
| 서버명 | stg-pm-agent-01 |
| 공인 IP | 1.201.124.96 |
| 내부 IP | 192.168.0.9 |
| OS | Ubuntu 22.04 LTS |
| 스펙 | 1vCore, 2GB RAM, 50GB SSD |
| SSH 접속 | `ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96` |
| 프로젝트 경로 | `/home/ubuntu/Fortimove-OS/pm-agent` |
| 데이터 경로 | `/home/ubuntu/pm-agent-data` |
| systemd 서비스 | `pm-agent.service` |
| Nginx 설정 | `/etc/nginx/sites-available/pm-agent` |

---

## 5. 중요 자격 증명 정보 🔑

### ADMIN_TOKEN (반드시 안전한 곳에 저장!)
```
def98d917135283ce92f5e74d536093cf3baf8133f9e44588c6625489f3d9c95
```

**사용 용도**:
- Admin UI 로그인 (`/admin` 엔드포인트)
- API 인증 헤더: `Authorization: Bearer {ADMIN_TOKEN}`

**보안 주의사항**:
- 이 토큰은 재생성 불가
- 1Password, Bitwarden 등 비밀번호 관리자에 저장
- GitHub에 커밋 금지 (`.gitignore`로 차단됨)

### SSH 키 파일 위치
```
로컬: /home/fortymove/fortimove-pm-agent-key.pem
원본: OneDrive/바탕 화면/사업/포티무브 글로벌/키페어/fortimove-pm-agent-key.pem
```

---

## 6. 다음 단계 (우선순위 순)

### 즉시 필요 (Critical)
1. ✅ **ANTHROPIC_API_KEY 설정** → 서비스 시작
2. ✅ **도메인 DNS 설정** → Nginx 업데이트
3. ✅ **SSL 인증서 발급** → HTTPS 활성화

### 1주일 내 (High)
4. **Slack/Email 알림 설정** (`.env`에 SLACK_WEBHOOK_URL 추가)
5. **모니터링 설정** (Uptime monitoring, Prometheus/Grafana)
6. **백업 자동화** (SQLite DB 일일 백업)

### 1개월 내 (Medium)
7. **Korean Law MCP 통합** (법제처 API 승인 시)
8. **Phase 5-7 Agent 구현** (Pricing, Inventory, Analytics)
9. **Load Testing** (성능 및 부하 테스트)

---

## 7. 트러블슈팅 가이드

### 문제 1: pm-agent 서비스가 시작 안 됨
```bash
# 로그 확인
sudo journalctl -u pm-agent -n 50

# 일반적인 원인:
# - ANTHROPIC_API_KEY 미설정 → .env 파일 확인
# - Python 패키지 누락 → venv/bin/pip list
# - 포트 충돌 → lsof -i :8000
```

### 문제 2: Nginx 502 Bad Gateway
```bash
# pm-agent 서비스 상태 확인
sudo systemctl status pm-agent

# 127.0.0.1:8000 직접 접속
curl http://127.0.0.1:8000/health

# Nginx 에러 로그
sudo tail -f /var/log/nginx/error.log
```

### 문제 3: SSL 인증서 발급 실패
```bash
# DNS 전파 재확인
nslookup your-domain.com

# Certbot dry-run
sudo certbot certonly --nginx --dry-run -d your-domain.com

# 일반적인 원인:
# - DNS 미전파 (30분 대기)
# - 80포트 차단 (ufw allow 80/tcp)
# - 도메인 소유 인증 실패
```

---

## 8. 유지보수 명령어 모음

### 서비스 관리
```bash
# 서비스 시작/중지/재시작
sudo systemctl start pm-agent
sudo systemctl stop pm-agent
sudo systemctl restart pm-agent

# 서비스 상태 확인
sudo systemctl status pm-agent

# 로그 실시간 확인
sudo journalctl -u pm-agent -f
```

### 코드 업데이트
```bash
# 서버 접속
ssh -i ~/fortimove-pm-agent-key.pem ubuntu@1.201.124.96

# Git pull
cd ~/Fortimove-OS/pm-agent
git pull origin main

# 패키지 업데이트 (필요 시)
source venv/bin/activate
pip install -r requirements.txt

# 서비스 재시작
sudo systemctl restart pm-agent
```

### Nginx 관리
```bash
# 설정 테스트
sudo nginx -t

# 재로드 (다운타임 없음)
sudo systemctl reload nginx

# 재시작
sudo systemctl restart nginx

# 로그 확인
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 9. 현재 상태 요약

### ✅ 완료 (80%)
- 서버 인프라 구축 완료
- 애플리케이션 배포 완료
- systemd 서비스 등록 완료
- Nginx 리버스 프록시 설정 완료
- 방화벽 설정 완료

### ⏳ 대기 중 (20%)
- ANTHROPIC_API_KEY 설정 필요
- 도메인 DNS 설정 필요
- SSL 인증서 발급 필요

### 🎯 배포 완료 조건
위 3가지 대기 작업 완료 시 → **100% Production Ready**

---

## 10. 연락처 및 지원

**배포 담당**: Claude Code
**배포 일시**: 2026-03-31 01:15 KST
**배포 문서**: [/home/fortymove/Fortimove-OS/pm-agent/DEPLOYMENT.md](../pm-agent/DEPLOYMENT.md)

**추가 지원 필요 시**:
1. ANTHROPIC_API_KEY 발급: https://console.anthropic.com/settings/keys
2. 도메인 설정: Gabia DNS 관리 페이지
3. SSL 인증서: Let's Encrypt (무료, 자동 갱신)

---

**다음 작업**: 위 "다음 단계" 섹션의 Critical 항목 3가지를 완료하면 즉시 Production 서비스 시작 가능합니다.
