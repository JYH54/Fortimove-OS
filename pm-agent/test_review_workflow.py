#!/usr/bin/env python3
"""
Review Workflow State Machine Test
상태 전환 규칙 검증 테스트
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from review_workflow import ReviewWorkflow, validate_status_transition, get_allowed_next_statuses


def test_valid_transitions():
    """유효한 상태 전환 테스트"""
    print("=" * 60)
    print("TEST 1: Valid Transitions")
    print("=" * 60)

    workflow = ReviewWorkflow()

    valid_cases = [
        ("draft", "under_review"),
        ("draft", "hold"),
        ("under_review", "approved_for_export"),
        ("under_review", "hold"),
        ("under_review", "rejected"),
        ("approved_for_export", "approved_for_upload"),
        ("approved_for_export", "hold"),
        ("approved_for_upload", "hold"),
        ("hold", "under_review"),
        ("hold", "rejected"),
    ]

    passed = 0
    failed = 0

    for current, new in valid_cases:
        result = validate_status_transition(current, new)
        if result.allowed:
            print(f"  ✅ {current:20} → {new:20} : PASS")
            passed += 1
        else:
            print(f"  ❌ {current:20} → {new:20} : FAIL (expected PASS)")
            print(f"     Error: {result.error_message}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_invalid_transitions():
    """유효하지 않은 상태 전환 테스트"""
    print("\n" + "=" * 60)
    print("TEST 2: Invalid Transitions")
    print("=" * 60)

    workflow = ReviewWorkflow()

    invalid_cases = [
        ("draft", "approved_for_export"),  # Cannot skip under_review
        ("draft", "rejected"),  # Cannot reject draft directly
        ("rejected", "under_review"),  # Terminal state
        ("rejected", "approved_for_export"),  # Terminal state
        ("approved_for_export", "draft"),  # Cannot go back to draft
        ("approved_for_upload", "under_review"),  # Cannot go back to under_review
        ("hold", "approved_for_export"),  # Must go through under_review first
    ]

    passed = 0
    failed = 0

    for current, new in invalid_cases:
        result = validate_status_transition(current, new)
        if not result.allowed:
            print(f"  ✅ {current:20} → {new:20} : CORRECTLY BLOCKED")
            print(f"     Reason: {result.error_message}")
            passed += 1
        else:
            print(f"  ❌ {current:20} → {new:20} : FAIL (expected BLOCK)")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_same_state_transition():
    """동일 상태로의 전환 (no-op) 테스트"""
    print("\n" + "=" * 60)
    print("TEST 3: Same State Transitions (no-op)")
    print("=" * 60)

    workflow = ReviewWorkflow()

    statuses = ["draft", "under_review", "approved_for_export", "approved_for_upload", "hold", "rejected"]

    passed = 0
    failed = 0

    for status in statuses:
        result = validate_status_transition(status, status)
        if result.allowed:
            print(f"  ✅ {status:20} → {status:20} : PASS (no-op)")
            passed += 1
        else:
            print(f"  ❌ {status:20} → {status:20} : FAIL (expected PASS)")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_get_allowed_actions():
    """가능한 액션 목록 조회 테스트"""
    print("\n" + "=" * 60)
    print("TEST 4: Get Allowed Actions")
    print("=" * 60)

    workflow = ReviewWorkflow()

    test_cases = [
        ("draft", ["under_review", "hold"]),
        ("under_review", ["approved_for_export", "hold", "rejected"]),
        ("approved_for_export", ["approved_for_upload", "hold"]),
        ("approved_for_upload", ["hold"]),
        ("hold", ["under_review", "rejected"]),
        ("rejected", []),
    ]

    passed = 0
    failed = 0

    for status, expected in test_cases:
        allowed = get_allowed_next_statuses(status)
        if set(allowed) == set(expected):
            print(f"  ✅ {status:20} : {', '.join(allowed) if allowed else '(none)'}")
            passed += 1
        else:
            print(f"  ❌ {status:20} : FAIL")
            print(f"     Expected: {expected}")
            print(f"     Got: {allowed}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_terminal_state():
    """종료 상태 테스트"""
    print("\n" + "=" * 60)
    print("TEST 5: Terminal State Detection")
    print("=" * 60)

    workflow = ReviewWorkflow()

    test_cases = [
        ("draft", False),
        ("under_review", False),
        ("approved_for_export", False),
        ("approved_for_upload", False),
        ("hold", False),
        ("rejected", True),
    ]

    passed = 0
    failed = 0

    for status, is_terminal in test_cases:
        result = workflow.is_terminal_state(status)
        if result == is_terminal:
            print(f"  ✅ {status:20} : {'TERMINAL' if is_terminal else 'NON-TERMINAL'}")
            passed += 1
        else:
            print(f"  ❌ {status:20} : FAIL (expected {'TERMINAL' if is_terminal else 'NON-TERMINAL'})")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_state_path():
    """상태 경로 탐색 테스트"""
    print("\n" + "=" * 60)
    print("TEST 6: State Path Finding (BFS)")
    print("=" * 60)

    workflow = ReviewWorkflow()

    # Test cases: (start, end, should_have_path)
    test_cases = [
        ("draft", "approved_for_export", True),
        ("draft", "rejected", True),  # Can go via either under_review or hold
        ("hold", "approved_for_export", True),
        ("rejected", "approved_for_export", False),  # Cannot escape rejected (terminal)
        ("draft", "approved_for_upload", True),  # Long path: draft → under_review → approved_for_export → approved_for_upload
    ]

    passed = 0
    failed = 0

    for start, end, should_have_path in test_cases:
        path = workflow.get_state_path(start, end)
        has_path = path is not None

        if has_path == should_have_path:
            print(f"  ✅ {start:20} → {end:20}")
            if path:
                print(f"     Path: {' → '.join(path)}")
            else:
                print(f"     Path: NO PATH (as expected)")
            passed += 1
        else:
            print(f"  ❌ {start:20} → {end:20} : FAIL")
            print(f"     Expected path: {should_have_path}")
            print(f"     Got path: {path}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "=" * 60)
    print("REVIEW WORKFLOW STATE MACHINE TEST SUITE")
    print("=" * 60)

    results = []

    results.append(("Valid Transitions", test_valid_transitions()))
    results.append(("Invalid Transitions", test_invalid_transitions()))
    results.append(("Same State Transitions", test_same_state_transition()))
    results.append(("Get Allowed Actions", test_get_allowed_actions()))
    results.append(("Terminal State Detection", test_terminal_state()))
    results.append(("State Path Finding", test_state_path()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} : {test_name}")

    print(f"\n  Total: {len(results)} tests, {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
