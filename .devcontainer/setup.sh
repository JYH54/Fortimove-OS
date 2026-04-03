#!/bin/bash
set -e

echo "=== Fortimove-OS Dev Container Setup ==="

# .env 파일 생성 (없는 경우)
if [ ! -f /workspace/.env ]; then
    cp /workspace/.env.template /workspace/.env
    echo "[setup] .env 파일 생성 완료 — API 키를 입력하세요: nano .env"
fi

# pm-agent .env
if [ ! -f /workspace/pm-agent/.env ]; then
    cp /workspace/.env.template /workspace/pm-agent/.env
fi

# image-localization-system .env
if [ ! -f /workspace/image-localization-system/.env ]; then
    cp /workspace/.env.template /workspace/image-localization-system/.env
fi

# Git 설정 (컨테이너 내부)
git config --global --add safe.directory /workspace

# DB 마이그레이션 대기
echo "[setup] PostgreSQL 연결 대기 중..."
for i in $(seq 1 30); do
    if pg_isready -h db -p 5432 -U fortimove > /dev/null 2>&1; then
        echo "[setup] PostgreSQL 연결 완료"
        break
    fi
    sleep 1
done

echo ""
echo "=== 설정 완료 ==="
echo ""
echo "  사용법:"
echo "    cd pm-agent && python fortimove.py --help"
echo ""
echo "  API 키 설정:"
echo "    nano .env  (ANTHROPIC_API_KEY 입력)"
echo ""
