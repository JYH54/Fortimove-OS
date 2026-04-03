"""
상품 콘텐츠 생성 서비스
- 상품 핵심 요약
- 상세페이지 원고
- 이미지 리디자인 기획
- 판매 전략
"""

import json
from typing import Dict, List, Optional
from datetime import datetime


class ComplianceFilter:
    """표현 안전성 필터"""

    # 카테고리별 금지 표현
    FORBIDDEN_PATTERNS = {
        "medical_claims": [
            "치료", "완치", "개선", "회복", "치유", "효과", "효능",
            "질병", "증상", "진단", "처방", "예방"
        ],
        "absolute_claims": [
            "100%", "완벽", "반드시", "절대", "무조건", "최고", "최상"
        ],
        "medical_device": [
            "진단", "치료기", "의료기기", "의료용", "치료용"
        ],
        "exaggeration": [
            "기적", "혁명", "놀라운", "엄청난", "대박"
        ]
    }

    # 안전한 대체 표현
    SAFE_ALTERNATIVES = {
        "치료": "케어",
        "개선": "도움",
        "효과": "서포트",
        "질병": "일상적 불편함",
        "완벽": "우수한",
        "반드시": "권장",
        "최고": "프리미엄"
    }

    @classmethod
    def filter_text(cls, text: str, category: str = "wellness") -> str:
        """텍스트에서 위험 표현 자동 완화"""
        if not text:
            return text

        filtered = text

        # 의료 효능 표현 완화
        for risky, safe in cls.SAFE_ALTERNATIVES.items():
            filtered = filtered.replace(risky, safe)

        return filtered

    @classmethod
    def check_compliance(cls, text: str) -> Dict[str, List[str]]:
        """컴플라이언스 위반 표현 감지"""
        violations = {}

        for category, patterns in cls.FORBIDDEN_PATTERNS.items():
            found = [p for p in patterns if p in text]
            if found:
                violations[category] = found

        return violations


