#!/bin/bash
# Daily Scout Integration 연속 실행 스크립트
# 5분마다 폴링하며 상품 자동 처리

set -e

echo "======================================================================"
echo "  Daily Scout Integration - Continuous Mode"
echo "======================================================================"
echo ""

# 환경 변수 설정
export RUN_MODE=continuous
export DB_HOST=${DB_HOST:-localhost}
export DB_PORT=${DB_PORT:-5432}
export DB_NAME=${DB_NAME:-fortimove_images}
export DB_USER=${DB_USER:-fortimove}
export DB_PASSWORD=${DB_PASSWORD:-fortimove123}
export PM_AGENT_API_URL=${PM_AGENT_API_URL:-https://staging-pm-agent.fortimove.com}
export BATCH_SIZE=${BATCH_SIZE:-5}
export POLLING_INTERVAL=${POLLING_INTERVAL:-300}

echo "📋 설정:"
echo "  DB: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "  API: ${PM_AGENT_API_URL}"
echo "  Batch Size: ${BATCH_SIZE}"
echo "  Polling Interval: ${POLLING_INTERVAL}초 ($(($POLLING_INTERVAL / 60))분)"
echo ""
echo "⚠️  연속 모드로 실행됩니다. Ctrl+C로 종료하세요."
echo ""
sleep 3

cd /home/fortymove/Fortimove-OS/pm-agent

# Docker Python 환경에서 실행
docker run --rm \
    --name daily-scout-integration \
    --network host \
    -v $(pwd):/app \
    -w /app \
    -e RUN_MODE=${RUN_MODE} \
    -e DB_HOST=${DB_HOST} \
    -e DB_PORT=${DB_PORT} \
    -e DB_NAME=${DB_NAME} \
    -e DB_USER=${DB_USER} \
    -e DB_PASSWORD=${DB_PASSWORD} \
    -e PM_AGENT_API_URL=${PM_AGENT_API_URL} \
    -e BATCH_SIZE=${BATCH_SIZE} \
    -e POLLING_INTERVAL=${POLLING_INTERVAL} \
    python:3.10-slim bash -c "
        echo '📦 Installing dependencies...' && \
        pip install -q psycopg2-binary requests && \
        echo '✅ Dependencies installed' && \
        echo '' && \
        python3 daily_scout_integration_api.py
    "
