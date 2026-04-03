# Fortimove 이미지 현지화 시스템

타오바오/티몰 상세페이지 이미지를 한국 이커머스에 최적화된 형태로 자동 변환하는 프로덕션 레벨 시스템입니다.

## 주요 기능

### 🎯 핵심 기능
- **OCR 텍스트 추출**: EasyOCR로 중국어 텍스트 자동 추출
- **AI 번역**: Claude 3.5 Sonnet 기반 이커머스 최적화 번역
- **리스크 탐지**: 유아 이미지, 인물 얼굴, 브랜드 로고 자동 감지
- **리스크 자동 처리**: 유아 이미지 삭제, 얼굴 블러 처리
- **무드톤 조정**: 프리미엄/가성비/미니멀/트렌디 4가지 프리셋
- **SEO 메타데이터 생성**: 상품명 3안, 태그 10개, 키워드 5개 자동 생성

### 📊 기술 스택

**백엔드**:
- FastAPI (Python 3.11)
- PostgreSQL 15
- Redis 7
- Celery (작업 큐)

**AI/ML**:
- EasyOCR (텍스트 추출)
- Claude 3.5 Sonnet (번역, SEO)
- CLIP (유아 탐지)
- OpenCV (얼굴 탐지)
- Pillow, rembg (이미지 처리)

**인프라**:
- Docker & Docker Compose
- AWS S3 (이미지 스토리지)
- Sentry (모니터링)

## 빠른 시작

### 1. 사전 요구사항
```bash
- Docker & Docker Compose
- Anthropic API Key
```

### 2. 설치
```bash
# 저장소 클론
cd /home/fortymove/Fortimove-OS/image-localization-system

# 환경 변수 설정
cp .env.example .env
nano .env  # API 키 입력

# Docker 빌드 및 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f backend
```

### 3. API 테스트
```bash
# 헬스체크
curl http://localhost:8000/health

# 이미지 처리 (예시)
curl -X POST http://localhost:8000/api/v1/process \
  -F "files=@sample_image.jpg" \
  -F "moodtone=premium" \
  -F "brand_type=fortimove_global" \
  -F "generate_seo=true"
```

### 4. 웹 UI 접속
```
http://localhost:3000
```

## API 문서

### POST /api/v1/process

이미지 현지화 처리

**요청**:
- `files`: 이미지 파일 (multipart/form-data, 최대 20개)
- `moodtone`: 무드톤 (premium/value/minimal/trendy)
- `brand_type`: 브랜드 타입 (fortimove_global/fortimove)
- `product_name`: 원본 상품명 (선택)
- `generate_seo`: SEO 메타데이터 생성 여부 (기본: true)
- `auto_replace_risks`: 리스크 자동 대체 여부 (기본: true)

**응답**:
```json
{
  "job_id": "uuid",
  "status": "completed",
  "processed_images": [
    {
      "original_filename": "image.jpg",
      "processed_filename": "uuid_image.jpg",
      "download_url": "https://s3.../image.jpg",
      "width": 1200,
      "height": 800
    }
  ],
  "analysis_report": {
    "ocr_results": [...],
    "translations": [...],
    "risks_detected": [...],
    "risks_processed": [...]
  },
  "seo_metadata": {
    "product_names": ["상품명1", "상품명2", "상품명3"],
    "search_tags": ["태그1", "태그2", ...],
    "keywords": ["키워드1", "키워드2", ...]
  },
  "processing_time_seconds": 12.5
}
```

## 프로덕션 배포

### 1. 환경 변수 설정
```bash
# .env 파일 수정
DEBUG=false
ALLOWED_ORIGINS=["https://yourdomain.com"]
STORAGE_PROVIDER=s3
AWS_S3_BUCKET=your-production-bucket
SENTRY_DSN=your-sentry-dsn
```

### 2. SSL 인증서 설정
```bash
# nginx + Let's Encrypt 사용 권장
docker-compose -f docker-compose.prod.yml up -d
```

### 3. 모니터링
- Sentry: 에러 추적
- Prometheus: 메트릭 수집
- Grafana: 대시보드

## 성능

**처리 속도**:
- 이미지당 평균 3~5초
- 동시 처리: 최대 5개 작업

**리소스 요구사항**:
- CPU: 4 vCPU 이상 권장
- RAM: 8GB 이상 권장
- GPU: 선택 (OCR 속도 2배 향상)

## 비용 예상

**AI API 비용** (상품당):
- Claude API (번역 + SEO): ~$0.02
- 총 비용: **상품당 약 $0.02 (25원)**

**인프라 비용** (월간):
- AWS EC2 (t3.large): ~$60
- AWS S3: ~$5
- Redis/PostgreSQL: 포함
- **총 인프라: 월 ~$65**

## 문제 해결

### OCR 정확도 낮음
```bash
# Tesseract 대신 Google Cloud Vision 사용
OCR_ENGINE=google_vision
GOOGLE_CLOUD_VISION_API_KEY=your_key
```

### 처리 속도 느림
```bash
# GPU 활성화 (Docker)
docker-compose -f docker-compose.gpu.yml up -d

# Celery Worker 증가
docker-compose scale celery_worker=4
```

## 라이선스

MIT License

## 문의

- 이메일: dev@fortimove.com
- Slack: #image-localization
