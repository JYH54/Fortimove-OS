#!/bin/bash
# Sentinel 매일 자동 실행 스크립트
# crontab 등록: crontab -e → 아래 줄 추가
# 0 9 * * * /home/fortymove/Fortimove-OS/sentinel/run_daily.sh >> /home/fortymove/Fortimove-OS/sentinel/data/cron.log 2>&1

cd /home/fortymove/Fortimove-OS/sentinel
export SLACK_BOT_TOKEN="xoxb-REDACTED"
export GOOGLE_API_KEY="AIzaSyD6chNQ-Nb8CcX1fqaegdv2Z-sKEnRhWfE"

echo "=========================================="
echo "Sentinel 실행: $(date)"
echo "=========================================="

python3 main.py
