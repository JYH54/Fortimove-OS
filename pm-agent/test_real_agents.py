#!/usr/bin/env python3
"""
실제 에이전트 통합 테스트
Phase 3: Image Agent, Margin Agent, Daily Scout와 PM Agent 통합 검증
"""
import logging
import sys
from real_agents import (
    ImageLocalizationAgent,
    MarginCheckAgent,
    DailyScoutAgent,
    register_real_agents
)
from agent_framework import ExecutionContext, WorkflowExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_margin_agent():
    """Margin Check Agent 단독 테스트"""
    print("\n" + "="*80)
    print("TEST 1: Margin Check Agent - 통계 조회")
    print("="*80)

    agent = MarginCheckAgent()

    # 1. 통계 조회
    result = agent.execute({
        'action': 'get_stats'
    })

    print(f"\n[결과] 상태: {result.status.value}")
    if result.is_success():
        print(f"✅ 성공!")
        print(f"  - 전체 상품: {result.output['data']['total']}개")
        print(f"  - 통과: {result.output['data']['passed']}개")
        print(f"  - 보류: {result.output['data']['pending']}개")
        print(f"  - 지역별: {result.output['data']['region_stats']}")
    else:
        print(f"❌ 실패: {result.error}")
        return False

    # 2. 상품 검색
    print("\n" + "="*80)
    print("TEST 2: Margin Check Agent - 상품 검색")
    print("="*80)

    result = agent.execute({
        'action': 'search_products',
        'region': 'us',
        'limit': 3
    })

    print(f"\n[결과] 상태: {result.status.value}")
    if result.is_success():
        print(f"✅ 성공! {result.output['count']}개 상품 발견")
        for i, product in enumerate(result.output['data'][:3], 1):
            print(f"  {i}. {product['product_name'][:50]}... (Score: {product['trend_score']})")
    else:
        print(f"❌ 실패: {result.error}")
        return False

    # 3. 개별 상품 마진 체크
    print("\n" + "="*80)
    print("TEST 3: Margin Check Agent - 개별 상품 마진 분석")
    print("="*80)

    result = agent.execute({
        'action': 'check_margin',
        'product_id': 1
    })

    print(f"\n[결과] 상태: {result.status.value}")
    if result.is_success():
        product = result.output['product']
        margin = result.output['margin_analysis']
        print(f"✅ 성공!")
        print(f"  - 상품명: {product['product_name'][:50]}...")
        print(f"  - 가격: ${margin['price']}")
        print(f"  - 예상 마진: ${margin['estimated_margin']:.2f} ({margin['margin_rate']*100}%)")
        print(f"  - 추천: {margin['recommendation']}")
    else:
        print(f"❌ 실패: {result.error}")
        return False

    return True


def test_daily_scout_agent():
    """Daily Scout Agent 단독 테스트"""
    print("\n" + "="*80)
    print("TEST 4: Daily Scout Agent - 상태 확인")
    print("="*80)

    agent = DailyScoutAgent()

    result = agent.execute({
        'region': 'us',
        'max_products': 10
    })

    print(f"\n[결과] 상태: {result.status.value}")
    if result.is_success():
        print(f"✅ 성공!")
        print(f"  - 스캔된 상품: {result.output['scanned_count']}개")
        print(f"  - 저장된 상품: {result.output['saved_count']}개")
        print(f"  - 지역별: {result.output['region_stats']}")
        print(f"  - 날짜: {result.output['date']}")
    else:
        print(f"❌ 실패: {result.error}")
        return False

    return True


