"""
Detail Page Strategist (상세페이지 전략가)
===========================================

목적:
- 상품의 소싱 정보, 리스크 평가, 타겟 고객을 바탕으로
- 한국 이커머스(네이버/쿠팡) 최적화된 상세페이지 콘텐츠 생성
- 컴플라이언스를 준수하면서도 설득력 있는 스토리텔링 제공

핵심 원칙:
1. 의료 효능 표현 금지 (치료, 완치, 개선 → 케어, 도움, 서포트)
2. 절대적 표현 금지 (100%, 최고, 반드시 → 우수한, 권장)
3. 과장 표현 금지 (기적, 혁명 → 프리미엄, 검증된)
4. 문제-해결 구조의 스토리텔링
5. 구매 장벽 제거 중심 (FAQ, 사용법, 주의사항)
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from anthropic import Anthropic


class ComplianceGuard:
    """컴플라이언스 보호 장치"""

    # 절대 금지 표현 (자동 차단)
    FORBIDDEN_ABSOLUTE = [
        "치료", "완치", "진단", "처방", "의료기기", "치료기", "의약품",
        "질병", "증상 개선", "병 치료", "효과 보장"
    ]

    # 위험 표현 (경고 필요)
    RISKY_EXPRESSIONS = [
        "100%", "완벽", "최고", "반드시", "절대", "무조건",
        "기적", "혁명", "놀라운", "엄청난"
    ]

    # 안전한 대체 표현
    SAFE_ALTERNATIVES = {
        "치료": "케어",
        "개선": "도움",
        "효과": "서포트",
        "완치": "관리",
        "질병": "일상적 불편함",
        "증상": "상태",
        "완벽": "우수한",
        "반드시": "권장",
        "최고": "프리미엄",
        "100%": "높은 수준의",
        "기적": "주목받는",
        "혁명": "혁신적인"
    }

    @classmethod
    def scan_and_replace(cls, text: str) -> tuple[str, List[str]]:
        """
        텍스트를 스캔하여 금지 표현을 안전한 표현으로 자동 치환

        Returns:
            (치환된 텍스트, 발견된 위험 표현 리스트)
        """
        if not text:
            return text, []

        warnings = []
        cleaned = text

        # 절대 금지 표현 치환
        for forbidden in cls.FORBIDDEN_ABSOLUTE:
            if forbidden in cleaned:
                warnings.append(f"금지: {forbidden}")
                safe = cls.SAFE_ALTERNATIVES.get(forbidden, "")
                if safe:
                    cleaned = cleaned.replace(forbidden, safe)

        # 위험 표현 탐지 (치환하되 경고)
        for risky in cls.RISKY_EXPRESSIONS:
            if risky in cleaned:
                warnings.append(f"위험: {risky}")
                safe = cls.SAFE_ALTERNATIVES.get(risky, risky)
                cleaned = cleaned.replace(risky, safe)

        return cleaned, warnings


class DetailPageStrategist:
    """
    상세페이지 전략가 (LLM 기반)

    책임:
    - 상품의 USP를 극대화하는 Hook Copy 생성
    - 문제-해결 구조의 Benefit 서술
    - 구매 결정을 돕는 FAQ 생성
    - 네이버/쿠팡 채널별 최적화
    """

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        self.compliance_guard = ComplianceGuard()

    def generate_detail_page_content(
        self,
        product_summary: Dict,
        source_data: Dict,
        category: str = "wellness"
    ) -> Dict:
        """
        상세페이지 전체 콘텐츠 생성

        Args:
            product_summary: {
                "positioning_summary": str,
                "usp_points": List[str],
                "target_customer": str,
                "usage_scenarios": List[str],
                "differentiation_points": List[str]
            }
            source_data: {
                "source_title": str,
                "source_url": str,
                "source_price_cny": float,
                "category": str,
                "weight_kg": float
            }
            category: 카테고리 (wellness, fashion, electronics 등)

        Returns:
            {
                "main_title": str,
                "hook_copies": List[str],  # 3-5개의 후크 카피
                "key_benefits": List[str],  # 5-7개의 핵심 혜택
                "problem_scenarios": List[str],  # 3개의 문제 시나리오
                "solution_narrative": str,  # 해결 서사 (200-300자)
                "target_users": str,  # 타겟 유저 설명
                "usage_guide": str,  # 사용 가이드
                "cautions": str,  # 주의사항
                "faq": List[{"q": str, "a": str}],  # 5-7개 FAQ
                "naver_body": str,  # 네이버용 전체 본문
                "coupang_body": str,  # 쿠팡용 전체 본문
                "short_ad_copies": List[str],  # 짧은 광고 문구 10개
                "compliance_warnings": List[str]  # 컴플라이언스 경고
            }
        """

        # 1. Hook Copies 생성 (가장 중요)
        hook_copies = self._generate_hook_copies(product_summary, source_data, category)

        # 2. Key Benefits 생성
        key_benefits = self._generate_key_benefits(product_summary, source_data, category)

        # 3. Problem-Solution 구조 생성
        problem_scenarios = self._generate_problem_scenarios(product_summary, category)
        solution_narrative = self._generate_solution_narrative(
            product_summary, source_data, problem_scenarios, category
        )

        # 4. 실용 정보 생성
        usage_guide = self._generate_usage_guide(source_data, category)
        cautions = self._generate_cautions(source_data, category)
        faq = self._generate_faq(product_summary, source_data, category)

        # 5. 짧은 광고 문구 생성
        short_ad_copies = self._generate_short_ad_copies(product_summary, source_data)

        # 6. 채널별 본문 조합
        naver_body = self._assemble_naver_body(
            hook_copies, key_benefits, solution_narrative,
            usage_guide, cautions
        )
        coupang_body = self._assemble_coupang_body(
            hook_copies, key_benefits, solution_narrative,
            usage_guide
        )

        # 7. 컴플라이언스 스캔 및 치환
        all_warnings = []

        naver_body, warnings1 = self.compliance_guard.scan_and_replace(naver_body)
        all_warnings.extend(warnings1)

        coupang_body, warnings2 = self.compliance_guard.scan_and_replace(coupang_body)
        all_warnings.extend(warnings2)

        # Main title 생성
        main_title = self._generate_main_title(product_summary, source_data)

        return {
            "main_title": main_title,
            "hook_copies": hook_copies,
            "key_benefits": key_benefits,
            "problem_scenarios": problem_scenarios,
            "solution_narrative": solution_narrative,
            "target_users": product_summary.get("target_customer", ""),
            "usage_guide": usage_guide,
            "cautions": cautions,
            "faq": faq,
            "naver_body": naver_body,
            "coupang_body": coupang_body,
            "short_ad_copies": short_ad_copies,
            "compliance_warnings": list(set(all_warnings))  # 중복 제거
        }

    def _generate_hook_copies(
        self,
        product_summary: Dict,
        source_data: Dict,
        category: str
    ) -> List[str]:
        """
        Hook Copy 생성 (3-5개)
        - 첫 3초 내 시선을 붙잡는 카피
        - 문제 인식 → 호기심 유발
        """

        prompt = f"""당신은 한국 이커머스 상세페이지 카피라이터입니다.

