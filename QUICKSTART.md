# Fortimove-OS 빠른 시작 가이드

## 0. 개발 환경 (Dev Container — 권장)

> VS Code + Docker만 있으면 Python, DB, 크롤러 등 모든 의존성이 자동 설치됩니다.

**사전 요구**: VS Code, Docker Desktop, [Dev Containers 확장](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

```bash
# 1) WSL2 터미널에서 프로젝트 클론
git clone https://github.com/JYH54/Fortimove-OS.git
cd Fortimove-OS

# 2) VS Code로 열기
code .
```

VS Code에서 좌측 하단 `><` 클릭 → **"Reopen in Container"** 선택  
→ 첫 빌드 시 Python 패키지, Tesseract OCR, Playwright 등 자동 설치 (5~10분)  
→ 이후 재실행 시 수초 내 시작

**자동으로 설정되는 것:**
- Python 3.11 + 전체 패키지 (pm-agent, daily-scout, image-localization)
- PostgreSQL 16 (DB 자동 시작)
- Tesseract OCR (한국어/중국어)
- Playwright Chromium (크롤링용)
- `.env` 파일 자동 생성

```bash
# 컨테이너 안에서 바로 사용
nano .env  # ANTHROPIC_API_KEY 입력
cd pm-agent && python fortimove.py --help
```

---

## 1. 환경 설정 — 수동 (Dev Container 없이 직접 설치할 경우)

```bash
# .env 파일 생성
cp .env.template image-localization-system/.env

# image-localization-system/.env 파일 편집 — 아래 값 입력:
# ANTHROPIC_API_KEY=sk-ant-api03-실제키
# DB_PASSWORD=원하는비밀번호
# SECRET_KEY=랜덤문자열

# pm-agent/.env 파일 생성
cp .env.template pm-agent/.env
# pm-agent/.env 편집 — ANTHROPIC_API_KEY 입력
```

## 2. 전체 시스템 실행 (Docker)

```bash
cd image-localization-system
docker-compose up -d
```

실행되는 서비스:
| 포트 | 서비스 | 용도 |
|------|--------|------|
| 8000 | 이미지 현지화 API | 중국어 이미지 → 한국어 변환 |
| 8001 | PM Agent API | 에이전트 오케스트레이션 + 승인 큐 |
| 8050 | Scout 대시보드 | 글로벌 트렌드 모니터링 |
| 3000 | 프론트엔드 | 이미지 처리 웹 UI |

## 3. 일상 사용법

### 방법 A: 프리미엄 파이프라인 (핵심 — 가장 많이 쓸 도구)

> **스마트스토어 1,000개 제한 정책** — 대량등록은 의미 없습니다.
> 1개 상품을 **초퀄리티로** 만들어서 잘 팔아야 등록 한도가 늘어납니다.

```bash
cd pm-agent

# 1개 상품 → 소싱 리스크 + 마진 분석 + 등록 가치 점수 + 초퀄리티 상세페이지 + 광고 전략
python run_premium.py \
  --title "콜라겐 펩타이드 분말 100g 저분자 피쉬콜라겐" \
  --price 52 \
  --category wellness \
  --target "피부 탄력이 신경 쓰이는 30~40대 여성" \
  --features "저분자 1000달톤" "무맛 무취 분말" "100g 2개월분" "GMP 인증"

# 경쟁사 지정 시 차별화 전략 포함
python run_premium.py \
  --title "비타민C 1000mg 60정" --price 45 \
  --category supplement \
  --competitors "닥터린 비타민C" "종근당 비타민C"
```

```bash
# 미국 소싱 (iHerb, Amazon US)
python run_premium.py \
  --title "Optimum Nutrition Gold Standard Whey 5lbs" \
  --price 65 --country US --category supplement \
  --features "FDA 등록 시설" "GMP 인증" "글로벌 1위"

# 일본 소싱 (라쿠텐, Amazon JP)
python run_premium.py \
  --title "資生堂 コラーゲンパウダー 126g" \
  --price 3500 --country JP --category beauty

# 베트남 소싱
python run_premium.py \
  --title "Noni Juice 500ml" \
  --price 180000 --country VN --category wellness

# 국가별 소싱 가이드 확인
python country_config.py US
python country_config.py JP
```

출력물:
- `reports/premium_*_naver.txt` — 네이버 상세페이지 (복사 붙여넣기용)
- `reports/premium_*_ad_strategy.txt` — 광고 키워드 + 입찰 전략
- `reports/premium_*.json` — 전체 결과 (JSON)

> 국가별로 환율/관세/물류비가 자동 계산되고, 상세페이지에 원산지 신뢰 포인트가 반영됩니다.
> 상품 등록 가치 점수(A~D등급)가 자동 계산됩니다. D등급이면 등록하지 마세요.

### 방법 B: Fast-Track CLI (빠른 검증용)

> **참고**: 타오바오/1688은 크롤링 방어가 강하므로, 브라우저에서 상품 페이지를 보고 **제목/가격을 직접 복사**하여 입력합니다. URL은 참조용으로만 기록됩니다.

```bash
cd pm-agent

# 전체 파이프라인: 소싱→마진→등록→콘텐츠
# (타오바오에서 제목과 가격을 복사하여 입력)
python run_fast_track.py \
  --title "无线充电牙刷 声波电动牙刷" \
  --price 35 \
  --weight 0.3

# URL도 함께 기록 (참조용)
python run_fast_track.py \
  --title "不锈钢保温杯 500ml" \
  --price 28.5 \
  --url "https://item.taobao.com/item.htm?id=642968315"

# 빠른 검증: 소싱+마진만 (30초)
python run_fast_track.py --quick \
  --title "콜라겐 펩타이드 분말 100g" \
  --price 52 --category wellness

# 상세페이지까지 생성 (네이버/쿠팡 본문)
python run_fast_track.py --detail \
  --title "프리미엄 비타민C 1000mg" \
  --price 45 --category supplement

# 콘텐츠만 생성
python run_fast_track.py --content \
  --name "프리미엄 텀블러" \
  --desc "스테인리스 500ml 보온보냉" \
  --platform coupang
```

결과는 `pm-agent/reports/` 폴더에 JSON으로 자동 저장됩니다.

### 방법 B: Scout 수집 → 자동 처리

```bash
cd pm-agent

# Scout가 수집한 상품 목록 확인 (처리 안 함)
python process_scout_queue.py --dry-run

# 트렌드 점수 70 이상만 자동 처리
python process_scout_queue.py --min-score 70

# 일본 상품 10개만 처리
python process_scout_queue.py --region japan --limit 10
```

### 방법 C: HTTP API 직접 호출

```bash
# 전체 워크플로우 실행
curl -X POST http://localhost:8001/api/workflows/run \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "full_product_registration",
    "user_input": {
      "source_url": "https://item.taobao.com/item.htm?id=123",
      "source_title": "상품명",
      "source_price_cny": 35.0,
      "weight_kg": 0.3
    }
  }'

# 승인 큐 확인
curl http://localhost:8001/api/queue?status=pending

# 에이전트 상태 확인
curl http://localhost:8001/api/agents/status
```

### 방법 D: 이미지 현지화

```bash
# 중국어 이미지를 한국 이커머스용으로 변환
curl -X POST http://localhost:8000/api/v1/process \
  -F "files=@상품이미지.jpg" \
  -F "moodtone=premium" \
  -F "brand_type=fortimove_global" \
  -F "generate_seo=true"
```

### 방법 E: 배치 처리 (여러 상품 한꺼번에)

```bash
cd pm-agent

# CSV 파일로 여러 상품 한꺼번에 처리
python run_batch.py sample_products.csv

# 소싱+마진만 빠르게 검증
python run_batch.py sample_products.csv --quick

# 결과 CSV 지정
python run_batch.py sample_products.csv --output reports/result.csv
```

CSV 형식 (`sample_products.csv` 참고):
```csv
url,price,title,weight,category
https://item.taobao.com/item.htm?id=123,35,无线充电牙刷 声波电动,0.3,healthcare
,28.5,不锈钢保温杯 500ml 真空,0.5,general
```
> `url`은 빈 값이어도 됩니다. `title`과 `price`가 핵심 입력입니다.

### 방법 F: 상세페이지까지 생성

```bash
# --detail 옵션으로 네이버/쿠팡 상세페이지 본문까지 생성
python run_fast_track.py \
  --url "https://item.taobao.com/..." --price 35 --title "무선 칫솔" \
  --detail --category wellness
```

### 방법 G: 네이버/쿠팡 등록용 CSV 내보내기

```bash
# 배치 결과에서 네이버/쿠팡 대량등록 CSV 생성
python export_channels.py --input reports/batch_20260402.json --platform all

# 승인 큐에서 approved 상품만 내보내기
python export_channels.py --platform smartstore
python export_channels.py --platform coupang
```

### 방법 H: Markdown 보고서 생성

```bash
# 배치 결과를 보기 좋은 Markdown 보고서로 변환
python report_generator.py reports/batch_20260402.json
python report_generator.py reports/fast_track_20260402.json
```

## 4. API 문서

- PM Agent Swagger: http://localhost:8001/docs
- 이미지 API Swagger: http://localhost:8000/docs
- Scout 대시보드: http://localhost:8050

## 5. 일일 운영 루틴

```
09:00  Daily Scout 자동 실행 (4개국 트렌드 수집)
09:30  Scout 대시보드(localhost:8050)에서 트렌드 점수 80+ 상품 선별
10:00  선별 상품 1~3개에 대해 run_premium.py 실행
       → 등록 가치 점수(A/B등급) 확인
       → A등급만 진행
10:30  premium_*_naver.txt 열어서 상세페이지 복사 → 스마트스토어에 직접 등록
       premium_*_ad_strategy.txt 열어서 네이버 쇼핑 검색광고 설정
11:00  등록한 상품의 광고 키워드/입찰가 세팅
```

**한 줄 요약**: 타오바오에서 제목/가격 복사 → `run_premium.py` → 등록 가치 A등급이면 → 상세페이지+광고전략 복사 붙여넣기 → 판매 시작

## 6. 통합 CLI — `fortimove.py`

모든 도구를 하나의 명령어로 사용할 수 있습니다:

```bash
cd pm-agent

python fortimove.py premium --title "콜라겐 분말" --price 52 --country US --category wellness
python fortimove.py keyword "비타민C"
python fortimove.py daily --auto-premium 1
python fortimove.py sales report
python fortimove.py lifecycle status
python fortimove.py review --reviews "좋아요" "배송 느림" "품질 좋음"
python fortimove.py scout
python fortimove.py country JP
python fortimove.py --help     # 전체 명령어 목록
```

## 7. 전체 운영 도구 모음 (pm-agent/)

| 명령어 | 용도 | 빈도 |
|--------|------|------|
| `fortimove.py premium` | 1개 상품 초퀄리티 분석 (상세페이지+광고) | ★★★ 매일 |
| `fortimove.py keyword` | 네이버 쇼핑 키워드 리서치 | ★★★ 매일 |
| `fortimove.py daily` | 일일 워크플로우 (Scout→추천→Slack) | ★★★ 매일 |
| `fortimove.py scout` | Scout 상품 A/B등급 추천 | ★★☆ 매일 |
| `fortimove.py sales` | 판매 성과 추적 + 교체 추천 | ★★☆ 매일 |
| `fortimove.py lifecycle` | 테스트→반복→PB 전환 관리 | ★★☆ 주간 |
| `fortimove.py review` | 고객 리뷰 분석 → 개선점 추출 | ★★☆ 주간 |
| `fortimove.py image` | 이미지 현지화 | ★★☆ 등록 시 |
| `fortimove.py country` | 국가별 소싱 가이드 (CN/US/JP/VN) | ★☆☆ 참고 |
| `fortimove.py quick` | 빠른 소싱+마진 검증 | ★☆☆ 필요 시 |

### 키워드 리서치

```bash
# 상품 등록 전 키워드 조사
python keyword_research.py "콜라겐" --category wellness
python keyword_research.py "비타민C" --budget 20000
```

### 성과 추적

```bash
# 판매 데이터 기록 (매일)
python sales_tracker.py add --name "콜라겐 분말" --orders 8 --revenue 239200 --ad-spend 15000

# 전체 상품 성과 확인
python sales_tracker.py list

# 주간 리포트
python sales_tracker.py report

# D등급 상품 교체 추천
python sales_tracker.py replace
```

### 이미지 현지화

```bash
# 타오바오 상품 이미지를 한국어로 변환
python image_processor.py product1.jpg product2.png --moodtone premium --product "콜라겐 분말"
```

## 7. 문제 해결

```bash
# 서비스 상태 확인
curl http://localhost:8001/health/ready

# 로그 확인
docker-compose logs -f pm_agent
docker-compose logs -f daily_scout

# 전체 재시작
docker-compose restart
```
