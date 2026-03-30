# 🐳 Docker Desktop WSL2 연동 가이드

## 📌 현재 상황
- ✅ Docker Desktop이 Windows에 설치됨
- ❌ WSL2 (Ubuntu)와 연동 안 됨
- ❌ `docker-compose` 명령어 실행 불가

---

## 🚀 해결 방법 (30초 소요)

### Step 1: Docker Desktop 열기
```
Windows 검색창에서 "Docker Desktop" 검색 후 실행
```

### Step 2: 설정 메뉴 들어가기
```
1. Docker Desktop 창 우측 상단 톱니바퀴 아이콘 (⚙️) 클릭
2. "Resources" 메뉴 선택
3. "WSL Integration" 클릭
```

### Step 3: Ubuntu 연동 활성화
```
1. "Enable integration with my default WSL distro" 체크
2. 아래 "Ubuntu" (또는 사용 중인 배포판) 토글을 ON으로 변경
3. "Apply & Restart" 버튼 클릭
```

### Step 4: Docker Desktop 재시작 대기
```
Docker Desktop이 재시작됩니다 (약 10~20초 소요)
"Docker Desktop is running" 메시지 확인
```

---

## ✅ 연동 확인

### WSL 터미널에서 확인
```bash
# docker 명령어 확인
docker --version
# 예상 출력: Docker version 24.x.x, build ...

# docker-compose 확인
docker-compose --version
# 예상 출력: Docker Compose version v2.x.x

# Docker 데몬 연결 확인
docker ps
# 예상 출력: CONTAINER ID   IMAGE   ...
```

모두 정상 출력되면 ✅ 연동 완료!

---

## 🎯 다음 단계: 시스템 시작

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# Docker 컨테이너 시작
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f backend
```

---

## ❗ 문제 해결

### "Cannot connect to the Docker daemon" 에러
```bash
# Docker Desktop이 실행 중인지 확인
# Windows에서 Docker Desktop 아이콘이 시스템 트레이에 있어야 함
```

### "permission denied" 에러
```bash
# 사용자를 docker 그룹에 추가 (Windows에서)
# 일반적으로 WSL2에서는 필요 없음
```

### 여전히 안 되는 경우
```bash
# WSL 재시작
wsl --shutdown
# 그리고 다시 WSL 터미널 열기
```

---

## 📸 스크린샷 가이드

### Docker Desktop 설정 경로:
```
Docker Desktop
  └─ ⚙️ Settings
      └─ Resources
          └─ WSL Integration
              └─ ☑ Enable integration with my default WSL distro
              └─ Ubuntu: [ON] 👈 여기를 켜세요!
              └─ [Apply & Restart]
```

---

## 💡 참고

- **Docker Desktop 버전**: 최신 버전 권장 (4.x 이상)
- **WSL2 버전**: Ubuntu 20.04 이상 권장
- **메모리**: Docker Desktop에 최소 4GB 메모리 할당 권장

설정 후에도 문제가 있으면 알려주세요!
