# 🚀 여기서 시작하세요!

## ✅ 당신이 지금 해야 할 것 (순서대로)

### 1. Anthropic API 키 발급 (5분)
```
🔗 https://console.anthropic.com
1. 회원가입/로그인
2. API Keys 메뉴
3. "Create Key" 클릭
4. 키 복사 (sk-ant-api03-... 형식)
```

### 2. 환경 설정 (1분)
```bash
cd /home/fortymove/Fortimove-OS/image-localization-system

# .env 파일 생성
cp .env.example .env

# API 키 입력 (nano 또는 선호하는 에디터 사용)
nano .env
# ANTHROPIC_API_KEY= 부분에 복사한 키 붙여넣기
```

### 3. Docker 실행 (2분)
```bash
# 시스템 시작
docker-compose up -d

# 로그 확인 (Ctrl+C로 종료)
docker-compose logs -f backend
```

### 4. 테스트 (1분)
```bash
# 헬스체크
curl http://localhost:8000/health

# 또는 자동 테스트 스크립트
./test_api.sh
```

---

## 📸 실제 이미지 테스트

### 방법 1: Shell 스크립트
```bash
# 타오바오 이미지를 test_image.jpg로 저장 후
./test_api.sh
```

### 방법 2: Python 클라이언트
```bash
# Python 3 필요
pip install requests

# 실행
python3 test_client.py test_image.jpg
```

### 방법 3: curl 직접 호출
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -F "files=@your_image.jpg" \
  -F "moodtone=premium" \
  -F "generate_seo=true"
```

---

## 🎯 예상 결과

성공하면 이런 응답이 나옵니다:
```json
{
  "job_id": "abc-123-...",
  "status": "completed",
  "seo_metadata": {
    "product_names": [
      "프리미엄 초강력 흡수 속건 마이크로화이버 타월",
      "..."
    ],
    "search_tags": ["속건타월", "마이크로화이버", ...],
    "keywords": ["속건타월", ...]
  },
  "processing_time_seconds": 3.5
}
```

---

## 🆘 문제 해결

### "Connection refused" 에러
```bash
docker-compose ps  # 컨테이너 상태 확인
docker-compose restart backend  # 재시작
```

### "API key not found" 에러
```bash
cat .env | grep ANTHROPIC  # 키 확인
nano .env  # 키 재입력
docker-compose restart backend  # 재시작
```

### OCR 안 되는 경우
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 📚 추가 문서

- 상세 가이드: `QUICKSTART.md`
- 전체 문서: `README.md`
- API 문서: http://localhost:8000/docs (서버 실행 후)

---

## ✨ 다음 단계

시스템이 정상 작동하면:
1. 타오바오 상품 이미지로 실전 테스트
2. 대량 처리 (여러 이미지 동시 업로드)
3. 프로덕션 배포 (AWS)

**문의**: README.md 하단 참고