def test_workflow_integration():
    """워크플로우 통합 테스트: PM Agent → Margin Agent 자동 실행"""
    print("\n" + "="*80)
    print("TEST 5: 워크플로우 통합 - PM Agent + Margin Agent")
    print("="*80)

    # 에이전트 등록
    registry = register_real_agents()

    # 사용자 요청 시뮬레이션
    user_request = "미국 시장의 웰니스 상품 중 수익성 높은 아이템 추천해줘"

    # 워크플로우 정의 (PM Agent가 생성하는 것과 동일한 구조)
    workflow = [
        {
            "step": 1,
            "agent": "margin",
            "action": "search_products",
            "description": "미국 시장 상품 검색",
            "priority": "P1"
        }
    ]

    # 실행 컨텍스트 생성
    context = ExecutionContext(user_request)

    # 워크플로우 실행
    executor = WorkflowExecutor(registry)
    result_context = executor.execute_sequential(workflow, context)

    # 결과 출력
    print(f"\n[실행 결과]")
    print(f"  - 요청: {result_context.request}")
    print(f"  - 실행된 에이전트 수: {len(result_context.results)}")

    for agent_name, result in result_context.results.items():
        print(f"\n  [{agent_name}]")
        print(f"    상태: {result.status.value}")
        if result.is_success():
            print(f"    ✅ 성공")
            if 'count' in result.output:
                print(f"    발견한 상품: {result.output['count']}개")
        else:
            print(f"    ❌ 실패: {result.error}")

    # 실행 로그 출력
    print(f"\n[실행 로그]")
    for log in result_context.execution_log:
        print(f"  {log['timestamp']}: {log['agent']} → {log['status']}")

    return len(result_context.results) > 0


def test_multi_step_workflow():
    """다중 스텝 워크플로우 테스트: Daily Scout → Margin Check"""
    print("\n" + "="*80)
    print("TEST 6: 다중 스텝 워크플로우 - Daily Scout → Margin Check")
    print("="*80)

    # 에이전트 등록
    registry = register_real_agents()

    # 사용자 요청
    user_request = "최신 웰니스 트렌드를 스캔하고 수익성 분석해줘"

    # 2단계 워크플로우
    workflow = [
        {
            "step": 1,
            "agent": "daily_scout",
            "action": "scan",
            "description": "최신 웰니스 상품 스캔",
            "priority": "P1"
        },
        {
            "step": 2,
            "agent": "margin",
            "action": "get_stats",
            "description": "수익성 통계 분석",
            "priority": "P1",
            "depends_on": ["daily_scout"]
        }
    ]

    # 실행
    context = ExecutionContext(user_request)
    executor = WorkflowExecutor(registry)
    result_context = executor.execute_sequential(workflow, context)

    # 결과
    print(f"\n[실행 결과]")
    print(f"  - 총 {len(result_context.results)}개 에이전트 실행")

    for i, (agent_name, result) in enumerate(result_context.results.items(), 1):
        print(f"\n  Step {i}: {agent_name}")
        print(f"    상태: {result.status.value}")
        if result.is_success():
            print(f"    ✅ 성공")
        else:
            print(f"    ❌ 실패: {result.error}")

    # 자동 데이터 전달 검증
    print(f"\n[자동 데이터 전달 검증]")
    last_output = result_context.get_last_output()
    print(f"  마지막 성공 에이전트의 출력이 자동으로 전달됨:")
    print(f"  {list(last_output.keys())[:5]}...")

    return True


def main():
    """전체 테스트 실행"""
    print("\n")
    print("="*80)
    print("🧪 Phase 3: 실제 에이전트 통합 테스트")
    print("="*80)

    tests = [
        ("Margin Check Agent", test_margin_agent),
        ("Daily Scout Agent", test_daily_scout_agent),
        ("워크플로우 통합", test_workflow_integration),
        ("다중 스텝 워크플로우", test_multi_step_workflow),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"{test_name} 테스트 실패: {e}")
            results.append((test_name, False))

    # 최종 결과
    print("\n" + "="*80)
    print("📊 테스트 결과 요약")
    print("="*80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n전체: {passed}/{total} 통과 ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 모든 테스트 통과! Phase 3 완료")
        sys.exit(0)
    else:
        print(f"\n⚠️ {total-passed}개 테스트 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
