#!/bin/bash
# PM 에이전트 간단 테스트

echo "🧪 PM 에이전트 간단 테스트"
echo "================================"
echo ""

# API 키 확인
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다."
    echo ""
    echo "설정 방법:"
    echo "  export ANTHROPIC_API_KEY='your-key'"
    exit 1
fi

echo "✅ ANTHROPIC_API_KEY 확인됨"
echo ""

# 테스트 케이스 1: 소싱
echo "## 테스트 1: 신규 소싱"
echo ""
python3 /home/fortymove/Fortimove-OS/pm-agent/pm_agent.py "타오바오 무선 이어폰 링크 분석해줘. 원가는 10달러야."
echo ""
echo "================================"
echo ""

# 테스트 케이스 2: CS
echo "## 테스트 2: 고객 클레임"
echo ""
python3 /home/fortymove/Fortimove-OS/pm-agent/pm_agent.py "고객이 배송 지연 클레임 넣었어"
echo ""
echo "================================"
echo ""

echo "✅ 테스트 완료"
