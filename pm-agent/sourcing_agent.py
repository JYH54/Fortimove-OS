"""
소싱/상품 발굴 에이전트 (Sourcing Agent)
- 타오바오/1688 URL 분석
- 리스크 1차 필터링 (지재권/통관/의료기기)
- 벤더 질문 생성 (한국어/중국어)
- 상품 분류 (테스트/반복/PB)
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel, Field
from anthropic import Anthropic

from agent_framework import BaseAgent, register_agent
from korean_law_helper import get_korean_law_helper

logger = logging.getLogger(__name__)

# ============================================================
# Schema Definitions
# ============================================================

class SourcingInputSchema(BaseModel):
    source_url: str                              # 타오바오/1688 URL (필수)
    keywords: Optional[List[str]] = Field(default_factory=list)     # 검색 키워드
    vendor_chat: Optional[str] = None            # 벤더 채팅 내역
    target_category: Optional[str] = None        # 타겟 카테고리
    source_title: Optional[str] = None           # 상품 제목 (URL 파싱 대신 직접 제공 가능)
    source_description: Optional[str] = None     # 상품 설명
    source_price_cny: Optional[float] = None     # 매입가 (위안)
    market: str = "korea"                        # 타겟 시장 (기본값: korea)

class SourcingOutputSchema(BaseModel):
    product_classification: str                  # 테스트/반복/PB
    vendor_questions_ko: List[str]               # 한국어 질문
    vendor_questions_zh: List[str]               # 중국어 질문
    sourcing_decision: str                       # 통과/보류/제외
    risk_flags: List[str]                        # 리스크 플래그
    risk_details: Dict[str, Any]                 # 리스크 상세 정보
    next_step_recommendation: str                # 다음 단계 권고
    extracted_info: Dict[str, Any]               # URL에서 추출한 정보
    legal_check: Optional[Dict[str, Any]] = None # 법령 검증 결과 (Korean Law MCP)

# ============================================================
# Sourcing Agent Implementation
# ============================================================

@register_agent("sourcing")
class SourcingAgent(BaseAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return SourcingInputSchema

    @property
    def output_schema(self) -> Type[BaseModel]:
        return SourcingOutputSchema

    def __init__(self):
        super().__init__("sourcing")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Sourcing Agent initiated without ANTHROPIC_API_KEY")

        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

        # ⚠️ 2026-04-01 추가: Korean Law MCP 헬퍼 초기화
        self.korean_law = get_korean_law_helper()
        if self.korean_law.available:
            logger.info("Korean Law MCP 연동 완료")
        else:
            logger.warning("Korean Law MCP 사용 불가 (키워드 필터만 사용)")

        # ========================================================
        # Compliance 필수 체크: 2026년 8월 관세법 개정 + 4월 KC 인증 규제
        # ========================================================
        self.risk_keywords = {
            "지재권": [
                "나이키", "아디다스", "샤넬", "구찌", "루이비통", "애플", "삼성",
                "아이폰", "갤럭시", "nike", "adidas", "chanel", "gucci", "apple",
                "디즈니", "마블", "pokemon", "포켓몬", "짱구", "캐릭터"
            ],
            # ⚠️ 2026-04-01 업데이트: 의약품 별도 카테고리 분리 (약사법 준수)
            "의약품": [
                "의약품", "다이어트약", "피임약", "슬리밍", "한약재", "당귀", "인삼",
                "수면제", "진통제", "식욕억제", "지방분해", "체중감량", "살빠지는",
                "약", "medicine", "drug", "diet pill", "sleeping pill", "painkiller",
                "처방전", "복용", "투약", "약효", "부작용"
            ],
            "통관": [
                "건강기능식품", "보조제", "영양제", "비타민",
                "supplement", "vitamin", "프로바이오틱스", "오메가3",
                "콜라겐", "단백질", "프로틴"
            ],
            # ⚠️ 2026-04-01 업데이트: 의료기기 키워드 대폭 강화 (의료기기법 준수)
            "의료기기": [
                "치료", "완치", "재생", "혈압", "혈당", "진단", "의료용",
                "medical", "therapy", "cure", "측정기", "모니터링", "검사",
                "레이저", "초음파", "전기자극",
                # 2026-04-01 추가: 전기/물리 치료기기
                "전기 마사지", "저주파 치료", "고주파 치료", "적외선 램프",
                "혈액순환 개선", "체지방 측정", "근육 자극", "물리치료",
                "EMS", "TENS", "저주파", "고주파", "혈행개선",
                # 2026-04-01 추가: 미용 의료기기
                "피부 재생", "주름 개선 기기", "리프팅 기기", "셀룰라이트",
                "RF", "radio frequency", "갈바닉", "초음파 리프팅",
                # 2026-04-01 추가: 가정용 의료기기
                "체온계", "혈압계", "혈당측정기", "산소포화도", "심박수",
                "nebulizer", "흡입기", "적외선 체온계"
            ],
            # 2026년 8월 관세법 개정: 간이통관 면세 한도 하향 (리스크 품목)
            "고가품_관세주의": [
                "명품", "시계", "가방", "지갑", "귀금속", "보석", "다이아몬드",
                "gold", "luxury", "premium brand"
            ],
            # 2026년 4월 KC 인증 강화: 전자제품 필수 인증
            "KC인증필수": [
                "전자제품", "배터리", "충전기", "어댑터", "전원", "무선",
                "bluetooth", "usb", "전기", "전압", "리튬", "lithium",
                "이어폰", "헤드폰", "스피커", "led", "램프", "조명"
            ],
            # 식품 안전 강화 (수입식품 안전관리)
            "식품안전": [
                "식품", "음료", "간식", "과자", "food", "snack", "drink",
                "차", "tea", "커피", "coffee", "초콜릿", "chocolate"
            ],
            # 화장품법 강화 (기능성 화장품)
            "화장품규제": [
                "미백", "주름개선", "자외선차단", "whitening", "wrinkle", "sunscreen",
                "기능성", "안티에이징", "anti-aging", "피부재생"
            ]
        }

        # 8월 관세법 개정: 간이통관 면세 한도 USD 150 → USD 100 하향
        self.customs_threshold_usd = 100  # 2026년 8월 시행

        # KC 인증 필수 품목 자동 탐지 로직 활성화
        self.kc_cert_required = True  # 2026년 4월 시행

    def _do_execute(self, input_model: SourcingInputSchema) -> Dict[str, Any]:
        """소싱 에이전트 메인 로직 — 멀티국가 지원"""
        from country_config import get_country

        # 1. URL/국가 파싱
        extracted_info = self._extract_url_info(input_model.source_url)
        country_code = extracted_info.get("country", "CN")
        country = get_country(country_code)

        # 국가별 특이 리스크 추가
        if country:
            extracted_info["country_name"] = country.name_ko
            extracted_info["origin_trust_label"] = country.origin_trust_label

        # 2. 리스크 1차 필터링 (Rule-based)
        risk_flags, risk_details = self._check_risk_keywords(
            input_model.source_title or extracted_info.get("title", ""),
            input_model.source_description or ""
        )

        # 국가별 추가 리스크 체크
        if country:
            for cert in country.required_certs:
                cert_key = cert.split("(")[0].strip()
                # KC인증 등은 이미 키워드에 포함, 중복 방지
                if cert_key not in str(risk_flags):
                    pass  # 국가별 인증은 risk_notes에서 안내

        # 3. LLM 기반 상세 분석 (국가 맥락 포함)
        llm_analysis = self._analyze_with_llm(input_model, risk_flags, country_code)

        # 4. 벤더 질문 생성 (국가별 언어)
        vendor_questions_ko, vendor_questions_local = self._generate_vendor_questions(
            input_model, llm_analysis, country_code
        )

        # 5. Korean Law MCP 법령 검증 (의료기기/의약품 리스크만)
        legal_check = None
        if self.korean_law.available and ("의료기기" in risk_flags or "의약품" in risk_flags):
            legal_check = self._check_legal_compliance(
                input_model.source_title or "",
                input_model.source_description or "",
                risk_flags
            )

        # 6. 최종 판정
        sourcing_decision = self._make_decision(risk_flags, llm_analysis)

        # 7. 상품 분류
        product_classification = llm_analysis.get("product_classification", "테스트")

        # 8. 다음 단계 권고
        next_step = self._recommend_next_step(sourcing_decision, risk_flags)

        # 국가별 특이사항 추가
        country_notes = country.risk_notes if country else []

        return {
            "product_classification": product_classification,
            "vendor_questions_ko": vendor_questions_ko,
            "vendor_questions_local": vendor_questions_local,
            "vendor_questions_zh": vendor_questions_local if country_code == "CN" else [],
            "sourcing_decision": sourcing_decision,
            "risk_flags": risk_flags,
            "risk_details": risk_details,
            "next_step_recommendation": next_step,
            "extracted_info": extracted_info,
            "legal_check": legal_check,
            "source_country": country_code,
            "country_notes": country_notes,
        }

    def _extract_url_info(self, url: str) -> Dict[str, Any]:
        """URL에서 기본 정보 추출 — 멀티국가 플랫폼 지원"""
        from country_config import detect_country_from_url

        info = {
            "url": url,
            "platform": "unknown",
            "country": "CN",
            "item_id": None,
            "title": None
        }

        if not url:
            return info

        url_lower = url.lower()
        info["country"] = detect_country_from_url(url)

        # 중국
        if "taobao.com" in url_lower:
            info["platform"] = "taobao"
        elif "1688.com" in url_lower:
            info["platform"] = "1688"
        elif "tmall.com" in url_lower:
            info["platform"] = "tmall"
        # 미국
        elif "iherb.com" in url_lower:
            info["platform"] = "iherb"
        elif "amazon.com" in url_lower and ".co.jp" not in url_lower:
            info["platform"] = "amazon_us"
        elif "vitacost.com" in url_lower:
            info["platform"] = "vitacost"
        elif "gnc.com" in url_lower:
            info["platform"] = "gnc"
        # 일본
        elif "rakuten.co.jp" in url_lower:
            info["platform"] = "rakuten"
        elif "amazon.co.jp" in url_lower:
            info["platform"] = "amazon_jp"
        elif "cosme.net" in url_lower:
            info["platform"] = "cosme"
        # 베트남
        elif "shopee.vn" in url_lower:
            info["platform"] = "shopee_vn"
        elif "lazada.vn" in url_lower:
            info["platform"] = "lazada_vn"

        # Item ID 추출
        id_match = re.search(r'id=(\d+)', url)
        if not id_match:
            id_match = re.search(r'/dp/([A-Z0-9]+)', url)  # Amazon ASIN
        if not id_match:
            id_match = re.search(r'/pr/(\d+)', url)  # iHerb
        if not id_match:
            id_match = re.search(r'/offer/(\d+)', url)  # 1688
        if id_match:
            info["item_id"] = id_match.group(1)

        return info

    def _check_risk_keywords(self, title: str, description: str) -> tuple:
        """리스크 키워드 기반 1차 필터링"""
        risk_flags = []
        risk_details = {}

        combined_text = f"{title} {description}".lower()

        for risk_type, keywords in self.risk_keywords.items():
            matched_keywords = [kw for kw in keywords if kw.lower() in combined_text]
            if matched_keywords:
                risk_flags.append(risk_type)
                risk_details[risk_type] = matched_keywords

        return risk_flags, risk_details

    def _analyze_with_llm(self, input_model: SourcingInputSchema, risk_flags: List[str], country_code: str = "CN") -> Dict[str, Any]:
        """LLM을 사용한 상세 분석 — 멀티국가 지원"""
        from country_config import get_country

        if not self.client:
            return {
                "product_classification": "테스트",
                "recommended_decision": "보류" if risk_flags else "통과",
                "confidence": 0.5
            }

        country = get_country(country_code)
        country_name = country.name_ko if country else "중국"
        country_notes = "\n".join(f"- {n}" for n in country.risk_notes) if country else ""

        prompt = f"""당신은 Fortimove Global의 소싱 담당자입니다.
