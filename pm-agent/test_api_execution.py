#!/usr/bin/env python3
"""
API Execution 테스트 스크립트
"""

import sys
import json
import requests

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_single_agent_execution():
    """Test 1: 개별 에이전트 실행"""
    print_section("Test 1: 개별 에이전트 실행 (Sourcing Agent)")

    payload = {
        "agent": "sourcing",
        "input": {
            "source_url": "https://item.taobao.com/item.htm?id=123456789",
            "source_title": "휴대용 미니 블렌더",
            "keywords": ["블렌더", "휴대용"],
            "market": "korea"
        },
        "save_to_queue": False
    }

    try:
        response = requests.post(f"{BASE_URL}/api/agents/execute", json=payload, timeout=60)

        print(f"\n상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"실행 ID: {result['execution_id']}")
            print(f"상태: {result['status']}")
            print(f"메시지: {result['message']}")

            if result.get('result'):
                print(f"\n결과:")
                print(f"  소싱 판정: {result['result'].get('sourcing_decision', 'N/A')}")
                print(f"  리스크 플래그: {result['result'].get('risk_flags', [])}")

            print("\n✅ Test 1 PASS")
            return True
        else:
            print(f"❌ Test 1 FAIL: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Test 1 FAIL: {e}")
        return False

def test_workflow_execution():
    """Test 2: 워크플로우 실행"""
    print_section("Test 2: 워크플로우 실행 (quick_sourcing_check)")

    payload = {
        "workflow_name": "quick_sourcing_check",
        "user_input": {
            "source_url": "https://item.taobao.com/item.htm?id=987654321",
            "source_title": "스테인리스 텀블러",
            "market": "korea",
            "source_price_cny": 30.0,
            "weight_kg": 0.5
        },
        "save_to_queue": False
    }

    try:
        response = requests.post(f"{BASE_URL}/api/workflows/run", json=payload, timeout=120)

        print(f"\n상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"실행 ID: {result['execution_id']}")
            print(f"상태: {result['status']}")
            print(f"메시지: {result['message']}")

            if result.get('result'):
                print(f"\n결과:")
                for step_id, step_result in result['result'].items():
                    print(f"  {step_id}: {step_result['status']}")

            print("\n✅ Test 2 PASS")
            return True
        else:
            print(f"❌ Test 2 FAIL: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Test 2 FAIL: {e}")
        return False

def test_list_workflows():
    """Test 3: 워크플로우 목록 조회"""
    print_section("Test 3: 워크플로우 목록 조회")

    try:
        response = requests.get(f"{BASE_URL}/api/workflows/list", timeout=10)

        print(f"\n상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n사용 가능한 워크플로우:")
            for workflow in result['workflows']:
                print(f"  • {workflow['name']}: {workflow['description']} ({workflow['steps_count']} 단계)")

            print("\n✅ Test 3 PASS")
            return True
        else:
            print(f"❌ Test 3 FAIL: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Test 3 FAIL: {e}")
        return False

def test_content_agent():
    """Test 4: Content Agent 실행"""
    print_section("Test 4: Content Agent 실행")

    payload = {
        "agent": "content",
        "input": {
            "product_name": "스테인리스 텀블러",
            "product_category": "주방용품",
            "key_features": ["진공 단열", "500ml"],
            "price": 15900,
            "content_type": "product_page",
            "compliance_mode": True
        },
        "save_to_queue": False
    }

    try:
        response = requests.post(f"{BASE_URL}/api/agents/execute", json=payload, timeout=60)

        print(f"\n상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"실행 ID: {result['execution_id']}")
            print(f"상태: {result['status']}")

            if result.get('result'):
                print(f"\n생성된 콘텐츠:")
                print(f"  SEO 제목: {result['result'].get('seo_title', 'N/A')}")
                print(f"  컴플라이언스: {result['result'].get('compliance_status', 'N/A')}")

            print("\n✅ Test 4 PASS")
            return True
        else:
            print(f"❌ Test 4 FAIL: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Test 4 FAIL: {e}")
        return False

def main():
    print("\n" + "🤖" * 35)
    print("  API Execution 통합 테스트")
    print("🤖" * 35)

    print("\n⚠️  주의: PM Agent 서비스가 실행 중이어야 합니다.")
    print(f"   URL: {BASE_URL}")

    # Health check
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 서비스 정상 작동 중\n")
        else:
            print(f"❌ 서비스 응답 이상: {response.status_code}\n")
            return 1
    except Exception as e:
        print(f"❌ 서비스에 연결할 수 없습니다: {e}\n")
        print("   서비스를 먼저 시작하세요: sudo systemctl start pm-agent")
        return 1

    tests = [
        ("개별 에이전트 실행", test_single_agent_execution),
        ("워크플로우 실행", test_workflow_execution),
        ("워크플로우 목록 조회", test_list_workflows),
        ("Content Agent 실행", test_content_agent),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ 테스트 '{test_name}' 실행 중 예외: {e}")
            results.append((test_name, False))

    # 최종 요약
    print_section("📊 테스트 결과 요약")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    print()
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {test_name}")

    print(f"\n총 {total_count}개 중 {passed_count}개 통과 ({passed_count/total_count*100:.0f}%)")

    if passed_count == total_count:
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count}개 테스트 실패")
        return 1

if __name__ == "__main__":
    sys.exit(main())
