"""
Critical Fixes 통합 테스트
1. Workflow Executor Hook 통합
2. Margin Check Agent 완전 구현
3. Sourcing Agent 신규 구현
"""

import sys
import json
from agent_framework import WorkflowExecutor, AgentRegistry, ExecutionContext
from sourcing_agent import SourcingAgent
from real_agents import MarginCheckAgent
from product_registration_agent import ProductRegistrationAgent
from cs_agent import CSAgent

def test_workflow_hook_integration():
    """Test 1: Workflow Executor Hook 통합 테스트"""
    print("\n" + "="*60)
    print("TEST 1: Workflow Executor Hook 통합")
    print("="*60)

    # Registry 생성 및 에이전트 등록
    registry = AgentRegistry()
    registry.register("sourcing", SourcingAgent())
    registry.register("margin_check", MarginCheckAgent())

    # WorkflowExecutor 생성 (Agent Status Tracker 자동 초기화)
    executor = WorkflowExecutor(registry)

    # Workflow 정의
    workflow = [
        {
            "step_id": "step_1",
            "agent": "sourcing",
            "depends_on": [],
            "expected_status": ["completed"],
            "input_mapping": {
                "source_url": "literal.https://item.taobao.com/item.htm?id=123456",
                "source_title": "literal.프리미엄 비타민C 세럼",
                "keywords": "literal.['비타민', '세럼']"
            },
            "checks": {
                "required_fields": ["source_url"],
                "fail_message": "URL 필수"
            }
        }
    ]

    # ExecutionContext 생성
    context = ExecutionContext(raw_message="타오바오 상품 소싱 테스트", structured_input={})

    # Workflow 실행
    result = executor.execute_sequential(workflow, context)

    # Agent Status Tracker 확인
    if executor.agent_tracker:
        print("\n✅ Agent Status Tracker 초기화 성공")
        status = executor.agent_tracker.get_all_agent_status()
        print(f"📊 Sourcing Agent 상태: {status['agents'].get('sourcing', {}).get('status', 'unknown')}")
        print(f"📊 총 실행 횟수: {status['agents'].get('sourcing', {}).get('total_executions', 0)}")

        # Workflow 이력 확인
        history = executor.agent_tracker.get_workflow_history(limit=1)
        if history:
            print(f"📋 Workflow 기록: {history[0]['workflow_id']} ({history[0]['status']})")
        else:
            print("⚠️ Workflow 이력 없음")
    else:
        print("❌ Agent Status Tracker 초기화 실패")

    print("\n✅ TEST 1 완료")
    return executor.agent_tracker is not None


def test_margin_calculate_detailed():
    """Test 2: Margin Check Agent 상세 계산 테스트"""
    print("\n" + "="*60)
    print("TEST 2: Margin Check Agent 상세 마진 계산")
    print("="*60)

    agent = MarginCheckAgent()

    # 테스트 입력: 실제 원가 구조
    input_data = {
        "action": "calculate_margin",
        "source_price_cny": 100.0,      # 매입가 100위안
        "exchange_rate": 200.0,          # 환율 1위안 = 200원
        "weight_kg": 1.0,                # 1kg
        "platform_fee_rate": 0.15,       # 수수료 15%
        "discount_rate": 0.05,           # 할인 5%
        "target_margin_rate": 0.30       # 목표 마진 30%
    }

    result = agent.execute(input_data)

    if result.is_success():
        print("\n✅ 마진 계산 성공")
        output = result.output

        # 원가 분석
        cost = output.get("cost_breakdown", {})
        print(f"\n📊 원가 분석:")
        print(f"  • 매입가: {cost.get('source_price_krw', 0):,.0f}원")
        print(f"  • 배송비: {cost.get('shipping_fee_krw', 0):,.0f}원")
        print(f"  • 포장비: {cost.get('packaging_fee_krw', 0):,.0f}원")
        print(f"  • 검수비: {cost.get('inspection_fee_krw', 0):,.0f}원")
        print(f"  • 총 원가: {cost.get('total_cost_krw', 0):,.0f}원")

        # 마진 분석
        margin = output.get("margin_analysis", {})
        print(f"\n💰 마진 분석:")
        print(f"  • 손익분기 판매가: {margin.get('break_even_price', 0):,.0f}원")
        print(f"  • 목표 마진 판매가: {margin.get('target_price', 0):,.0f}원")
        print(f"  • 순이익: {margin.get('net_profit', 0):,.0f}원")
        print(f"  • 순이익률: {margin.get('net_margin_rate', 0):.1f}%")

        # 최종 판정
        decision = output.get("final_decision", "unknown")
        warnings = output.get("risk_warnings", [])
        print(f"\n🎯 최종 판정: {decision}")
        if warnings:
            print(f"⚠️ 리스크 경고:")
            for w in warnings:
                print(f"  {w}")

        print("\n✅ TEST 2 완료")
        return decision in ["등록 가능", "재검토", "제외"]
    else:
        print(f"\n❌ 마진 계산 실패: {result.error}")
        return False


