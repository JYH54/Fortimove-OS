# Fortimove MD Dashboard - Premium Wellness Sourcing Intelligence

## 개요

Daily Wellness Scout가 수집한 웰니스 소싱 데이터를 실시간으로 조회하고 필터링할 수 있는 프리미엄 웹 대시보드입니다.

**기술 스택**: FastAPI + Jinja2 + TailwindCSS + SQLite

## 아키텍처

```
┌─────────────────────────────────────────────┐
│   Daily Wellness Scout (Crawler Agent)     │
│   └─> SQLite DB (wellness_trends.db)       │
└─────────────────┬───────────────────────────┘
                  │ Read-only Volume Share
                  ▼
┌─────────────────────────────────────────────┐
│      MD Dashboard (FastAPI Backend)         │
│   ┌─────────────────────────────────────┐   │
│   │  Backend: main.py                   │   │
│   │  - /api/products (필터링 지원)      │   │
│   │  - /api/stats (요약 통계)           │   │
│   │  - /health (헬스 체크)              │   │
│   └─────────────────────────────────────┘   │
│                                              │
│   ┌─────────────────────────────────────┐   │
│   │  Frontend: templates/index.html     │   │
│   │  - TailwindCSS Glassmorphism        │   │
│   │  - 실시간 필터링 & 검색              │   │
│   │  - 반응형 디자인                     │   │
│   └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                  │
                  ▼
            http://localhost:8050
```

## 주요 기능

### 1. 요약 통계 위젯 (Summary Widgets)

- **오늘 수집된 상품**: 당일 크롤링된 총 상품 수
- **리스크 통과**: 리스크 검토를 통과한 상품 수
- **검토 보류**: 추가 검토가 필요한 상품 수
- **최고 트렌드 점수**: 가장 높은 트렌드 점수

각 위젯은 glassmorphism 효과와 smooth hover 애니메이션 적용.

### 2. 필터링 바 (Filter Bar)

다음 조건으로 상품을 실시간 필터링:

- **지역 (Region)**: japan, us, uk, china 등
- **카테고리 (Category)**: 단백질/프로틴, 영양제/보충제 등
- **리스크 상태 (Risk Status)**: 통과, 보류

### 3. 상품 데이터 테이블 (Product Data Grid)

표시 항목:

- 지역 (Region Badge)
- 상품명 (Product Name) + AI 평가 요약 (Overall Reason)
- 브랜드 (Brand)
- 가격 (Price)
- 카테고리 (Category)
- 트렌드 점수 (Trend Score) - 원형 배지로 표시
- 리스크 상태 (Status Badge)
- 원본 URL (외부 링크 버튼)

## API 엔드포인트

### GET /

메인 대시보드 페이지 (HTML)

### GET /api/products

상품 데이터 조회 (JSON)

**Query Parameters**:
- `region` (optional): 지역 필터 (예: japan, us)
- `category` (optional): 카테고리 필터
- `risk_status` (optional): 리스크 상태 (통과/보류)
- `limit` (default: 100): 최대 결과 수

**Response Example**:
```json
{
  "success": true,
  "count": 5,
  "data": [
    {
      "id": 21,
      "date": "2026-03-29",
      "region": "japan",
      "product_name": "Optimum Nutrition Gold Standard Whey",
      "brand": "Optimum Nutrition",
      "price": "¥11,269",
      "category": "단백질/프로틴",
      "trend_score": 98,
      "risk_status": "통과",
      "url": "https://jp.iherb.com/pr/..."
    }
  ]
}
```

### GET /api/stats

요약 통계 조회 (JSON)

**Response Example**:
```json
{
  "success": true,
  "data": {
    "total": 30,
    "passed": 25,
    "pending": 5,
    "rejected": 0,
    "region_stats": {
      "japan": 15,
      "us": 15
    },
    "max_score": 98,
    "date": "2026-03-29"
  }
}
```

### GET /health

헬스 체크 (JSON)

## 설치 및 실행

### Docker Compose로 실행

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# 대시보드 빌드
docker-compose build scout_dashboard

# 대시보드 시작
docker-compose up -d scout_dashboard

# 로그 확인
docker logs image-localization-system-scout_dashboard-1 --tail 50
```

### 접속

브라우저에서 접속:
```
http://localhost:8050
```

### 헬스 체크

```bash
curl http://localhost:8050/health
```

## 디렉토리 구조

```
daily-scout/dashboard/
├── Dockerfile              # 컨테이너 빌드 설정
├── requirements.txt        # Python 의존성
├── main.py                # FastAPI 백엔드
└── templates/
    └── index.html         # Jinja2 템플릿 (프리미엄 UI)
