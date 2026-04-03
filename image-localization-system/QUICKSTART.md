# ⚡ 빠른 시작 가이드 (5분 완성)

## 전제 조건
- Docker 및 Docker Compose 설치됨
- Anthropic API 키 보유

---

## 🎯 Step 1: API 키 발급 (처음 1회만)

```bash
# 1. Anthropic 콘솔 접속
https://console.anthropic.com

# 2. API Keys 메뉴에서 키 생성
# 3. 키 복사 (sk-ant-api03-... 형식)
```

---

## 🎯 Step 2: 프로젝트 디렉토리 이동

```bash
cd /home/fortymove/Fortimove-OS/image-localization-system
```

---

## 🎯 Step 3: 환경 변수 설정

```bash
# .env 파일 생성 (한 번에 복붙)
cat > .env << 'EOF'
DATABASE_URL=postgresql://fortimove:fortimove123@db:5432/fortimove_images
DB_PASSWORD=fortimove123
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
ANTHROPIC_API_KEY=sk-ant-여기에-실제-키-입력
SECRET_KEY=fortimove-dev-secret-key-2026
DEBUG=true
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]
STORAGE_PROVIDER=local
LOCAL_STORAGE_PATH=/tmp/fortimove-images
MAX_IMAGE_SIZE_MB=20
OUTPUT_IMAGE_WIDTH=1200
OUTPUT_IMAGE_QUALITY=85
OCR_ENGINE=easyocr
TRANSLATION_MODEL=claude-3-5-sonnet-20241022
INFANT_DETECTION_THRESHOLD=0.7
EOF

# ⚠️ 중요: ANTHROPIC_API_KEY 부분에 실제 키 입력하세요!
nano .env  # 또는 vi .env
```

---

## 🎯 Step 4: Docker 컨테이너 실행

```bash
# Docker Compose로 전체 시스템 시작
docker-compose up -d

# 실행 확인 (모든 컨테이너가 healthy 상태여야 함)
docker-compose ps

# 예상 출력:
# NAME                  STATUS
# backend               Up (healthy)
# db                    Up (healthy)
# redis                 Up (healthy)
```

---

## 🎯 Step 5: 백엔드 로그 확인

```bash
# 실시간 로그 확인
docker-compose logs -f backend

# 예상 출력:
# INFO: 서비스 초기화 중...
# INFO: 서비스 초기화 완료
# INFO: Application startup complete.
# INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## 🎯 Step 6: API 헬스체크

```bash
# 터미널에서 테스트
curl http://localhost:8000/health

# 예상 응답:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "services": {
#     "ocr": "ready",
#     "translation": "ready",
#     ...
#   }
# }
```

---

## 🎯 Step 7: 실제 이미지 처리 테스트

### 방법 A: curl 명령어
```bash
# 테스트용 이미지 준비 (타오바오 상품 이미지)
# 예: test_image.jpg

# API 호출
curl -X POST http://localhost:8000/api/v1/process \
  -F "files=@test_image.jpg" \
  -F "moodtone=premium" \
  -F "brand_type=fortimove_global" \
  -F "product_name=超强吸水速干毛巾" \
  -F "generate_seo=true" \
  -F "auto_replace_risks=true"
```

### 방법 B: Python 스크립트
```python
import requests

# API 엔드포인트
url = "http://localhost:8000/api/v1/process"

# 이미지 파일
files = {'files': open('test_image.jpg', 'rb')}

# 요청 데이터
data = {
    'moodtone': 'premium',
    'brand_type': 'fortimove_global',
    'product_name': '超强吸水速干毛巾',
    'generate_seo': True,
    'auto_replace_risks': True
}

# API 호출
response = requests.post(url, files=files, data=data)
result = response.json()

# 결과 확인
print(f"작업 ID: {result['job_id']}")
print(f"상태: {result['status']}")
print(f"처리 시간: {result['processing_time_seconds']}초")
print(f"상품명: {result['seo_metadata']['product_names']}")
```

---

## 🎯 Step 8: 결과 확인

응답 예시:
```json
{
  "job_id": "abc123-...",
  "status": "completed",
  "processed_images": [
    {
      "original_filename": "test_image.jpg",
      "processed_filename": "abc123_test_image.jpg",
      "download_url": "http://localhost:8000/downloads/abc123_test_image.jpg",
      "width": 1200,
      "height": 800
    }
  ],
  "analysis_report": {
    "ocr_results": [...],
    "translations": [
      {
        "original": "超强吸水",
        "translated": "초강력 흡수력"
      }
    ],
    "risks_detected": [
      {
        "risk_type": "infant",
        "confidence": 0.85,
        "description": "유아 이미지 감지됨"
      }
    ],
    "risks_processed": [
      {
        "risk_type": "infant",
        "action": "deleted",
        "details": "유아 이미지 전체 삭제"
      }
    ]
  },
  "seo_metadata": {
    "product_names": [
      "프리미엄 초강력 흡수 속건 마이크로화이버 타월",
      "호텔급 극세사 타올 빠른건조 스포츠용",
      "고급 속건 타월 흡수력 3배 헬스 헤어타올"
    ],
    "search_tags": [
      "속건타월", "마이크로화이버", "프리미엄타월",
      "헬스타올", "스포츠수건", ...
    ],
    "keywords": [
      "속건타월", "마이크로화이버타월", "흡수력타월", ...
    ]
  },
  "processing_time_seconds": 4.2
}
```

---

## 🛑 문제 해결

### 문제 1: "Connection refused"
```bash
# 컨테이너 상태 확인
docker-compose ps

# 문제 있는 컨테이너 재시작
docker-compose restart backend
```

### 문제 2: "ANTHROPIC_API_KEY not found"
```bash
# .env 파일 확인
cat .env | grep ANTHROPIC

# API 키 재설정
nano .env
```

### 문제 3: OCR 오류
```bash
# Tesseract 설치 확인
docker-compose exec backend tesseract --version

# 컨테이너 재빌드
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 📊 시스템 중지/재시작

```bash
# 중지
docker-compose down

# 재시작
docker-compose up -d

# 전체 삭제 (데이터 포함)
docker-compose down -v
```

---

## 🎉 성공!

시스템이 정상 작동하면:
- ✅ API가 `http://localhost:8000`에서 실행 중
- ✅ 이미지 업로드 → OCR → 번역 → 리스크 제거 → SEO 생성 자동화
- ✅ 상품당 3~5초 처리

**다음 단계**: README.md의 "프로덕션 배포" 섹션 참고
