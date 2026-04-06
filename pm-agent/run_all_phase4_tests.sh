#!/bin/bash
# Phase 4 Complete Test Suite Runner

echo "================================================================================"
echo "🧪 Phase 4 Review-First Publishing Console - Complete Test Suite"
echo "================================================================================"
echo ""

# Set working directory
cd "$(dirname "$0")"

# Test results
PASS_COUNT=0
FAIL_COUNT=0

# Function to run test
run_test() {
    local test_name="$1"
    local test_file="$2"

    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "Running: $test_name"
    echo "--------------------------------------------------------------------------------"

    if python3 "$test_file"; then
        echo "✅ $test_name PASSED"
        PASS_COUNT=$((PASS_COUNT + 1))
        return 0
    else
        echo "❌ $test_name FAILED"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
}

# Run tests
run_test "Happy-Path E2E Tests" "test_phase4_e2e_simple.py"
run_test "Blocked-Path Tests" "test_phase4_blocked_paths.py"

# Summary
echo ""
echo "================================================================================"
echo "📊 Test Suite Summary"
echo "================================================================================"
echo ""
echo "  ✅ Passed: $PASS_COUNT"
echo "  ❌ Failed: $FAIL_COUNT"
echo "  📊 Total:  $((PASS_COUNT + FAIL_COUNT))"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    echo ""
    echo "Phase 4 Review-First Publishing Console is production-ready."
    echo ""
    exit 0
else
    echo "⚠️  SOME TESTS FAILED"
    echo ""
    echo "Please review the test output above and fix failing tests."
    echo ""
    exit 1
fi