def test_sourcing_agent():
    """Test 3: Sourcing Agent 기본 기능 테스트"""
    print("\n" + "="*60)
    print("TEST 3: Sourcing Agent 신규 구현")
    print("="*60)

    agent = SourcingAgent()

    # 테스트 입력 1: 안전한 상품
    input_safe = {
        "source_url": "https://item.taobao.com/item.htm?id=123456",
        "source_title": "프리미엄 스테인리스 텀블러",
        "keywords": ["텀블러", "보온병"],
        "source_price_cny": 50.0
    }

    result_safe = agent.execute(input_safe)

    if result_safe.is_success():
        output = result_safe.output
        print(f"\n✅ 안전 상품 분석 성공")
        print(f"  • 상품 분류: {output.get('product_classification', 'unknown')}")
        print(f"  • 소싱 판정: {output.get('sourcing_decision', 'unknown')}")
        print(f"  • 리스크 플래그: {', '.join(output.get('risk_flags', [])) or '없음'}")
        print(f"  • 다음 단계: {output.get('next_step_recommendation', 'unknown')}")

        # 벤더 질문 확인
        questions_ko = output.get("vendor_questions_ko", [])
        print(f"\n💬 벤더 질문 (한국어): {len(questions_ko)}개")
        for i, q in enumerate(questions_ko[:3], 1):
            print(f"  {i}. {q}")

    else:
        print(f"❌ 안전 상품 분석 실패: {result_safe.error}")
        return False

    # 테스트 입력 2: 리스크 상품
    input_risk = {
        "source_url": "https://item.taobao.com/item.htm?id=654321",
        "source_title": "나이키 에어맥스 스니커즈",
        "keywords": ["나이키", "신발"],
        "source_price_cny": 200.0
    }

    result_risk = agent.execute(input_risk)

    if result_risk.is_success():
        output_risk = result_risk.output
        print(f"\n✅ 리스크 상품 분석 성공")
        print(f"  • 상품 분류: {output_risk.get('product_classification', 'unknown')}")
        print(f"  • 소싱 판정: {output_risk.get('sourcing_decision', 'unknown')}")
        print(f"  • 리스크 플래그: {', '.join(output_risk.get('risk_flags', [])) or '없음'}")

        risk_details = output_risk.get("risk_details", {})
        if risk_details:
            print(f"  • 리스크 상세:")
            for risk_type, keywords in risk_details.items():
                print(f"    - {risk_type}: {', '.join(keywords)}")

        print(f"  • 다음 단계: {output_risk.get('next_step_recommendation', 'unknown')}")

    else:
        print(f"❌ 리스크 상품 분석 실패: {result_risk.error}")
        return False

    print("\n✅ TEST 3 완료")
    return True


