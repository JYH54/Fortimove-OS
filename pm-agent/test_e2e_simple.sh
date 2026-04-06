#!/bin/bash
# End-to-End 통합 테스트 (간단 버전)
# PM Agent + Real Agents 통합 검증

echo "================================================================================"
echo "🧪 Phase 3: End-to-End 통합 테스트 (Simple)"
echo "================================================================================"

# 1. 실제 에이전트 API 상태 확인
echo ""
echo "TEST 1: 실제 에이전트 API 상태 확인"
echo "--------------------------------------------------------------------------------"

echo "📍 Image Agent (localhost:8000) 헬스체크..."
IMAGE_HEALTH=$(curl -s http://localhost:8000/health)
if [ $? -eq 0 ]; then
    echo "✅ Image Agent: OK"
    echo "   $IMAGE_HEALTH" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"   Version: {d.get('version', 'unknown')}\")"
else
    echo "❌ Image Agent: 연결 실패"
fi

echo ""
echo "📍 Scout Dashboard (localhost:8050) 헬스체크..."
SCOUT_HEALTH=$(curl -s http://localhost:8050/health)
if [ $? -eq 0 ]; then
    echo "✅ Scout Dashboard: OK"
    echo "   $SCOUT_HEALTH" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"   Service: {d.get('service', 'unknown')}\")"
else
    echo "❌ Scout Dashboard: 연결 실패"
fi

# 2. 실제 에이전트 래퍼 테스트
echo ""
echo ""
echo "TEST 2: 실제 에이전트 래퍼 테스트"
echo "--------------------------------------------------------------------------------"

cd /home/fortymove/Fortimove-OS/pm-agent

python3 test_real_agents.py

TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo "================================================================================"
    echo "✅ Phase 3 통합 테스트 완료!"
    echo "================================================================================"
    echo ""
    echo "📊 검증 완료 항목:"
    echo "  1. ✅ Image Localization Agent (localhost:8000) - BaseAgent 래퍼"
    echo "  2. ✅ Margin Check Agent (localhost:8050) - BaseAgent 래퍼"
    echo "  3. ✅ Daily Scout Agent - BaseAgent 래퍼"
    echo "  4. ✅ AgentRegistry 등록 및 자동 실행"
    echo "  5. ✅ 워크플로우 자동 실행 (순차)"
    echo "  6. ✅ 에이전트 간 자동 데이터 전달"
    echo "  7. ✅ 상태 추적 및 실행 로그"
    echo ""
    echo "🚀 다음 단계:"
    echo "  - PM Agent CLI에서 실제 에이전트 사용"
    echo "  - Docker Compose로 전체 시스템 실행"
    echo "  - 나머지 4개 에이전트 구현 (sourcing, product_registration, content, cs)"
    echo ""
    exit 0
else
    echo ""
    echo "================================================================================"
    echo "❌ Phase 3 통합 테스트 실패"
    echo "================================================================================"
    exit 1
fi
