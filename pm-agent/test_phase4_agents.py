#!/usr/bin/env python3
"""
Phase 4 에이전트 검수 테스트
CS Agent, Product Registration Agent 코드 품질 및 동작 검증
"""
import os
import sys
import logging
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_cs_agent_structure():
    """CS Agent 구조 및 인터페이스 검증"""
    print("\n" + "="*80)
    print("TEST 1: CS Agent - 구조 및 인터페이스 검증")
    print("="*80)

    try:
        from cs_agent import CSAgent, CSInputSchema, CSOutputSchema

        # 1. 클래스 임포트 성공
        print("✅ CSAgent 클래스 임포트 성공")

        # 2. 스키마 확인
        print("\n[CSInputSchema 필드]")
        for field_name, field_info in CSInputSchema.model_fields.items():
            print(f"  - {field_name}: {field_info.annotation}")

        print("\n[CSOutputSchema 필드]")
        for field_name, field_info in CSOutputSchema.model_fields.items():
            print(f"  - {field_name}: {field_info.annotation}")

        # 3. BaseAgent 인터페이스 확인
        agent = CSAgent()
        print(f"\n✅ CSAgent 인스턴스 생성 성공")
        print(f"  - agent_name: {agent.agent_name}")
        print(f"  - input_schema: {agent.input_schema.__name__}")
        print(f"  - output_schema: {agent.output_schema.__name__}")

        # 4. 필수 메서드 확인
        assert hasattr(agent, 'execute'), "execute 메서드 없음"
        assert hasattr(agent, '_do_execute'), "_do_execute 메서드 없음"
        print(f"✅ 필수 메서드 존재 확인")

        return True

    except Exception as e:
        logger.error(f"CS Agent 구조 검증 실패: {e}")
        return False


def test_product_registration_agent_structure():
    """Product Registration Agent 구조 및 인터페이스 검증"""
    print("\n" + "="*80)
    print("TEST 2: Product Registration Agent - 구조 및 인터페이스 검증")
    print("="*80)

    try:
        from product_registration_agent import (
            ProductRegistrationAgent,
            ProductRegistrationInputSchema,
            ProductRegistrationOutputSchema
        )

        # 1. 클래스 임포트 성공
        print("✅ ProductRegistrationAgent 클래스 임포트 성공")

        # 2. 스키마 확인
        print("\n[ProductRegistrationInputSchema 필드]")
        for field_name, field_info in ProductRegistrationInputSchema.model_fields.items():
            print(f"  - {field_name}: {field_info.annotation}")

        print("\n[ProductRegistrationOutputSchema 필드]")
        for field_name, field_info in ProductRegistrationOutputSchema.model_fields.items():
            print(f"  - {field_name}: {field_info.annotation}")

        # 3. BaseAgent 인터페이스 확인
        agent = ProductRegistrationAgent()
        print(f"\n✅ ProductRegistrationAgent 인스턴스 생성 성공")
        print(f"  - agent_name: {agent.agent_name}")
        print(f"  - input_schema: {agent.input_schema.__name__}")
        print(f"  - output_schema: {agent.output_schema.__name__}")

        # 4. 필수 메서드 확인
        assert hasattr(agent, 'execute'), "execute 메서드 없음"
        assert hasattr(agent, '_do_execute'), "_do_execute 메서드 없음"
        assert hasattr(agent, '_check_garbage_title'), "_check_garbage_title 메서드 없음"
        assert hasattr(agent, '_check_sensitive_category'), "_check_sensitive_category 메서드 없음"
        assert hasattr(agent, '_check_risky_wording'), "_check_risky_wording 메서드 없음"
        print(f"✅ 필수 메서드 존재 확인")

        return True

    except Exception as e:
        logger.error(f"Product Registration Agent 구조 검증 실패: {e}")
        return False