def test_full_workflow():
    """Test 4: 전체 워크플로우 통합 테스트"""
    print("\n" + "="*60)
    print("TEST 4: 전체 워크플로우 통합 (Sourcing → Margin → Product Registration)")
    print("="*60)

    # Registry 생성
    registry = AgentRegistry()
    registry.register("sourcing", SourcingAgent())
    registry.register("margin_check", MarginCheckAgent())
    registry.register("product_registration", ProductRegistrationAgent())

    # WorkflowExecutor 생성
    executor = WorkflowExecutor(registry)

    # 전체 Workflow 정의
    workflow = [
        {
            "step_id": "sourcing_step",
            "agent": "sourcing",
            "depends_on": [],
            "expected_status": ["completed"],
            "input_mapping": {
                "source_url": "literal.https://item.taobao.com/item.htm?id=999999",
                "source_title": "literal.프리미엄 유리 물병",
                "source_price_cny": "literal.80.0",
                "keywords": "literal.[]"
            },
            "checks": {
                "required_fields": ["source_url"]
            }
        },
        {
            "step_id": "margin_step",
            "agent": "margin_check",
            "depends_on": ["sourcing_step"],
            "expected_status": ["completed"],
            "input_mapping": {
                "action": "literal.calculate_margin",
                "source_price_cny": "literal.80.0",
                "exchange_rate": "literal.200.0",
                "weight_kg": "literal.0.8"
            },
            "checks": {
                "required_fields": ["action"]
            }
        },
        {
            "step_id": "registration_step",
            "agent": "product_registration",
            "depends_on": ["margin_step"],
            "expected_status": ["completed"],
            "input_mapping": {
                "source_title": "literal.프리미엄 유리 물병",
                "source_options": "literal.[]",
                "source_description": "literal.친환경 유리 재질"
            },
            "checks": {
                "required_fields": ["source_title"]
            }
        }
    ]

    # ExecutionContext 생성
    context = ExecutionContext(
        raw_message="타오바오 상품 전체 워크플로우 테스트",
        structured_input={}
    )

    # Workflow 실행
    result_context = executor.execute_sequential(workflow, context)

    # 결과 검증
    print(f"\n📊 워크플로우 실행 결과:")
    for step_id, result in result_context.results.items():
        status_emoji = "✅" if result.is_success() else "❌"
        print(f"  {status_emoji} {step_id}: {result.status}")

    # Agent Status 확인
    if executor.agent_tracker:
        print(f"\n📈 Agent Status Tracker:")
        stats = executor.agent_tracker.get_statistics()
        print(f"  • 총 워크플로우: {stats['total_workflows']}개")
        print(f"  • 완료: {stats['completed_workflows']}개")
        print(f"  • 실패: {stats['failed_workflows']}개")

    print("\n✅ TEST 4 완료")
    return all(r.is_success() for r in result_context.results.values())


if __name__ == "__main__":
    print("\n" + "🔥"*30)
    print("Critical Fixes 통합 테스트 시작")
    print("🔥"*30)

    results = []

    # Test 1: Workflow Hook
    try:
        results.append(("Workflow Hook 통합", test_workflow_hook_integration()))
    except Exception as e:
        print(f"\n❌ TEST 1 예외 발생: {e}")
        results.append(("Workflow Hook 통합", False))

    # Test 2: Margin Agent
    try:
        results.append(("Margin Check Agent", test_margin_calculate_detailed()))
    except Exception as e:
        print(f"\n❌ TEST 2 예외 발생: {e}")
        results.append(("Margin Check Agent", False))

    # Test 3: Sourcing Agent
    try:
        results.append(("Sourcing Agent", test_sourcing_agent()))
    except Exception as e:
        print(f"\n❌ TEST 3 예외 발생: {e}")
        results.append(("Sourcing Agent", False))

    # Test 4: Full Workflow
    try:
        results.append(("전체 워크플로우", test_full_workflow()))
    except Exception as e:
        print(f"\n❌ TEST 4 예외 발생: {e}")
        results.append(("전체 워크플로우", False))

    # 최종 결과
    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n총 {total}개 중 {passed}개 통과 ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 모든 테스트 통과!")
        sys.exit(0)
    else:
        print(f"\n⚠️ {total - passed}개 테스트 실패")
        sys.exit(1)