다음 상품 정보를 분석하여 소싱 가능 여부를 판단하십시오.

# 입력 정보
- URL: {input_model.source_url}
- 제목: {input_model.source_title or "미제공"}
- 설명: {input_model.source_description or "미제공"}
- 키워드: {', '.join(input_model.keywords) if input_model.keywords else "없음"}
- 소싱 국가: {country_name} ({country_code})
- 타겟 시장: {input_model.market}

# {country_name} 소싱 시 주의사항
{country_notes or "없음"}

# 자동 감지된 리스크
{', '.join(risk_flags) if risk_flags else "없음"}

# 분석 기준
1. **지재권 리스크**: 유명 브랜드 모방/침해 여부
2. **통관 리스크**: 의약품, 식품 등 통관 제한 품목 (한국 수입 기준)
3. **의료기기 리스크**: 의료적 효능 표방 여부
4. **인증 리스크**: 해당 국가에서 한국 수입 시 필요한 인증 (KC, 식약처 등)
5. **상품 분류**: 테스트/반복/PB 중 판단

# 출력 형식 (JSON)
{{
  "product_classification": "테스트|반복|PB",
  "recommended_decision": "통과|보류|제외",
  "confidence": 0.9,
  "risk_assessment": "리스크 평가 1줄",
  "reasoning": "판단 근거 2-3줄",
  "required_certs": ["한국 수입 시 필요한 인증 목록"]
}}