```

## 의존성

### Backend (Python)

- `fastapi==0.109.0` - 웹 프레임워크
- `uvicorn[standard]==0.27.0` - ASGI 서버
- `jinja2==3.1.3` - 템플릿 엔진
- `aiosqlite==0.19.0` - 비동기 SQLite 접근
- `python-dateutil==2.8.2` - 날짜 처리

### Frontend (CDN)

- **TailwindCSS 3.x** - 유틸리티 CSS 프레임워크
- **FontAwesome 6.4.0** - 아이콘 라이브러리
- **Google Fonts (Inter)** - 웹 폰트

## 디자인 특징

### Glassmorphism 효과

```css
.glass {
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
}
```

### Smooth Animations

- Fade-in 애니메이션 (0.6s ease-in)
- Hover lift 효과 (transform: translateY(-4px))
- 스태거드 애니메이션 (각 행마다 0.02s 지연)

### Gradient Backgrounds

- 메인 배경: Purple to Pink gradient (135deg, #667eea → #764ba2)
- 위젯 아이콘: 각각 색상별 gradient (Blue, Green, Orange, Purple)
- 상태 배지: 통과 (Purple), 보류 (Pink-Red)

## 보안 고려사항

### Read-only Volume Mount

대시보드는 Daily Scout의 SQLite DB를 **읽기 전용**으로 마운트:

```yaml
volumes:
  - scout_data:/app/data:ro  # Read-only
```

이를 통해:
- 대시보드가 실수로 데이터를 수정하는 것 방지
- Daily Scout의 데이터 무결성 보호

### SQLite 동시성 처리

- 각 요청마다 새로운 DB 연결 생성
- 명시적인 cursor.close() 및 db.close() 호출
- try-finally 블록으로 리소스 누수 방지

## 모니터링

### 컨테이너 상태 확인

```bash
docker-compose ps scout_dashboard
```

### 로그 실시간 조회

```bash
docker logs -f image-localization-system-scout_dashboard-1
```

### 헬스체크

Docker Compose는 30초마다 자동 헬스체크 실행:

```yaml
healthcheck:
  test: python -c "import urllib.request; urllib.request.urlopen('http://localhost:8050/health')"
  interval: 30s
  timeout: 10s
  start_period: 5s
  retries: 3
```

## 향후 개선 사항

### 단기

- [ ] 날짜 범위 필터 추가 (오늘/최근 7일/최근 30일)
- [ ] 상품 상세 모달 (클릭 시 전체 정보 표시)
- [ ] 페이지네이션 (현재 limit=100)
- [ ] 검색 기능 (상품명, 브랜드 검색)

### 중기

- [ ] CSV/Excel 내보내기 기능
- [ ] 트렌드 차트 (일별 수집 추이)
- [ ] 지역별/카테고리별 비교 분석
- [ ] 사용자 인증 (로그인 기능)

### 장기

- [ ] PostgreSQL 마이그레이션 (SQLite → PostgreSQL)
- [ ] 실시간 웹소켓 업데이트 (크롤링 진행 상황)
- [ ] 알림 설정 (특정 조건 만족 시 Slack/Email)
- [ ] AI 추천 엔진 (유망 상품 자동 추천)

## 문제 해결

### 대시보드가 시작되지 않음

```bash
# 로그 확인
docker logs image-localization-system-scout_dashboard-1

# 컨테이너 재시작
docker-compose restart scout_dashboard

# 강제 재빌드
docker-compose build --no-cache scout_dashboard
docker-compose up -d scout_dashboard
```

### 데이터가 표시되지 않음

1. Daily Scout가 실행 중인지 확인:
   ```bash
   docker-compose ps daily_scout
   ```

2. DB 파일이 존재하는지 확인:
   ```bash
   docker exec image-localization-system-daily_scout-1 ls -la /app/data/
   ```

3. DB에 데이터가 있는지 확인:
   ```bash
   curl -s "http://localhost:8050/api/products?limit=5"
   ```

### API 오류 발생

```bash
# API 엔드포인트 직접 테스트
curl -s "http://localhost:8050/health"
curl -s "http://localhost:8050/api/stats"
curl -s "http://localhost:8050/api/products?region=japan&limit=10"
```

## 연관 문서

- [Daily Wellness Scout 크롤러 업그레이드 리포트](daily-scout-crawler-upgrade-report.md)
- [Playwright 하이브리드 크롤러 리포트](playwright-hybrid-crawler-report.md)
- [소싱 SOP](sourcing-sop.md)

---

**작성일**: 2026-03-29
**작성자**: Claude (Fortimove AI Assistant)
**버전**: 1.0.0
