#!/usr/bin/env python3
"""
Content Agent 테스트 스크립트
- 상품 상세페이지 카피 생성 테스트
- SNS 콘텐츠 생성 테스트
- 광고 문구 생성 테스트
- Alt text 생성 테스트
- 컴플라이언스 검증 테스트
"""

import sys
import json
from content_agent import ContentAgent

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_product_page_generation():
    """Test 1: 상품 상세페이지 카피 생성"""
    print_section("Test 1: 상품 상세페이지 카피 생성")

    agent = ContentAgent()

    input_data = {
        "product_name": "프리미엄 비타민C 세럼",
        "product_category": "스킨케어",
        "product_description": "맑고 투명한 피부를 위한 고농축 비타민C 세럼",
        "key_features": ["고농축 비타민C 20%", "히알루론산 함유", "무향료 무알코올"],
        "price": 29900,
        "target_customer": "20-30대 여성",
        "target_platform": "smartstore",
        "content_type": "product_page",
        "tone": "neutral",
        "seo_keywords": ["비타민C", "세럼", "스킨케어"],
        "compliance_mode": True
    }

    print("\n📥 입력 데이터:")
    print(f"  - 상품명: {input_data['product_name']}")
    print(f"  - 카테고리: {input_data['product_category']}")
    print(f"  - 콘텐츠 유형: {input_data['content_type']}")
    print(f"  - 컴플라이언스 모드: {input_data['compliance_mode']}")

    try:
        result = agent.execute(input_data)

        print("\n📤 생성 결과:")
        print(f"  - 상태: {result.status}")

        if result.is_success():
            output = result.output
            print(f"\n  📝 메인 콘텐츠:")
            print(f"  {output.get('main_content', 'N/A')[:200]}...")

            print(f"\n  🔍 SEO 제목: {output.get('seo_title', 'N/A')}")
            print(f"  🔍 SEO 설명: {output.get('seo_description', 'N/A')[:80]}...")

            variations = output.get('variations', [])
            print(f"\n  📋 대안 버전 ({len(variations)}개):")
            for i, var in enumerate(variations[:2], 1):
                print(f"    {i}. {var[:100]}...")

            warnings = output.get('warnings', [])
            if warnings:
                print(f"\n  ⚠️  경고 ({len(warnings)}개):")
                for w in warnings:
                    print(f"    - {w}")

            compliance_status = output.get('compliance_status', 'unknown')
            print(f"\n  ✅ 컴플라이언스 상태: {compliance_status}")

            print("\n✅ Test 1 PASS: 상품 상세페이지 생성 성공")
            return True
        else:
            print(f"\n❌ Test 1 FAIL: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Test 1 FAIL: 예외 발생 - {e}")
        return False

def test_sns_content_generation():
    """Test 2: SNS 콘텐츠 생성"""
    print_section("Test 2: SNS 콘텐츠 생성")

    agent = ContentAgent()

    input_data = {
        "product_name": "휴대용 미니 블렌더",
        "product_category": "주방용품",
        "product_description": "언제 어디서나 신선한 스무디를",
        "key_features": ["USB 충전식", "500ml 대용량", "세척 간편"],
        "price": 24900,
        "target_customer": "직장인",
        "target_platform": "instagram",
        "content_type": "sns",
        "tone": "friendly",
        "compliance_mode": True
    }

    print("\n📥 입력 데이터:")
    print(f"  - 상품명: {input_data['product_name']}")
    print(f"  - 플랫폼: {input_data['target_platform']}")
    print(f"  - 톤: {input_data['tone']}")

    try:
        result = agent.execute(input_data)

        print("\n📤 생성 결과:")
        print(f"  - 상태: {result.status}")

        if result.is_success():
            output = result.output
            print(f"\n  📱 SNS 포스트:")
            print(f"  {output.get('main_content', 'N/A')}")

            hashtags = output.get('hashtags', [])
            print(f"\n  #️⃣  해시태그 ({len(hashtags)}개):")
            print(f"  {' '.join(hashtags[:7])}")

            variations = output.get('variations', [])
            print(f"\n  📋 대안 버전 ({len(variations)}개):")
            for i, var in enumerate(variations[:2], 1):
                print(f"    {i}. {var[:80]}...")

            print("\n✅ Test 2 PASS: SNS 콘텐츠 생성 성공")
            return True
        else:
            print(f"\n❌ Test 2 FAIL: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Test 2 FAIL: 예외 발생 - {e}")
        return False