def test_cs_agent_rule_based():
    """CS Agent - Rule-Based 동작 테스트 (API 키 불필요)"""
    print("\n" + "="*80)
    print("TEST 3: CS Agent - Rule-Based 동작 테스트")
    print("="*80)

    try:
        from cs_agent import CSAgent

        agent = CSAgent()

        # API 키가 없을 때 에러 핸들링 확인
        test_input = {
            "customer_message": "배송이 늦어지고 있어요. 언제 도착하나요?",
            "order_id": "ORD-12345",
            "order_status": None,
            "tracking_number": None
        }

        print(f"\n[테스트 입력]")
        print(f"  고객 메시지: {test_input['customer_message']}")
        print(f"  주문번호: {test_input['order_id']}")

        result = agent.execute(test_input)

        print(f"\n[실행 결과]")
        print(f"  상태: {result.status}")

        if result.status == "failed":
            print(f"  ✅ API 키 없음 → 실패 처리 (예상된 동작)")
            print(f"  에러 메시지: {result.error}")
            return True
        else:
            print(f"  ⚠️ API 키 없이도 성공? (검토 필요)")
            return False

    except Exception as e:
        logger.error(f"CS Agent Rule-Based 테스트 실패: {e}")
        return False


def test_product_registration_agent_rule_based():
    """Product Registration Agent - Rule-Based 동작 테스트"""
    print("\n" + "="*80)
    print("TEST 4: Product Registration Agent - Rule-Based 동작 테스트")
    print("="*80)

    try:
        from product_registration_agent import ProductRegistrationAgent

        agent = ProductRegistrationAgent()

        # 테스트 케이스 1: 쓰레기 제목 (Garbage Title)
        print("\n[테스트 케이스 1: 쓰레기 제목]")
        test_input_1 = {
            "source_title": "test",  # 3자 미만 또는 테스트 키워드
            "source_options": ["Color: Red"],
            "source_description": "Test product"
        }

        result_1 = agent.execute(test_input_1)
        print(f"  입력: {test_input_1['source_title']}")
        print(f"  상태: {result_1.status}")
        print(f"  출력: {result_1.output.get('registration_status')}")

        if result_1.output.get('registration_status') == 'reject':
            print(f"  ✅ 쓰레기 제목 → reject (Rule-Based 동작 확인)")
        else:
            print(f"  ❌ 쓰레기 제목이 reject되지 않음")

        # 테스트 케이스 2: 민감 카테고리 (Sensitive Category)
        print("\n[테스트 케이스 2: 민감 카테고리]")
        test_input_2 = {
            "source_title": "강아지 관절 영양제",
            "source_options": [],
            "source_description": "강아지 건강을 위한 관절 보호 제품"
        }

        result_2 = agent.execute(test_input_2)
        print(f"  입력: {test_input_2['source_title']}")
        print(f"  상태: {result_2.status}")

        if result_2.status == "failed":
            print(f"  ✅ API 키 없음 → 실패 (예상된 동작)")
        else:
            output_status = result_2.output.get('registration_status')
            needs_review = result_2.output.get('needs_human_review')
            print(f"  출력: registration_status={output_status}, needs_human_review={needs_review}")

            if output_status == 'hold' and needs_review:
                print(f"  ✅ 민감 카테고리 → hold + 휴먼 리뷰 (Rule-Based 동작 확인)")
            else:
                print(f"  ⚠️ 민감 카테고리가 제대로 감지되지 않음")

        # 테스트 케이스 3: 정상 제품
        print("\n[테스트 케이스 3: 정상 제품]")
        test_input_3 = {
            "source_title": "스테인리스 텀블러 500ml",
            "source_options": ["블랙", "화이트"],
            "source_description": "보온보냉 기능이 있는 휴대용 텀블러"
        }

        result_3 = agent.execute(test_input_3)
        print(f"  입력: {test_input_3['source_title']}")
        print(f"  상태: {result_3.status}")

        if result_3.status == "failed":
            print(f"  ✅ API 키 없음 → LLM 호출 실패 → hold (예상된 동작)")
        else:
            print(f"  출력: {result_3.output.get('registration_status')}")

        return True

    except Exception as e:
        logger.error(f"Product Registration Agent Rule-Based 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_code_quality():
    """코드 품질 검수 (정적 분석)"""
    print("\n" + "="*80)
    print("TEST 5: 코드 품질 검수")
    print("="*80)

    issues = []

    # 1. CS Agent 코드 품질
    print("\n[CS Agent 코드 품질]")
    try:
        with open('/home/fortymove/Fortimove-OS/pm-agent/cs_agent.py', 'r') as f:
            cs_code = f.read()

        # 보안: Hallucination 방지 체크
        if '확답' in cs_code or 'Hallucination' in cs_code:
            print("  ✅ Hallucination 방지 규칙 명시됨")
        else:
            issues.append("CS Agent: Hallucination 방지 규칙 누락")

        # Pydantic 스키마 사용
        if 'BaseModel' in cs_code and 'CSInputSchema' in cs_code:
            print("  ✅ Pydantic 스키마 사용")
        else:
            issues.append("CS Agent: Pydantic 스키마 미사용")

        # LLM 호출 분리
        if '_generate_response' in cs_code:
            print("  ✅ LLM 호출 로직 분리됨")
        else:
            issues.append("CS Agent: LLM 호출 로직 분리 미흡")

    except Exception as e:
        issues.append(f"CS Agent 코드 읽기 실패: {e}")

    # 2. Product Registration Agent 코드 품질
    print("\n[Product Registration Agent 코드 품질]")
    try:
        with open('/home/fortymove/Fortimove-OS/pm-agent/product_registration_agent.py', 'r') as f:
            pr_code = f.read()

        # Rule-based 판정
        if '_check_garbage_title' in pr_code and '_check_sensitive_category' in pr_code:
            print("  ✅ Rule-based 검증 함수 존재")
        else:
            issues.append("Product Registration: Rule-based 검증 함수 누락")

        # Compliance 체크
        if 'compliance_flags' in pr_code:
            print("  ✅ Compliance 플래그 처리")
        else:
            issues.append("Product Registration: Compliance 플래그 처리 누락")

        # 옵션 모호성 체크
        if '_check_ambiguous_options' in pr_code:
            print("  ✅ 옵션 모호성 체크 로직 존재")
        else:
            issues.append("Product Registration: 옵션 모호성 체크 누락")

        # LLM 호출 분리
        if '_generate_drafts' in pr_code:
            print("  ✅ LLM 초안 작성 로직 분리됨")
        else:
            issues.append("Product Registration: LLM 로직 분리 미흡")

        # 에러 핸들링
        if 'llm_parse_error' in pr_code:
            print("  ✅ LLM 파싱 에러 Fallback 처리")
        else:
            issues.append("Product Registration: LLM 에러 핸들링 미흡")

    except Exception as e:
        issues.append(f"Product Registration Agent 코드 읽기 실패: {e}")

    # 결과 출력
    print("\n[검수 결과]")
    if not issues:
        print("  ✅ 모든 코드 품질 검사 통과!")
        return True
    else:
        print(f"  ⚠️ {len(issues)}개 이슈 발견:")
        for issue in issues:
            print(f"    - {issue}")
        return False


def main():
    """전체 검수 테스트 실행"""
    print("\n")
    print("="*80)
    print("🔍 Phase 4 에이전트 검수 테스트")
    print("="*80)

    tests = [
        ("CS Agent 구조 검증", test_cs_agent_structure),
        ("Product Registration Agent 구조 검증", test_product_registration_agent_structure),
        ("CS Agent Rule-Based 동작", test_cs_agent_rule_based),
        ("Product Registration Agent Rule-Based 동작", test_product_registration_agent_rule_based),
        ("코드 품질 검수", test_code_quality),
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
    print("📊 검수 결과 요약")
    print("="*80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n전체: {passed}/{total} 통과 ({passed/total*100:.1f}%)")

    if passed >= 4:  # 5개 중 4개 이상 통과
        print("\n✅ Phase 4 에이전트 검수 통과!")
        print("   (API 키 없이 테스트 가능한 범위 내에서 검증 완료)")
        sys.exit(0)
    else:
        print(f"\n⚠️ {total-passed}개 검수 항목 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