상품 정보:
- 제목: {source_data.get('source_title', '')}
- 포지셔닝: {product_summary.get('positioning_summary', '')}
- USP: {', '.join(product_summary.get('usp_points', []))}
- 타겟: {product_summary.get('target_customer', '')}
- 카테고리: {category}

임무: 상세페이지 상단에 배치할 **Hook Copy 3개**를 생성하세요.

요구사항:
1. 각 카피는 15-25자 이내
2. 타겟 고객의 문제를 직관적으로 건드릴 것
3. 호기심을 유발하되, 과장하지 말 것
4. 의료 효능 표현 금지 (치료, 완치, 개선 등)
5. 절대적 표현 금지 (100%, 최고, 반드시 등)

예시 (비타민C의 경우):
- "매일 아침, 활력이 부족하다면?"
- "면역력 서포트, 이제는 습관으로"
- "고함량 비타민C로 일상 건강 관리"

JSON 형식으로만 응답하세요:
{{"hook_copies": ["카피1", "카피2", "카피3"]}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
            return result.get("hook_copies", [])[:5]
        except:
            # Fallback: 룰 기반 생성
            return self._fallback_hook_copies(product_summary, source_data)

    def _generate_key_benefits(
        self,
        product_summary: Dict,
        source_data: Dict,
        category: str
    ) -> List[str]:
        """
        핵심 혜택 생성 (5-7개)
        - 구체적이고 실용적인 혜택
        """

        prompt = f"""당신은 한국 이커머스 상세페이지 카피라이터입니다.

상품 정보:
- 제목: {source_data.get('source_title', '')}
- 포지셔닝: {product_summary.get('positioning_summary', '')}
- USP: {', '.join(product_summary.get('usp_points', []))}
- 차별화 포인트: {', '.join(product_summary.get('differentiation_points', []))}

임무: 고객이 얻을 수 있는 **핵심 혜택 5개**를 생성하세요.

요구사항:
1. 각 혜택은 "~할 수 있습니다" 형태로 서술
2. 구체적이고 실용적인 혜택일 것
3. 의료 효능 표현 금지 (치료, 완치 등 → 케어, 도움, 서포트)
4. 과장 금지 (기적, 혁명 등 → 프리미엄, 검증된)

예시 (프로틴의 경우):
- "운동 후 근육 회복을 효과적으로 서포트할 수 있습니다"
- "고품질 단백질로 일일 영양 균형을 맞출 수 있습니다"
- "다양한 맛으로 질리지 않고 꾸준히 섭취할 수 있습니다"

JSON 형식으로만 응답하세요:
{{"key_benefits": ["혜택1", "혜택2", "혜택3", "혜택4", "혜택5"]}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
            return result.get("key_benefits", [])[:7]
        except:
            return self._fallback_key_benefits(product_summary)

    def _generate_problem_scenarios(
        self,
        product_summary: Dict,
        category: str
    ) -> List[str]:
        """
        문제 시나리오 생성 (3개)
        - 타겟 고객이 공감할 수 있는 문제 상황
        """

        target_customer = product_summary.get("target_customer", "")

        prompt = f"""당신은 한국 이커머스 상세페이지 카피라이터입니다.

타겟 고객: {target_customer}
카테고리: {category}

임무: 타겟 고객이 공감할 수 있는 **문제 시나리오 3개**를 생성하세요.

요구사항:
1. 각 시나리오는 20-30자 이내
2. "이런 분들께 추천합니다" 형태
3. 구체적인 상황 서술
4. 부정적이지 않되, 공감을 이끌어낼 것

예시 (비타민의 경우):
- "아침에 일어나도 개운하지 않은 분"
- "면역력 관리가 필요한 직장인"
- "야외 활동이 많은 활동적인 분"

JSON 형식으로만 응답하세요:
{{"problem_scenarios": ["시나리오1", "시나리오2", "시나리오3"]}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
            return result.get("problem_scenarios", [])[:3]
        except:
            return [
                "건강 관리가 필요한 분",
                "일상 활력이 부족한 분",
                "프리미엄 품질을 찾는 분"
            ]

    def _generate_solution_narrative(
        self,
        product_summary: Dict,
        source_data: Dict,
        problem_scenarios: List[str],
        category: str
    ) -> str:
        """
        해결 서사 생성 (200-300자)
        - 문제 → 솔루션 → 결과의 스토리텔링
        """

        prompt = f"""당신은 한국 이커머스 상세페이지 카피라이터입니다.

상품 정보:
- 제목: {source_data.get('source_title', '')}
- 포지셔닝: {product_summary.get('positioning_summary', '')}
- 문제 시나리오: {', '.join(problem_scenarios)}

임무: **문제-솔루션-결과** 구조의 스토리텔링을 200-300자로 작성하세요.

요구사항:
1. 문제 공감 → 제품 소개 → 기대 결과 순서
2. 자연스럽고 설득력 있는 흐름
3. 의료 효능 표현 금지 (치료, 완치 등)
4. 과장 금지 (기적, 혁명 등)
5. "~할 수 있습니다" 형태로 마무리

예시:
"바쁜 일상 속에서 건강 관리는 늘 뒷전이 되기 마련입니다. 하지만 작은 습관 하나로 달라질 수 있습니다. [제품명]은 검증된 품질과 편리한 섭취 방식으로, 매일 꾸준히 건강을 서포트합니다. 일상에 활력을 더하고 싶다면, 지금 시작해보세요."

JSON 형식으로만 응답하세요:
{{"solution_narrative": "서사 내용"}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1200,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
            return result.get("solution_narrative", "")
        except:
            return f"{product_summary.get('positioning_summary', '')} 검증된 품질로 일상을 서포트합니다."

    def _generate_usage_guide(self, source_data: Dict, category: str) -> str:
        """사용 가이드 생성"""

        if category == "wellness":
            return """**사용 방법**
1. 1일 1회, 식후에 물과 함께 섭취하세요
2. 권장 섭취량을 지켜주세요
3. 개봉 후 밀봉 보관하세요

**보관 방법**
- 직사광선을 피하고 서늘한 곳에 보관
- 어린이 손이 닿지 않는 곳에 보관"""
        else:
            return """**사용 방법**
제품 특성에 맞게 사용하세요. 자세한 내용은 제품 라벨을 참고하세요."""

    def _generate_cautions(self, source_data: Dict, category: str) -> str:
        """주의사항 생성"""

        if category == "wellness":
            return """**주의사항**
- 본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다
- 특정 체질이나 알레르기가 있는 경우 원료를 확인 후 섭취하세요
- 임산부, 수유부는 전문가와 상담 후 섭취하세요
- 이상 반응 발생 시 즉시 섭취를 중단하고 전문가와 상담하세요"""
        else:
            return """**주의사항**
- 제품 사용 전 주의사항을 반드시 확인하세요
- 본 제품은 용도에 맞게 사용하세요"""

    def _generate_faq(
        self,
        product_summary: Dict,
        source_data: Dict,
        category: str
    ) -> List[Dict[str, str]]:
        """FAQ 생성 (5-7개)"""

        prompt = f"""당신은 한국 이커머스 상세페이지 카피라이터입니다.

상품 정보:
- 제목: {source_data.get('source_title', '')}
- 포지셔닝: {product_summary.get('positioning_summary', '')}
- 카테고리: {category}

임무: 고객이 자주 묻는 질문 **FAQ 5개**를 생성하세요.

요구사항:
1. 구매 장벽을 제거하는 실용적인 질문
2. 질문: 10-20자, 답변: 50-100자
3. 의료 효능 언급 금지
4. "배송", "환불", "성분", "사용법", "보관" 등 실용 주제

예시:
Q: 하루에 몇 번 섭취하나요?
A: 1일 1회, 식후에 물과 함께 섭취하시면 됩니다. 권장 섭취량을 지켜주세요.

JSON 형식으로만 응답하세요:
{{"faq": [
  {{"q": "질문1", "a": "답변1"}},
  {{"q": "질문2", "a": "답변2"}},
  {{"q": "질문3", "a": "답변3"}},
  {{"q": "질문4", "a": "답변4"}},
  {{"q": "질문5", "a": "답변5"}}
]}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
            return result.get("faq", [])[:7]
        except:
            return self._fallback_faq(category)

    def _generate_short_ad_copies(
        self,
        product_summary: Dict,
        source_data: Dict
    ) -> List[str]:
        """짧은 광고 문구 생성 (10개)"""

        prompt = f"""당신은 한국 이커머스 상세페이지 카피라이터입니다.

상품 정보:
- 제목: {source_data.get('source_title', '')}
- USP: {', '.join(product_summary.get('usp_points', []))}

임무: 이미지 썸네일이나 배너에 사용할 **짧은 광고 문구 10개**를 생성하세요.

요구사항:
1. 각 문구는 5-12자 이내
2. 임팩트 있고 기억에 남을 것
3. 의료 효능 표현 금지
4. 과장 금지

예시:
- "프리미엄 품질"
- "매일 건강 습관"
- "검증된 브랜드"
- "간편한 섭취"

JSON 형식으로만 응답하세요:
{{"short_ad_copies": ["문구1", "문구2", ..., "문구10"]}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = json.loads(response.content[0].text)
            return result.get("short_ad_copies", [])[:10]
        except:
            return [
                "프리미엄 품질", "매일 건강", "검증된 브랜드",
                "간편한 섭취", "가성비 우수", "안전한 선택",
                "일상 활력", "꾸준한 관리", "신뢰할 수 있는", "추천 제품"
            ]

    def _generate_main_title(
        self,
        product_summary: Dict,
        source_data: Dict
    ) -> str:
        """메인 타이틀 생성"""

        source_title = source_data.get("source_title", "")
        positioning = product_summary.get("positioning_summary", "")

        # 간결하고 명확하게
        if len(source_title) <= 50:
            return source_title
        else:
            # 너무 길면 포지셔닝 기반으로 축약
            return positioning[:50]

    def _assemble_naver_body(
        self,
        hook_copies: List[str],
        key_benefits: List[str],
        solution_narrative: str,
        usage_guide: str,
        cautions: str
    ) -> str:
        """네이버용 본문 조합"""

        body = f"""
{chr(10).join(hook_copies)}

━━━━━━━━━━━━━━━━━━━━━━

💎 이런 점이 좋습니다

{chr(10).join([f"✓ {b}" for b in key_benefits])}

━━━━━━━━━━━━━━━━━━━━━━

📖 제품 소개

{solution_narrative}

━━━━━━━━━━━━━━━━━━━━━━

{usage_guide}

━━━━━━━━━━━━━━━━━━━━━━

{cautions}
"""
        return body.strip()

    def _assemble_coupang_body(
        self,
        hook_copies: List[str],
        key_benefits: List[str],
        solution_narrative: str,
        usage_guide: str
    ) -> str:
        """쿠팡용 본문 조합 (더 간결하게)"""

        body = f"""
{hook_copies[0] if hook_copies else ''}

{chr(10).join([f"• {b}" for b in key_benefits[:5]])}

{solution_narrative}

{usage_guide}
"""
        return body.strip()

    # === Fallback Methods (LLM 실패 시) ===

    def _fallback_hook_copies(self, product_summary: Dict, source_data: Dict) -> List[str]:
        """Fallback: 룰 기반 Hook Copy"""
        return [
            "프리미엄 품질로 일상을 케어하세요",
            "검증된 브랜드의 신뢰할 수 있는 선택",
            "매일 꾸준히, 건강한 습관으로"
        ]

    def _fallback_key_benefits(self, product_summary: Dict) -> List[str]:
        """Fallback: 룰 기반 Key Benefits"""
        return [
            "고품질 원료를 사용하여 안심하고 섭취할 수 있습니다",
            "편리한 형태로 일상에서 간편하게 관리할 수 있습니다",
            "검증된 브랜드로 신뢰할 수 있습니다",
            "꾸준한 섭취로 일상 건강을 서포트할 수 있습니다",
            "합리적인 가격으로 부담 없이 시작할 수 있습니다"
        ]

    def _fallback_faq(self, category: str) -> List[Dict[str, str]]:
        """Fallback: 기본 FAQ"""
        if category == "wellness":
            return [
                {"q": "하루 섭취량은 얼마인가요?", "a": "1일 1회 권장량을 섭취하시면 됩니다. 제품 라벨을 참고하세요."},
                {"q": "언제 섭취하는 것이 좋나요?", "a": "식후에 물과 함께 섭취하시는 것을 권장합니다."},
                {"q": "보관 방법은 어떻게 되나요?", "a": "직사광선을 피하고 서늘한 곳에 밀봉 보관하세요."},
                {"q": "배송은 얼마나 걸리나요?", "a": "주문 후 1-3일 이내 출고되며, 지역에 따라 2-5일 소요됩니다."},
                {"q": "환불 정책은 어떻게 되나요?", "a": "미개봉 제품에 한해 수령 후 7일 이내 반품 가능합니다."}
            ]
        else:
            return [
                {"q": "배송은 얼마나 걸리나요?", "a": "주문 후 1-3일 이내 출고되며, 지역에 따라 2-5일 소요됩니다."},
                {"q": "환불 정책은 어떻게 되나요?", "a": "미개봉 제품에 한해 수령 후 7일 이내 반품 가능합니다."},
                {"q": "제품 사용 방법은?", "a": "제품 라벨의 사용 방법을 참고하세요."}
            ]


# 모듈 테스트용 메인 블록
if __name__ == "__main__":
    # 테스트 데이터
    test_product_summary = {
        "positioning_summary": "고품질 단백질 보충을 원하는 운동 애호가를 위한 프리미엄 영양 보충제",
        "usp_points": [
            "세계적으로 검증된 골드 스탠다드 품질",
            "순도 높은 원료 사용",
            "글로벌 프리미엄 브랜드",
            "대용량 가성비 구성"
        ],
        "target_customer": "근력 운동을 하는 20-40대 남녀, 단백질 보충이 필요한 건강 관리자",
        "usage_scenarios": [
            "운동 후 근육 회복",
            "아침 식사 대용",
            "간식 대체"
        ],
        "differentiation_points": [
            "Optimum Nutrition 브랜드",
            "100% Whey Protein",
            "5lbs 대용량"
        ]
    }

    test_source_data = {
        "source_title": "Optimum Nutrition, Gold Standard 100% Whey Protein, Double Rich Chocolate, 5 lbs",
        "source_url": "https://www.iherb.com/pr/optimum-nutrition-gold-standard-100-whey-protein",
        "source_price_cny": 380.0,
        "category": "wellness",
        "weight_kg": 2.27
    }

    try:
        strategist = DetailPageStrategist()
        result = strategist.generate_detail_page_content(
            test_product_summary,
            test_source_data,
            "wellness"
        )

        print("✅ Detail Page Strategist 테스트 성공!")
        print(f"\n메인 타이틀: {result['main_title']}")
        print(f"\nHook Copies ({len(result['hook_copies'])}개):")
        for i, hook in enumerate(result['hook_copies'], 1):
            print(f"  {i}. {hook}")
        print(f"\n컴플라이언스 경고: {len(result['compliance_warnings'])}건")
        if result['compliance_warnings']:
            for warning in result['compliance_warnings']:
                print(f"  ⚠️ {warning}")

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
