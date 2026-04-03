#!/bin/bash
# API 테스트 스크립트

echo "🔍 Fortimove 이미지 현지화 API 테스트"
echo "========================================"

# 1. 헬스체크
echo ""
echo "1️⃣ 헬스체크 테스트..."
curl -s http://localhost:8000/health | python3 -m json.tool

# 2. API 문서 확인
echo ""
echo "2️⃣ API 문서 URL:"
echo "   http://localhost:8000/docs"

# 3. 테스트 이미지 확인
echo ""
echo "3️⃣ 테스트 이미지 확인..."
if [ -f "test_image.jpg" ]; then
    echo "   ✅ test_image.jpg 파일 존재"

    echo ""
    echo "4️⃣ 이미지 처리 테스트 실행 중..."
    curl -X POST http://localhost:8000/api/v1/process \
      -F "files=@test_image.jpg" \
      -F "moodtone=premium" \
      -F "brand_type=fortimove_global" \
      -F "generate_seo=true" \
      | python3 -m json.tool
else
    echo "   ⚠️  test_image.jpg 파일이 없습니다."
    echo "   타오바오 상품 이미지를 다운로드하여 test_image.jpg로 저장하세요."
fi

echo ""
echo "========================================"
echo "✅ 테스트 완료"
