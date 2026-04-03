#!/usr/bin/env python3
"""
End-to-End 통합 테스트
PM Agent → Real Agents → 자동 실행 → 결과 확인
"""
import os
import sys
import logging
from pm_agent import PMAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_margin_check_workflow():
    """
    시나리오 1: 수익성 분석 요청
    사용자 → PM Agent → Margin Agent (자동 실행)
    """
    print("\n" + "="*80)
    print("🧪 E2E Test 1: 수익성 분석 워크플로우")
    print("="*80)

    # API 키 확인
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return False

    # PM Agent 초기화
    pm = PMAgent()

    # 사용자 요청
    user_request = "미국 시장의 웰니스 상품 중 수익성 높은 아이템을 분석해줘"

    print(f"\n📝 사용자 요청: {user_request}")
    print(f"🚀 PM Agent 자동 실행 시작...\n")

    # 자동 실행
    try:
        result = pm.execute_workflow(user_request, auto_execute=True)

        print(f"\n📊 실행 결과:")
        print(f"  - 상태: {result['status']}")

        if result['status'] == 'completed':
            exec_context = result['execution_context']
            print(f"  - 실행된 에이전트: {len(exec_context['results'])}개")

            for agent_name, agent_result in exec_context['results'].items():
                print(f"\n  [{agent_name}]")
                print(f"    상태: {agent_result['status']}")

                if agent_result['status'] == 'completed':
                    output = agent_result['output']
                    if 'data' in output:
                        data = output['data']
                        print(f"    ✅ 전체 상품: {data.get('total')}개")
                        print(f"    ✅ 통과: {data.get('passed')}개")
                        print(f"    ✅ 보류: {data.get('pending')}개")

            print(f"\n✅ E2E Test 1 통과!")
            return True
        else:
            print(f"  ❌ 실패: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        logger.error(f"E2E 테스트 실패: {e}")
        return False


def test_product_search_workflow():
    """
    시나리오 2: 상품 검색 요청
    사용자 → PM Agent → Margin Agent (검색) → 자동 실행
    """
    print("\n" + "="*80)
    print("🧪 E2E Test 2: 상품 검색 워크플로우")
    print("="*80)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return False

    pm = PMAgent()
    user_request = "일본 시장의 프로바이오틱스 제품을 검색해줘"

    print(f"\n📝 사용자 요청: {user_request}")
    print(f"🚀 PM Agent 자동 실행 시작...\n")

    try:
        result = pm.execute_workflow(user_request, auto_execute=True)

        print(f"\n📊 실행 결과:")
        print(f"  - 상태: {result['status']}")

        if result['status'] == 'completed':
            exec_context = result['execution_context']

            for agent_name, agent_result in exec_context['results'].items():
                print(f"\n  [{agent_name}]")
                print(f"    상태: {agent_result['status']}")

                if agent_result['status'] == 'completed':
                    output = agent_result['output']
                    if 'count' in output:
                        print(f"    ✅ 검색 결과: {output['count']}개 상품 발견")

            print(f"\n✅ E2E Test 2 통과!")
            return True
        else:
            print(f"  ❌ 실패: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        logger.error(f"E2E 테스트 실패: {e}")
        return False


def test_planning_only_mode():
    """
    시나리오 3: 계획만 수립 (자동 실행 OFF)
    사용자 → PM Agent → 실행 계획 반환 (실행 안함)
    """
    print("\n" + "="*80)
    print("🧪 E2E Test 3: 계획 수립 모드 (자동 실행 OFF)")
    print("="*80)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return False

    pm = PMAgent()
    user_request = "타오바오 링크를 분석하고 이미지를 현지화해줘"

    print(f"\n📝 사용자 요청: {user_request}")
    print(f"📋 계획 수립 모드...\n")

    try:
        result = pm.execute_workflow(user_request, auto_execute=False)

        print(f"\n📊 실행 계획:")
        print(f"  - 상태: {result['status']}")
        print(f"  - 분석된 작업 유형: {result['analysis'].get('task_type')}")
        print(f"  - 에이전트 대기열: {len(result['agent_queue'])}개")

        for i, agent in enumerate(result['agent_queue'], 1):
            print(f"    {i}. {agent['agent']}: {agent['description']}")

        print(f"\n✅ E2E Test 3 통과! (계획만 수립, 실행 안함)")
        return True

    except Exception as e:
        logger.error(f"E2E 테스트 실패: {e}")
        return False


def main():
    """전체 E2E 테스트 실행"""
    print("\n")
    print("="*80)
    print("🚀 End-to-End 통합 테스트 (PM Agent + Real Agents)")
    print("="*80)

    # ANTHROPIC_API_KEY 확인
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n❌ ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   실행 방법: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    tests = [
        ("수익성 분석 워크플로우", test_margin_check_workflow),
        ("상품 검색 워크플로우", test_product_search_workflow),
        ("계획 수립 모드", test_planning_only_mode),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"{test_name} 실패: {e}")
            results.append((test_name, False))

    # 최종 결과
    print("\n" + "="*80)
    print("📊 E2E 테스트 결과 요약")
    print("="*80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n전체: {passed}/{total} 통과 ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 모든 E2E 테스트 통과! Phase 3 완전 완료")
        sys.exit(0)
    else:
        print(f"\n⚠️ {total-passed}개 E2E 테스트 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