JSON만 반환하십시오."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = response.content[0].text.strip()

            # Markdown block cleanup
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            return json.loads(raw)

        except Exception as e:
            logger.error(f"LLM 분석 실패: {e}")
            return {
                "product_classification": "테스트",
                "recommended_decision": "보류",
                "confidence": 0.3,
                "risk_assessment": f"LLM 분석 실패: {str(e)}",
                "reasoning": "자동 분석 실패로 보류 처리"
            }

    def _generate_vendor_questions(self, input_model: SourcingInputSchema, llm_analysis: Dict, country_code: str = "CN") -> tuple:
        """벤더 질문 생성 — 국가별 언어 지원"""

        # 한국어 기본 질문 (공통)
        questions_ko = [
            "현재 실재고가 있나요? 품절 위험은 없나요?",
            "배송까지 걸리는 리드타임은 며칠인가요?",
            "최소 주문 수량(MOQ)이 있나요?"
        ]

        # 국가별 현지 언어 질문
        LOCAL_QUESTIONS = {
            "CN": [
                "现在有现货吗？没有缺货风险吗？",
                "从订购到发货需要多少天？",
                "有最小订购量(MOQ)吗？",
            ],
            "US": [
                "Is this item currently in stock?",
                "What is the lead time from order to shipment?",
                "Is there a minimum order quantity (MOQ)?",
            ],
            "JP": [
                "現在在庫はありますか？品切れのリスクはありませんか？",
                "注文から発送までのリードタイムは何日ですか？",
                "最小注文数量（MOQ）はありますか？",
            ],
            "VN": [
                "Hiện tại có hàng sẵn không? Có nguy cơ hết hàng không?",
                "Thời gian giao hàng từ khi đặt là bao lâu?",
                "Có số lượng đặt hàng tối thiểu (MOQ) không?",
            ],
        }

        questions_local = LOCAL_QUESTIONS.get(country_code, LOCAL_QUESTIONS["CN"])

        # 리스크에 따라 추가 질문
        risk_text = llm_analysis.get("risk_assessment", "")

        if "지재권" in risk_text or "지재권" in str(llm_analysis):
            questions_ko.append("이 제품은 정품인가요? 브랜드 라이선스가 있나요?")
            ip_q = {"CN": "这个产品是正品吗？有品牌授权吗？", "US": "Is this an authorized/genuine product?",
                     "JP": "この製品は正規品ですか？ブランドライセンスはありますか？", "VN": "Sản phẩm này có phải hàng chính hãng không?"}
            questions_local.append(ip_q.get(country_code, ip_q["CN"]))

        if "통관" in risk_text or "통관" in str(llm_analysis):
            questions_ko.append("한국 수입 시 필요한 서류나 인증이 있나요?")
            customs_q = {"CN": "韩国清关时需要什么文件或认证吗？", "US": "Do you have export documentation for Korea import?",
                          "JP": "韓国への輸出に必要な書類や認証はありますか？", "VN": "Có giấy tờ xuất khẩu sang Hàn Quốc không?"}
            questions_local.append(customs_q.get(country_code, customs_q["CN"]))

        # 국가별 특수 질문
        if country_code == "US":
            questions_ko.append("FDA 등록 시설에서 생산된 제품인가요?")
            questions_local.append("Is this product manufactured in an FDA-registered facility?")
        elif country_code == "JP":
            questions_ko.append("성분표 및 원산지 증명서 제공이 가능한가요?")
            questions_local.append("成分表と原産地証明書の提供は可能ですか？")
        elif country_code == "VN":
            questions_ko.append("위생/검역 증명서가 있나요?")
            questions_local.append("Có giấy chứng nhận vệ sinh/kiểm dịch không?")

        return questions_ko, questions_local

    def _make_decision(self, risk_flags: List[str], llm_analysis: Dict) -> str:
        """최종 소싱 판정"""

        # Rule 1: 치명적 리스크 (지재권, 의약품) → 제외
        # ⚠️ 2026-04-01 업데이트: 의약품 리스크 "제외" 판정으로 강화 (약사법 위반 위험)
        if "지재권" in risk_flags:
            return "제외"

        if "의약품" in risk_flags:
            return "제외"  # 약사법 위반 시 징역 10년/벌금 1억원 → 무조건 제외

        # Rule 2: 의료기기 리스크 → 제외
        # ⚠️ 2026-04-01 업데이트: 의료기기도 무조건 제외 (의료기기법 위반 위험)
        if "의료기기" in risk_flags:
            return "제외"  # 의료기기법 위반 시 징역 5년/벌금 5천만원 → 무조건 제외

        # Rule 3: LLM 추천이 제외 → 제외
        if llm_analysis.get("recommended_decision") == "제외":
            return "제외"

        # Rule 4: 2개 이상 리스크 → 보류
        if len(risk_flags) >= 2:
            return "보류"

        # Rule 5: 1개 리스크 → 보류
        if len(risk_flags) == 1:
            return "보류"

        # Rule 6: 리스크 없음 → 통과
        return "통과"

    def _recommend_next_step(self, decision: str, risk_flags: List[str]) -> str:
        """다음 단계 권고"""

        if decision == "제외":
            return "소싱 불가 - 다른 상품 검색 권장"

        elif decision == "보류":
            if "지재권" in risk_flags:
                return "변리사 검토 필요 - 상표권/디자인권 확인 후 재판단"
            elif "통관" in risk_flags:
                return "관세사 확인 필요 - 통관 가능 여부 검증 후 재판단"
            elif "의료기기" in risk_flags:
                return "상품 설명 수정 필요 - 의료적 효능 표현 제거 후 재검토"
            else:
                return "벤더에게 추가 정보 요청 후 재검토"

        else:  # 통과
            if risk_flags:
                return "주의 사항 확인 후 마진 검수 단계로 이동"
            else:
                return "마진 검수 단계로 즉시 이동 가능"

    def _check_legal_compliance(self, product_name: str, description: str, risk_flags: List[str]) -> Dict[str, Any]:
        """
        Korean Law MCP를 사용한 종합 법령 검증

        Args:
            product_name: 상품명
            description: 상품 설명
            risk_flags: 감지된 리스크 플래그

        Returns:
            법령 검증 결과
        """
        try:
            # 종합 법적 리스크 체크 (의료기기 + 약사법 + 건강기능식품 + 통관)
            result = self.korean_law.comprehensive_legal_check(product_name, description)

            # risk_flags 기반 추가 검색이 필요한 경우
            for flag in risk_flags:
                if flag not in result.get("flagged_categories", []):
                    result["flagged_categories"].append(flag)
                    if result["overall_risk_level"] == "low":
                        result["overall_risk_level"] = "medium"

            if result["overall_risk_level"] in ("high", "critical"):
                logger.warning(
                    f"법적 리스크 감지 [{result['overall_risk_level']}]: "
                    f"{', '.join(result.get('flagged_categories', []))}"
                )

            return result

        except Exception as e:
            logger.error(f"종합 법령 검증 실패: {e}")
            return {
                "medical_device": None,
                "pharmaceutical": None,
                "health_food": None,
                "customs": None,
                "overall_risk_level": "unknown",
                "recommendations": [],
                "error": str(e)
            }