class ProductContentGenerator:
    """상품 콘텐츠 생성 서비스"""

    def __init__(self):
        self.compliance_filter = ComplianceFilter()

    def generate_product_summary(self, review_data: dict) -> dict:
        """
        상품 핵심 요약 생성

        Args:
            review_data: {
                "source_title": str,
                "source_data_json": str (JSON),
                "category": str,
                "score": int,
                "decision": str
            }

        Returns:
            {
                "positioning_summary": str,
                "usp_points": List[str],
                "target_customer": str,
                "usage_scenarios": List[str],
                "differentiation_points": List[str],
                "search_intent_summary": str
            }
        """
        title = review_data.get("source_title", "")
        category = review_data.get("category", "wellness")

        # 소스 데이터 파싱
        source_data = {}
        if review_data.get("source_data_json"):
            try:
                source_data = json.loads(review_data["source_data_json"])
            except:
                pass

        # 기본 요약 생성 (룰 기반)
        summary = {
            "positioning_summary": self._generate_positioning(title, category),
            "usp_points": self._extract_usp_points(title, source_data),
            "target_customer": self._identify_target_customer(title, category),
            "usage_scenarios": self._generate_usage_scenarios(title, category),
            "differentiation_points": self._extract_differentiation(title, source_data),
            "search_intent_summary": self._summarize_search_intent(title, category)
        }

        return summary

    def generate_detail_content(self, review_data: dict, summary: dict) -> dict:
        """
        상세페이지 원고 생성

        Returns:
            {
                "main_title": str,
                "hook_copies": List[str],
                "key_benefits": List[str],
                "problem_scenarios": List[str],
                "solution_narrative": str,
                "target_users": str,
                "usage_guide": str,
                "cautions": str,
                "faq": List[{"q": str, "a": str}],
                "naver_body": str,
                "coupang_body": str,
                "short_ad_copies": List[str]
            }
        """
        title = review_data.get("source_title", "")
        category = review_data.get("category", "wellness")

        content = {
            "main_title": self._generate_main_title(title, summary),
            "hook_copies": self._generate_hook_copies(title, summary),
            "key_benefits": self._generate_key_benefits(title, summary),
            "problem_scenarios": self._generate_problem_scenarios(category, summary),
            "solution_narrative": self._generate_solution_narrative(title, summary),
            "target_users": summary.get("target_customer", ""),
            "usage_guide": self._generate_usage_guide(title, category),
            "cautions": self._generate_cautions(category),
            "faq": self._generate_faq(title, category),
            "naver_body": "",  # 추후 조합
            "coupang_body": "",  # 추후 조합
            "short_ad_copies": self._generate_short_ads(title, summary)
        }

        # 상세 원고 조합
        content["naver_body"] = self._assemble_naver_body(content)
        content["coupang_body"] = self._assemble_coupang_body(content)

        # 컴플라이언스 필터 적용
        content = self._apply_compliance_filter(content, category)

        return content

    def generate_image_design_guide(self, review_data: dict, summary: dict) -> dict:
        """
        이미지 리디자인 기획 생성

        Returns:
            {
                "main_thumbnail_copy": str,
                "sub_thumbnail_copies": List[str],
                "banner_copy": str,
                "section_copies": List[str],
                "layout_guide": str,
                "tone_manner": str,
                "forbidden_expressions": List[str],
                "generation_prompt": str,
                "edit_prompt": str
            }
        """
        title = review_data.get("source_title", "")
        category = review_data.get("category", "wellness")

        return {
            "main_thumbnail_copy": self._generate_main_thumbnail_copy(title, summary),
            "sub_thumbnail_copies": self._generate_sub_thumbnail_copies(summary),
            "banner_copy": self._generate_banner_copy(title, summary),
            "section_copies": self._generate_section_copies(summary),
            "layout_guide": self._generate_layout_guide(category),
            "tone_manner": self._generate_tone_manner(category),
            "forbidden_expressions": self._get_forbidden_expressions(category),
            "generation_prompt": self._generate_image_prompt(title, summary, category),
            "edit_prompt": self._generate_edit_prompt(title, category)
        }

    def generate_sales_strategy(self, review_data: dict, summary: dict) -> dict:
        """
        판매 전략 생성

        Returns:
            {
                "target_audience": str,
                "ad_points": List[str],
                "primary_keywords": List[str],
                "secondary_keywords": List[str],
                "hashtags": List[str],
                "review_points": List[str],
                "price_positioning": str,
                "sales_channels": List[str],
                "competitive_angles": List[str]
            }
        """
        title = review_data.get("source_title", "")
        category = review_data.get("category", "wellness")
        price = review_data.get("generated_price", 0)

        return {
            "target_audience": summary.get("target_customer", ""),
            "ad_points": self._generate_ad_points(title, summary),
            "primary_keywords": self._extract_primary_keywords(title, category),
            "secondary_keywords": self._extract_secondary_keywords(title, category),
            "hashtags": self._generate_hashtags(title, category),
            "review_points": self._generate_review_points(summary),
            "price_positioning": self._analyze_price_positioning(price, category),
            "sales_channels": ["네이버 스마트스토어", "쿠팡"],
            "competitive_angles": self._generate_competitive_angles(summary)
        }

    def assess_compliance_risks(self, review_data: dict, all_content: dict) -> dict:
        """
        컴플라이언스 리스크 평가

        Returns:
            {
                "ip_notes": str,
                "claim_notes": str,
                "compliance_notes": str,
                "final_decision": str,  # "PASS", "HOLD", "REJECT"
                "risk_level": str  # "LOW", "MEDIUM", "HIGH"
            }
        """
        title = review_data.get("source_title", "")
        category = review_data.get("category", "wellness")

        # 모든 생성된 텍스트 취합
        all_text = " ".join([
            str(v) for v in all_content.values() if isinstance(v, (str, list))
        ])

        violations = self.compliance_filter.check_compliance(all_text)

        return {
            "ip_notes": self._check_ip_risks(title),
            "claim_notes": self._analyze_claim_risks(violations),
            "compliance_notes": self._analyze_compliance_risks(category, violations),
            "final_decision": self._make_final_decision(violations),
            "risk_level": self._assess_risk_level(violations)
        }

    # === Private Helper Methods ===

    def _generate_positioning(self, title: str, category: str) -> str:
        """포지셔닝 문장 생성"""
        if "protein" in title.lower() or "프로틴" in title:
            return "고품질 단백질 보충을 원하는 운동 애호가를 위한 프리미엄 영양 보충제"
        elif "vitamin" in title.lower() or "비타민" in title:
            return "일상 건강 관리와 면역력 서포트를 위한 고함량 비타민 영양제"
        elif "omega" in title.lower() or "오메가" in title:
            return "심혈관 건강과 두뇌 활동 서포트를 위한 프리미엄 오메가3"
        else:
            return f"{category} 카테고리의 품질 중심 건강 서포트 제품"

    def _extract_usp_points(self, title: str, source_data: dict) -> List[str]:
        """USP 포인트 추출"""
        usp = []

        title_lower = title.lower()

        if "gold standard" in title_lower:
            usp.append("세계적으로 검증된 골드 스탠다드 품질")
        if "100%" in title:
            usp.append("순도 높은 원료 사용")
        if any(brand in title_lower for brand in ["now foods", "optimum nutrition", "california gold"]):
            usp.append("글로벌 프리미엄 브랜드")
        if source_data.get("weight_kg", 0) > 1.0:
            usp.append("대용량 가성비 구성")

        if not usp:
            usp.append("검증된 품질과 안전성")
            usp.append("실속있는 가격 구성")

        return usp[:5]

    def _identify_target_customer(self, title: str, category: str) -> str:
        """타깃 고객 식별"""
        if "protein" in title.lower():
            return "운동을 즐기는 20~40대 남녀, 근육 관리가 필요한 성인"
        elif "vitamin c" in title.lower():
            return "면역력 관리가 필요한 전 연령층, 특히 야외 활동이 많은 직장인"
        elif "omega" in title.lower():
            return "두뇌 활동이 많은 직장인, 심혈관 건강을 신경쓰는 중장년층"
        else:
            return f"{category} 제품에 관심있는 건강 의식 높은 소비자"

    def _generate_usage_scenarios(self, title: str, category: str) -> List[str]:
        """사용 상황 생성"""
        if "protein" in title.lower():
            return [
                "운동 후 단백질 보충이 필요할 때",
                "하루 단백질 섭취량이 부족할 때",
                "근력 운동 전후 영양 보충"
            ]
        elif "vitamin" in title.lower():
            return [
                "환절기 건강 관리가 필요할 때",
                "피로감이 느껴질 때",
                "면역력 서포트가 필요할 때"
            ]
        else:
            return [
                "일상적인 건강 서포트가 필요할 때",
                "영양 보충이 필요할 때"
            ]

    def _extract_differentiation(self, title: str, source_data: dict) -> List[str]:
        """차별화 포인트 추출"""
        diff = []

        if "gold" in title.lower():
            diff.append("프리미엄 원료와 제조 공정")
        if source_data.get("source_price_cny", 0) < 100:
            diff.append("합리적인 가격대")

        diff.append("해외 직구 프리미엄 브랜드")
        diff.append("검증된 품질 관리")

        return diff

    def _summarize_search_intent(self, title: str, category: str) -> str:
        """검색 의도 요약"""
        if "protein" in title.lower():
            return "운동 효율을 높이고 싶은 사람들이 검색"
        elif "vitamin" in title.lower():
            return "건강 관리와 면역력 서포트를 원하는 사람들이 검색"
        else:
            return f"{category} 관련 건강 서포트를 원하는 사람들이 검색"

    def _generate_main_title(self, title: str, summary: dict) -> str:
        """메인 제목 생성"""
        positioning = summary.get("positioning_summary", "")
        return f"{title}\n\n{positioning}"

    def _generate_hook_copies(self, title: str, summary: dict) -> List[str]:
        """훅 카피 3종 생성"""
        usp = summary.get("usp_points", [])

        hooks = []
        if len(usp) >= 1:
            hooks.append(f"✅ {usp[0]}")
        if len(usp) >= 2:
            hooks.append(f"💪 {usp[1]}")
        if len(usp) >= 3:
            hooks.append(f"🌟 {usp[2]}")

        while len(hooks) < 3:
            hooks.append("건강한 일상을 위한 선택")

        return hooks

    def _generate_key_benefits(self, title: str, summary: dict) -> List[str]:
        """핵심 장점 5개 생성"""
        benefits = summary.get("usp_points", []).copy()

        benefits.append("간편한 복용과 보관")
        benefits.append("안심할 수 있는 품질 관리")

        return benefits[:5]

    def _generate_problem_scenarios(self, category: str, summary: dict) -> List[str]:
        """문제 상황 3개 생성"""
        if "protein" in str(summary).lower():
            return [
                "운동은 열심히 하는데 근육이 잘 안 붙어요",
                "단백질 보충제 맛이 안 맞아서 오래 못 먹었어요",
                "좋은 제품은 너무 비싸고 저렴한 건 품질이 걱정돼요"
            ]
        elif "vitamin" in str(summary).lower():
            return [
                "환절기만 되면 컨디션이 떨어져요",
                "야외 활동이 많은데 피부 케어가 걱정돼요",
                "매일 챙겨먹기 번거로운 영양제는 싫어요"
            ]
        else:
            return [
                "건강 관리를 시작하고 싶은데 뭘 먹어야 할지 모르겠어요",
                "좋은 제품을 찾기가 어려워요",
                "꾸준히 섭취하기 쉬운 제품이 필요해요"
            ]

    def _generate_solution_narrative(self, title: str, summary: dict) -> str:
        """문제 해결 서사 생성"""
        return f"{title}는 이런 고민을 해결하기 위해 만들어졌습니다.\n\n" \
               f"검증된 원료와 프리미엄 제조 공정으로 만들어져, " \
               f"매일 안심하고 섭취할 수 있습니다.\n\n" \
               f"합리적인 가격에 대용량 구성으로 부담 없이 꾸준히 관리할 수 있습니다."

    def _generate_usage_guide(self, title: str, category: str) -> str:
        """사용 방법 생성"""
        return "1일 1~2회, 1회 1회 제공량을 물과 함께 섭취하세요.\n\n" \
               "운동 전후나 식사와 함께 섭취하시면 더욱 좋습니다.\n\n" \
               "개인의 건강 상태와 목적에 따라 섭취량을 조절할 수 있습니다."

    def _generate_cautions(self, category: str) -> str:
        """주의사항 생성"""
        return "• 본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다.\n" \
               "• 알레르기가 있는 분은 성분을 확인 후 섭취하세요.\n" \
               "• 임산부, 수유부, 질환이 있는 분은 전문가와 상담 후 섭취하세요.\n" \
               "• 어린이의 손이 닿지 않는 곳에 보관하세요.\n" \
               "• 직사광선을 피하고 서늘한 곳에 보관하세요."

    def _generate_faq(self, title: str, category: str) -> List[dict]:
        """FAQ 5개 생성"""
        return [
            {
                "q": "하루에 얼마나 섭취해야 하나요?",
                "a": "제품 라벨의 권장 섭취량을 확인하시고, 개인의 건강 상태에 따라 조절하세요."
            },
            {
                "q": "언제 먹는 것이 좋나요?",
                "a": "식사 후나 운동 전후가 권장되지만, 본인의 라이프스타일에 맞춰 섭취하시면 됩니다."
            },
            {
                "q": "다른 영양제와 함께 먹어도 되나요?",
                "a": "대부분의 경우 가능하지만, 특정 약물을 복용 중이라면 전문가와 상담을 권장합니다."
            },
            {
                "q": "얼마나 오래 먹어야 하나요?",
                "a": "건강 보조 목적이므로 꾸준히 섭취하는 것이 좋습니다."
            },
            {
                "q": "부작용은 없나요?",
                "a": "일반적으로 안전하지만, 과다 섭취는 피하시고 이상 반응 시 섭취를 중단하세요."
            }
        ]

    def _generate_short_ads(self, title: str, summary: dict) -> List[str]:
        """짧은 광고 문구 10개"""
        usp = summary.get("usp_points", [])

        ads = []
        for point in usp:
            ads.append(point)

        ads.extend([
            "매일 챙기는 건강 습관",
            "합리적인 가격, 확실한 품질",
            "검증된 글로벌 브랜드",
            "간편한 복용, 확실한 서포트",
            "건강한 하루를 시작하세요"
        ])

        return ads[:10]

    def _assemble_naver_body(self, content: dict) -> str:
        """네이버 상세 원고 조합"""
        body = f"# {content['main_title']}\n\n"

        for hook in content['hook_copies']:
            body += f"{hook}\n"
        body += "\n---\n\n"

        body += "## 이런 분들께 추천합니다\n\n"
        body += f"{content['target_users']}\n\n"

        body += "## 핵심 장점\n\n"
        for benefit in content['key_benefits']:
            body += f"✅ {benefit}\n"
        body += "\n"

        body += "## 이런 고민 있으신가요?\n\n"
        for problem in content['problem_scenarios']:
            body += f"• {problem}\n"
        body += "\n"

        body += f"## 해결 방법\n\n{content['solution_narrative']}\n\n"

        body += f"## 사용 방법\n\n{content['usage_guide']}\n\n"

        body += f"## 주의사항\n\n{content['cautions']}\n\n"

        body += "## 자주 묻는 질문\n\n"
        for faq in content['faq']:
            body += f"**Q. {faq['q']}**\n"
            body += f"A. {faq['a']}\n\n"

        return body

    def _assemble_coupang_body(self, content: dict) -> str:
        """쿠팡 상세 원고 조합"""
        # 쿠팡은 네이버보다 간결하게
        body = f"# {content['main_title']}\n\n"

        body += "## 핵심 장점\n\n"
        for benefit in content['key_benefits']:
            body += f"• {benefit}\n"
        body += "\n"

        body += f"## 사용 방법\n\n{content['usage_guide']}\n\n"

        body += f"## 주의사항\n\n{content['cautions']}\n"

        return body

    def _apply_compliance_filter(self, content: dict, category: str) -> dict:
        """컴플라이언스 필터 적용"""
        filtered = content.copy()

        # 텍스트 필드만 필터링
        for key, value in content.items():
            if isinstance(value, str):
                filtered[key] = self.compliance_filter.filter_text(value, category)
            elif isinstance(value, list) and all(isinstance(v, str) for v in value):
                filtered[key] = [self.compliance_filter.filter_text(v, category) for v in value]

        return filtered

    def _generate_main_thumbnail_copy(self, title: str, summary: dict) -> str:
        """메인 썸네일 카피"""
        usp = summary.get("usp_points", [])
        if usp:
            return usp[0]
        return "프리미엄 건강 서포트"

    def _generate_sub_thumbnail_copies(self, summary: dict) -> List[str]:
        """서브 썸네일 카피 3개"""
        usp = summary.get("usp_points", [])
        return usp[1:4] if len(usp) > 1 else ["품질 보증", "합리적 가격", "간편 복용"]

    def _generate_banner_copy(self, title: str, summary: dict) -> str:
        """배너 카피"""
        return summary.get("positioning_summary", "건강한 일상을 위한 선택")

    def _generate_section_copies(self, summary: dict) -> List[str]:
        """섹션별 카피"""
        return [
            "제품 특징",
            "사용 방법",
            "고객 혜택",
            "품질 보증",
            "구매 안내"
        ]

    def _generate_layout_guide(self, category: str) -> str:
        """레이아웃 가이드"""
        return "모바일 최적화 세로형 레이아웃\n" \
               "메인 이미지 → 핵심 장점 → 사용 방법 → 구매 정보 순서\n" \
               "각 섹션은 한 화면에 들어가도록 구성\n" \
               "텍스트는 최소화하고 아이콘과 이미지 중심"

    def _generate_tone_manner(self, category: str) -> str:
        """톤앤매너"""
        if category == "wellness":
            return "깔끔하고 신뢰감 있는 톤\n" \
                   "파스텔 또는 화이트 베이스\n" \
                   "과하지 않은 고급스러움\n" \
                   "건강과 웰빙을 연상시키는 색감"
        return "모던하고 깔끔한 디자인"

    def _get_forbidden_expressions(self, category: str) -> List[str]:
        """금지 표현 목록"""
        return [
            "치료",
            "완치",
            "질병 예방",
            "의학적 효과",
            "100% 효과",
            "반드시 개선"
        ]

    def _generate_image_prompt(self, title: str, summary: dict, category: str) -> str:
        """이미지 생성 프롬프트"""
        return f"Product photography of {title}\n" \
               f"Clean white background\n" \
               f"Professional lighting\n" \
               f"High resolution\n" \
               f"Focus on product packaging\n" \
               f"Wellness and health concept\n" \
               f"Soft shadows\n" \
               f"Minimal and modern style"

    def _generate_edit_prompt(self, title: str, category: str) -> str:
        """이미지 편집 프롬프트"""
        return "이미지 편집 가이드:\n" \
               "1. 배경을 깔끔한 화이트 또는 파스텔로 교체\n" \
               "2. 제품 중심으로 크롭\n" \
               "3. 밝기와 대비 조정으로 선명도 향상\n" \
               "4. 한글 카피 삽입 (간결하게)\n" \
               "5. 불필요한 요소 제거"

    def _generate_ad_points(self, title: str, summary: dict) -> List[str]:
        """광고 포인트"""
        return summary.get("usp_points", [])[:3]

    def _extract_primary_keywords(self, title: str, category: str) -> List[str]:
        """주요 키워드 추출"""
        keywords = []

        title_words = title.lower().split()

        if "protein" in title_words or "whey" in title_words:
            keywords.extend(["단백질보충제", "프로틴", "웨이프로틴"])
        if "vitamin" in title_words:
            keywords.extend(["비타민", "영양제", "건강기능식품"])
        if "omega" in title_words:
            keywords.extend(["오메가3", "EPA", "DHA"])

        if not keywords:
            keywords.extend([category, "건강식품", "영양보충"])

        return keywords[:5]

    def _extract_secondary_keywords(self, title: str, category: str) -> List[str]:
        """보조 키워드"""
        if "protein" in title.lower():
            return ["운동보충제", "근육", "헬스", "다이어트"]
        elif "vitamin" in title.lower():
            return ["면역력", "피로회복", "항산화", "건강관리"]
        else:
            return ["건강", "웰빙", "라이프스타일"]

    def _generate_hashtags(self, title: str, category: str) -> List[str]:
        """해시태그 생성"""
        primary = self._extract_primary_keywords(title, category)
        secondary = self._extract_secondary_keywords(title, category)

        tags = [f"#{kw}" for kw in (primary + secondary)[:10]]
        return tags

    def _generate_review_points(self, summary: dict) -> List[str]:
        """리뷰 유도 포인트"""
        return [
            "제품 품질에 대한 만족도",
            "복용 편의성",
            "가격 대비 만족도",
            "재구매 의향"
        ]

    def _analyze_price_positioning(self, price: float, category: str) -> str:
        """가격 포지셔닝 분석"""
        if price < 30000:
            return "가성비 중심 가격대 - 부담 없이 시작할 수 있는 합리적 가격"
        elif price < 60000:
            return "중가 품질 중심 - 품질과 가격의 균형"
        else:
            return "프리미엄 가격대 - 최고 품질 지향"

    def _generate_competitive_angles(self, summary: dict) -> List[str]:
        """경쟁 우위 포인트"""
        return summary.get("differentiation_points", [])

    def _check_ip_risks(self, title: str) -> str:
        """IP 리스크 체크"""
        branded = False
        for brand in ["Optimum Nutrition", "NOW Foods", "California Gold"]:
            if brand.lower() in title.lower():
                branded = True
                break

        if branded:
            return "정식 브랜드 제품으로 판단됨. 단, 정품 인증 및 정식 수입 경로 확인 필요."
        return "일반 제품으로 판단됨."

    def _analyze_claim_risks(self, violations: dict) -> str:
        """표현 리스크 분석"""
        if not violations:
            return "위험 표현 없음. 안전한 수준."

        notes = "다음 표현 주의 필요:\n"
        for category, words in violations.items():
            notes += f"- {category}: {', '.join(words)}\n"

        return notes

    def _analyze_compliance_risks(self, category: str, violations: dict) -> str:
        """컴플라이언스 리스크"""
        if category == "wellness":
            return "건강기능식품 카테고리 - 의료 효능 표현 금지, 식약처 고시 표현만 사용 권장"
        return "일반 제품 - 과장 표현 주의"

    def _make_final_decision(self, violations: dict) -> str:
        """최종 판정"""
        if not violations:
            return "PASS"

        if "medical_device" in violations:
            return "HOLD"

        if len(violations) > 2:
            return "HOLD"

        return "PASS"

    def _assess_risk_level(self, violations: dict) -> str:
        """리스크 레벨 평가"""
        if not violations:
            return "LOW"

        if "medical_device" in violations or "medical_claims" in violations:
            return "HIGH"

        if len(violations) >= 2:
            return "MEDIUM"

        return "LOW"
