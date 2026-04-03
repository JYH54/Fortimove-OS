#!/usr/bin/env python3
"""
Unit Test: BaseAgent API Key Graceful Fail
목적: ANTHROPIC_API_KEY 없어도 시스템이 뻗지 않고 경고만 출력하는지 검증
"""

import os
import sys
from pathlib import Path

# Add pm-agent to path
sys.path.insert(0, str(Path(__file__).parent))

def test_api_key_missing():
    """Test 1: API 키 없을 때 Graceful Fail"""
    print("=" * 80)
    print("TEST 1: API KEY MISSING - Graceful Fail")
    print("=" * 80)

    # Remove API key from environment
    if 'ANTHROPIC_API_KEY' in os.environ:
        del os.environ['ANTHROPIC_API_KEY']

    try:
        from agent_framework import BaseAgent, TaskResult, AgentStatus
        from pydantic import BaseModel
        from typing import Dict, Any, Type

        # Create a minimal test agent
        class TestAgent(BaseAgent):
            def __init__(self):
                super().__init__("test_agent")

            @property
            def input_schema(self) -> Type[BaseModel]:
                class InputSchema(BaseModel):
                    message: str
                return InputSchema

            @property
            def output_schema(self) -> Type[BaseModel]:
                class OutputSchema(BaseModel):
                    result: str
                return OutputSchema

            def _do_execute(self, input_model: BaseModel) -> Dict[str, Any]:
                if not self._api_available:
                    return {"result": "FALLBACK: API 키 없음, 기본 응답 반환"}
                return {"result": "SUCCESS"}

        # Instantiate agent
        agent = TestAgent()

        # Check API availability flag
        assert hasattr(agent, '_api_available'), "❌ _api_available 속성 없음"
        assert agent._api_available == False, "❌ API 키 없는데 _api_available=True"

        # Execute agent
        result = agent.execute({"message": "test"})

        # Verify it didn't crash
        assert result.status != AgentStatus.FAILED.value, f"❌ 시스템 크래시: {result.error}"
        assert "FALLBACK" in result.output.get("result", ""), "❌ Fallback 로직 미작동"

        print("✅ Test 1 PASSED: API 키 없어도 시스템 정상 작동")
        print(f"   - _api_available: {agent._api_available}")
        print(f"   - Status: {result.status}")
        print(f"   - Output: {result.output}")

    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_api_key_placeholder():
    """Test 2: API 키가 PLACEHOLDER일 때"""
    print("\n" + "=" * 80)
    print("TEST 2: API KEY PLACEHOLDER")
    print("=" * 80)

    os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-api03-PLACEHOLDER-REPLACE-WITH-REAL-KEY'

    try:
        # Reimport to reload environment
        import importlib
        import agent_framework
        importlib.reload(agent_framework)

        from agent_framework import BaseAgent
        from pydantic import BaseModel
        from typing import Dict, Any, Type

        class TestAgent(BaseAgent):
            def __init__(self):
                super().__init__("test_agent_placeholder")

            @property
            def input_schema(self) -> Type[BaseModel]:
                class InputSchema(BaseModel):
                    message: str
                return InputSchema

            @property
            def output_schema(self) -> Type[BaseModel]:
                class OutputSchema(BaseModel):
                    result: str
                return OutputSchema

            def _do_execute(self, input_model: BaseModel) -> Dict[str, Any]:
                return {"result": "test"}

        agent = TestAgent()

        assert agent._api_available == False, "❌ PLACEHOLDER인데 _api_available=True"

        print("✅ Test 2 PASSED: PLACEHOLDER도 정상적으로 감지")
        print(f"   - _api_available: {agent._api_available}")

    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_api_key_valid():
    """Test 3: 유효한 API 키"""
    print("\n" + "=" * 80)
    print("TEST 3: VALID API KEY")
    print("=" * 80)

    os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-api03-valid-key-example-12345'

    try:
        import importlib
        import agent_framework
        importlib.reload(agent_framework)

        from agent_framework import BaseAgent
        from pydantic import BaseModel
        from typing import Dict, Any, Type

        class TestAgent(BaseAgent):
            def __init__(self):
                super().__init__("test_agent_valid")

            @property
            def input_schema(self) -> Type[BaseModel]:
                class InputSchema(BaseModel):
                    message: str
                return InputSchema

            @property
            def output_schema(self) -> Type[BaseModel]:
                class OutputSchema(BaseModel):
                    result: str
                return OutputSchema

            def _do_execute(self, input_model: BaseModel) -> Dict[str, Any]:
                return {"result": "test"}

        agent = TestAgent()

        assert agent._api_available == True, "❌ 유효한 키인데 _api_available=False"

        print("✅ Test 3 PASSED: 유효한 API 키 정상 인식")
        print(f"   - _api_available: {agent._api_available}")

    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    print("\n🧪 BaseAgent Dependency Check Unit Tests\n")

    results = []
    results.append(("API Key Missing", test_api_key_missing()))
    results.append(("API Key Placeholder", test_api_key_placeholder()))
    results.append(("API Key Valid", test_api_key_valid()))

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\n총 {passed}/{total} 테스트 통과")

    if passed == total:
        print("\n🎉 모든 테스트 통과!")
        sys.exit(0)
    else:
        print("\n❌ 일부 테스트 실패")
        sys.exit(1)
