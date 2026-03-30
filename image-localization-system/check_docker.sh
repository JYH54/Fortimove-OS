#!/bin/bash
echo "🔍 Docker 설정 확인 중..."
echo ""

# Docker 실행 파일 확인
if command -v docker &> /dev/null; then
    echo "✅ Docker 실행 파일 있음: $(which docker)"
    docker --version
else
    echo "❌ Docker 실행 파일 없음"
    exit 1
fi

echo ""

# Docker Compose 확인
if command -v docker-compose &> /dev/null; then
    echo "✅ Docker Compose 있음"
    docker-compose --version
else
    echo "❌ Docker Compose 없음 (WSL 연동 필요)"
    exit 1
fi

echo ""

# Docker 데몬 연결 확인
if docker ps &> /dev/null; then
    echo "✅ Docker 데몬 연결 성공"
    docker ps
else
    echo "❌ Docker 데몬 연결 실패"
    echo ""
    echo "해결 방법:"
    echo "1. Windows에서 Docker Desktop 실행"
    echo "2. Settings → Resources → WSL Integration"
    echo "3. Ubuntu 토글 ON"
    echo "4. Apply & Restart"
    exit 1
fi

echo ""
echo "✅ Docker 설정 완료! 시스템 시작 가능합니다."
echo ""
echo "다음 명령어 실행:"
echo "  cd /home/fortymove/Fortimove-OS/image-localization-system"
echo "  docker-compose up -d"
