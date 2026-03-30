"""
PM 에이전트 테스트 스크립트
"""
import os
import json
from pm_agent import PMAgent

# 테스트 케이스
test_cases = [
    {
        "name": "신규 소싱 + 마진 검수",
        "request": "타오바오 링크: https://item.taobao.com/item.htm?id=123456\n이 상품 소싱 가능한지 확인해줘. 원가는 30위안이야."
    },
    {
        "name": "고객 클레임 (긴급)",
        "request": "고객이 배송 지연 클레임 넣었어. 벤더가 연락 안 받고 있어."
    },
    {
        "name": "복합 작업 (이미지 + 등록 + 콘텐츠)",
        "request": "타오바오 타월 상품 이미지 5장 현지화하고, SEO 상품명도 만들고, 블로그 홍보 글도 써줘."
    },
    {
        "name": "마진 재검수",
        "request": "기존 상품 마진 재계산해줘. 배송비가 올랐어."
    }
]

def run_tests():
    """테스트 실행"""
    # API 키 확인
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   export ANTHROPIC_API_KEY='your-key'")
        return

    pm = PMAgent()

    print("🚀 PM 에이전트 테스트 시작\n")
    print("=" * 80)

    for i, test in enumerate(test_cases, 1):
        print(f"\n\n## 테스트 {i}: {test['name']}")
        print(f"\n**입력**:")
        print(f"```\n{test['request']}\n```")

        try:
            # 워크플로우 실행
            result = pm.execute_workflow(test['request'], auto_execute=False)

            # 마크다운 출력
            print(f"\n{pm.format_output(result)}")

            # JSON 출력 (옵션)
            if os.getenv("VERBOSE"):
                print(f"\n<details>")
                print(f"<summary>원본 JSON</summary>\n")
                print(f"```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```")
                print(f"</details>")

            print("\n" + "=" * 80)

        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            print("=" * 80)
            continue

    print("\n\n✅ 모든 테스트 완료")

if __name__ == "__main__":
    run_tests()
