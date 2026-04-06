#!/bin/bash
# Daily Scout Integration 단일 실행 스크립트
# 1개 배치만 처리하고 종료

set -e

echo "======================================================================"
echo "  Daily Scout Integration - Single Batch Execution"
echo "======================================================================"
echo ""

# 환경 변수 설정
export RUN_MODE=once
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=fortimove_images
export DB_USER=fortimove
export DB_PASSWORD=fortimove123
export PM_AGENT_API_URL=https://staging-pm-agent.fortimove.com
export BATCH_SIZE=1  # 테스트: 1개만
export POLLING_INTERVAL=300

echo "📋 설정:"
echo "  DB: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "  API: ${PM_AGENT_API_URL}"
echo "  Batch Size: ${BATCH_SIZE}"
echo ""

# Python 스크립트 실행
cd /home/fortymove/Fortimove-OS/pm-agent

# Docker Python 환경에서 실행 (로컬 Python이 없는 경우)
if command -v python3 &> /dev/null; then
    echo "✅ Local Python3 found - using local environment"
    python3 daily_scout_integration_api.py
else
    echo "⚠️  Local Python3 not found - using Docker Python"
    docker run --rm \
        --network host \
        -v $(pwd):/app \
        -w /app \
        -e RUN_MODE=once \
        -e DB_HOST=localhost \
        -e DB_PORT=5432 \
        -e DB_NAME=fortimove_images \
        -e DB_USER=fortimove \
        -e DB_PASSWORD=fortimove123 \
        -e PM_AGENT_API_URL=https://staging-pm-agent.fortimove.com \
        -e BATCH_SIZE=1 \
        python:3.10-slim bash -c "
            pip install -q psycopg2-binary requests && \
            python3 daily_scout_integration_api.py
        "
fi

echo ""
echo "======================================================================"
echo "  Execution Complete"
echo "======================================================================"