def test_ad_content_generation():
    """Test 3: 광고 문구 생성"""
    print_section("Test 3: 광고 문구 생성")

    agent = ContentAgent()

    input_data = {
        "product_name": "무선 목 마사지기",
        "product_category": "건강용품",
        "product_description": "집에서 즐기는 프리미엄 마사지",
        "key_features": ["15단계 강도 조절", "자동 온열 기능", "휴대 간편"],
        "price": 39900,
        "target_customer": "30-40대",
        "target_platform": "coupang",
        "content_type": "ad",
        "tone": "professional",
        "compliance_mode": True
    }

    print("\n📥 입력 데이터:")
    print(f"  - 상품명: {input_data['product_name']}")
    print(f"  - 플랫폼: {input_data['target_platform']}")
    print(f"  - 콘텐츠 유형: {input_data['content_type']}")

    try:
        result = agent.execute(input_data)

        print("\n📤 생성 결과:")
        print(f"  - 상태: {result.status}")

        if result.is_success():
            output = result.output

            ad_headlines = output.get('ad_headlines', [])
            print(f"\n  📢 광고 헤드라인 ({len(ad_headlines)}개):")
            for i, headline in enumerate(ad_headlines, 1):
                print(f"    {i}. {headline}")

            print(f"\n  📝 광고 본문:")
            print(f"  {output.get('main_content', 'N/A')[:150]}...")

            warnings = output.get('warnings', [])
            if warnings:
                print(f"\n  ⚠️  경고 ({len(warnings)}개):")
                for w in warnings:
                    print(f"    - {w}")

            print("\n✅ Test 3 PASS: 광고 문구 생성 성공")
            return True
        else:
            print(f"\n❌ Test 3 FAIL: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Test 3 FAIL: 예외 발생 - {e}")
        return False

def test_alt_text_generation():
    """Test 4: Alt text 생성 (룰 기반)"""
    print_section("Test 4: Alt Text 생성")

    agent = ContentAgent()

    input_data = {
        "product_name": "스테인리스 텀블러",
        "product_category": "주방용품",
        "key_features": ["진공 단열", "500ml", "스테인리스 스틸"],
        "price": 15900,
        "content_type": "alt_text",
        "compliance_mode": False  # Alt text는 간단하므로 컴플라이언스 체크 불필요
    }

    print("\n📥 입력 데이터:")
    print(f"  - 상품명: {input_data['product_name']}")
    print(f"  - 주요 특징: {', '.join(input_data['key_features'])}")

    try:
        result = agent.execute(input_data)

        print("\n📤 생성 결과:")
        print(f"  - 상태: {result.status}")

        if result.is_success():
            output = result.output

            print(f"\n  🖼️  메인 Alt Text:")
            print(f"  {output.get('main_content', 'N/A')}")

            alt_texts = output.get('image_alt_texts', [])
            print(f"\n  📋 추가 Alt Text ({len(alt_texts)}개):")
            for i, alt in enumerate(alt_texts, 1):
                print(f"    {i}. {alt}")

            print("\n✅ Test 4 PASS: Alt text 생성 성공")
            return True
        else:
            print(f"\n❌ Test 4 FAIL: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Test 4 FAIL: 예외 발생 - {e}")
        return False

def test_compliance_violation_detection():
    """Test 5: 컴플라이언스 위반 감지"""
    print_section("Test 5: 컴플라이언스 위반 감지")

    agent = ContentAgent()

    # 의도적으로 금지 표현 포함
    input_data = {
        "product_name": "세계 최고 건강 영양제",
        "product_category": "건강식품",
        "product_description": "질병 예방과 치료에 효과적인 건강 보조제",
        "key_features": ["100% 완벽한 치료", "의료용 성분", "약효 보증"],
        "price": 99900,
        "target_platform": "smartstore",
        "content_type": "product_page",
        "compliance_mode": True
    }

    print("\n📥 입력 데이터 (금지 표현 포함):")
    print(f"  - 상품명: {input_data['product_name']}")
    print(f"  - 설명: {input_data['product_description']}")
    print(f"  - 특징: {', '.join(input_data['key_features'])}")

    try:
        result = agent.execute(input_data)

        print("\n📤 생성 결과:")
        print(f"  - 상태: {result.status}")

        if result.is_success():
            output = result.output

            warnings = output.get('warnings', [])
            compliance_status = output.get('compliance_status', 'unknown')

            print(f"\n  ⚠️  경고 ({len(warnings)}개):")
            for w in warnings:
                print(f"    - {w}")

            print(f"\n  🚨 컴플라이언스 상태: {compliance_status}")

            # 검증: warning 또는 violation 상태여야 함
            if compliance_status in ["warning", "violation"] and len(warnings) > 0:
                print("\n✅ Test 5 PASS: 컴플라이언스 위반 정상 감지")
                return True
            else:
                print("\n❌ Test 5 FAIL: 컴플라이언스 위반 미감지")
                return False
        else:
            print(f"\n❌ Test 5 FAIL: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Test 5 FAIL: 예외 발생 - {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("\n" + "🤖" * 35)
    print("  Content Agent 통합 테스트")
    print("🤖" * 35)

    tests = [
        ("상품 상세페이지 생성", test_product_page_generation),
        ("SNS 콘텐츠 생성", test_sns_content_generation),
        ("광고 문구 생성", test_ad_content_generation),
        ("Alt Text 생성", test_alt_text_generation),
        ("컴플라이언스 위반 감지", test_compliance_violation_detection),
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
