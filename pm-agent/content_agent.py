"""
콘텐츠/홍보 에이전트 (Content Agent)
- 상품 상세페이지 카피 작성 (SEO 최적화)
- SNS 홍보 문구 생성 (인스타그램, 블로그 등)
- 광고 문구 생성 (네이버 쇼핑, 쿠팡 등)
- 이미지 대체 텍스트(alt text) 생성
- 브랜드 톤앤매너 적용 (과장 금지, 건조한 사실 전달)
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel, Field
from anthropic import Anthropic

from agent_framework import BaseAgent, register_agent

logger = logging.getLogger(__name__)

# ============================================================
# Schema Definitions
# ============================================================

class ContentInputSchema(BaseModel):
    """Content Agent 입력 스키마"""
    product_name: str                                    # 상품명 (필수)
    product_category: Optional[str] = None               # 카테고리
    product_description: Optional[str] = None            # 기본 설명
    key_features: Optional[List[str]] = Field(default_factory=list)  # 주요 특징
    price: Optional[float] = None                        # 가격
    target_customer: Optional[str] = None                # 타겟 고객 (예: 20대 여성, 직장인 등)
    target_platform: str = "smartstore"                  # 타겟 플랫폼 (smartstore/coupang/instagram/blog)
    content_type: str = "product_page"                   # 콘텐츠 유형 (product_page/sns/ad/alt_text)
    brand_context: Optional[str] = None                  # 브랜드 맥락 (Global/Main)
    tone: str = "neutral"                                # 톤 (neutral/friendly/professional)
    seo_keywords: Optional[List[str]] = Field(default_factory=list)  # SEO 키워드
    compliance_mode: bool = True                         # 컴플라이언스 모드 (과장 표현 필터링)

class ContentOutputSchema(BaseModel):
    """Content Agent 출력 스키마"""
    content_type: str                                    # 생성된 콘텐츠 유형
    main_content: str                                    # 메인 콘텐츠 (상세페이지/SNS 포스트 등)
    variations: List[str] = Field(default_factory=list)  # 대안 버전 (3-5개)
    seo_title: Optional[str] = None                      # SEO 최적화 제목
    seo_description: Optional[str] = None                # SEO 메타 설명
    hashtags: Optional[List[str]] = Field(default_factory=list)  # 해시태그 (SNS용)
    ad_headlines: Optional[List[str]] = Field(default_factory=list)  # 광고 헤드라인
    image_alt_texts: Optional[List[str]] = Field(default_factory=list)  # 이미지 대체 텍스트
    warnings: List[str] = Field(default_factory=list)    # 리스크 경고
    compliance_status: str = "safe"                      # 컴플라이언스 상태 (safe/warning/violation)

# ============================================================
# Content Agent Implementation
# ============================================================

@register_agent("content")
class ContentAgent(BaseAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return ContentInputSchema

    @property
    def output_schema(self) -> Type[BaseModel]:
        return ContentOutputSchema

    def __init__(self):
        super().__init__("content")
        # LLM Router 우선 사용 (Gemini Flash)
        self._use_router = False
        try:
            from llm_router import call_llm
            self._call_llm = call_llm
            self._use_router = True
        except ImportError:
            pass

        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            if not self._use_router:
                logger.warning("Content Agent: API 없음")

        self.model = "claude-sonnet-4-20250514"

        # 금지 표현 사전 (컴플라이언스)
        self.prohibited_expressions = {
            "의료적 효능": ["치료", "완치", "개선", "회복", "예방", "질병", "병", "증상"],
            "과대광고": ["최고", "1위", "세계최초", "100%", "절대", "완벽", "기적", "혁명적"],
            "허위 보장": ["반드시", "무조건", "확실", "보증", "당일배송 보장", "환불 100%"],
            "의약품 오인": ["약", "처방", "복용", "투약", "의약", "치료제", "특효"]
        }

    def _llm_call(self, prompt: str, task_type: str = "copywriting", max_tokens: int = 2000) -> str:
        """LLM Router 또는 직접 Claude 호출"""
        if self._use_router:
            return self._call_llm(task_type=task_type, prompt=prompt, max_tokens=max_tokens)
        elif self.client:
            response = self.client.messages.create(
                model=self.model, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        raise RuntimeError("LLM 클라이언트 없음")

    def _do_execute(self, input_model: ContentInputSchema) -> Dict[str, Any]:
        """Content Agent 메인 로직"""

        # 1. 컴플라이언스 사전 검사
        compliance_warnings = []
        if input_model.compliance_mode:
            compliance_warnings = self._check_compliance_preemptive(
                input_model.product_name,
                input_model.product_description or "",
                input_model.key_features
            )

        # 2. 콘텐츠 유형별 생성
        if input_model.content_type == "product_page":
            result = self._generate_product_page(input_model, compliance_warnings)
        elif input_model.content_type == "sns":
            result = self._generate_sns_content(input_model, compliance_warnings)
        elif input_model.content_type == "ad":
            result = self._generate_ad_content(input_model, compliance_warnings)
        elif input_model.content_type == "alt_text":
            result = self._generate_alt_text(input_model, compliance_warnings)
        else:
            result = self._generate_product_page(input_model, compliance_warnings)

        # 3. 컴플라이언스 후처리 검증
        final_warnings = compliance_warnings.copy()
        if input_model.compliance_mode:
            post_warnings = self._check_compliance_post(result.get("main_content", ""))
            final_warnings.extend(post_warnings)

        # 4. 최종 상태 판정
        compliance_status = "safe"
        if len(final_warnings) > 0:
            compliance_status = "warning"
        if any("의료" in w or "허위" in w for w in final_warnings):
            compliance_status = "violation"

        result["warnings"] = final_warnings
        result["compliance_status"] = compliance_status

        return result

    def _check_compliance_preemptive(self, product_name: str, description: str, features: List[str]) -> List[str]:
        """사전 컴플라이언스 검사 (입력 데이터)"""
        warnings = []
        combined_text = f"{product_name} {description} {' '.join(features or [])}"

        for category, keywords in self.prohibited_expressions.items():
            matched = [kw for kw in keywords if kw in combined_text]
            if matched:
                warnings.append(f"[입력 데이터] {category} 감지: {', '.join(matched[:3])}")

        return warnings

    def _check_compliance_post(self, generated_content: str) -> List[str]:
        """후처리 컴플라이언스 검사 (생성된 콘텐츠)"""
        warnings = []

        for category, keywords in self.prohibited_expressions.items():
            matched = [kw for kw in keywords if kw in generated_content]
            if matched:
                warnings.append(f"[생성 콘텐츠] {category} 감지: {', '.join(matched[:3])}")

        return warnings

    def _generate_product_page(self, input_model: ContentInputSchema, warnings: List[str]) -> Dict[str, Any]:
        """상품 상세페이지 카피 생성"""

        if not self.client:
            return self._generate_fallback_content(input_model, "product_page")

        prompt = f"""당신은 Fortimove Global의 이커머스 카피라이터입니다.
다음 상품에 대한 상세페이지 카피를 작성하십시오.

# 상품 정보
- 상품명: {input_model.product_name}
- 카테고리: {input_model.product_category or '미지정'}
- 기본 설명: {input_model.product_description or '없음'}
- 주요 특징: {', '.join(input_model.key_features) if input_model.key_features else '없음'}
- 가격: {input_model.price if input_model.price else '미정'}원
- 타겟 고객: {input_model.target_customer or '일반 소비자'}

# 필수 작성 원칙 (컴플라이언스)
1. **의료적 효능 표현 절대 금지**: "치료", "개선", "예방", "완치" 등 의료 효능 암시 불가
2. **과대광고 금지**: "최고", "1위", "100%" 등 검증 불가능한 최상급 표현 불가
3. **허위 보장 금지**: "반드시", "무조건", "보증" 등 확정적 약속 불가
4. **사실 중심 작성**: 제품의 실제 스펙, 재질, 크기, 기능만 객관적으로 기술
5. **톤앤매너**: {input_model.tone} - 건조하고 사실적인 문체 유지

# 사전 경고
{chr(10).join(warnings) if warnings else '없음'}

# 출력 형식 (JSON)
{{
  "main_content": "상세페이지 본문 (300-500자, HTML 태그 없음)",
  "variations": ["대안1", "대안2", "대안3"],
  "seo_title": "SEO 최적화 제목 (50자 이내)",
  "seo_description": "SEO 메타 설명 (120자 이내)",
  "seo_keywords": ["키워드1", "키워드2", "키워드3"]
}}

JSON만 반환하십시오."""

        try:
            response_obj = None  # router handles this
            response_text = self._llm_call(prompt, task_type="copywriting", max_tokens=2000)

            raw = response_text.strip()

            # JSON 추출
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)
            result["content_type"] = "product_page"
            return result

        except Exception as e:
            logger.error(f"상품 상세페이지 생성 실패: {e}")
            return self._generate_fallback_content(input_model, "product_page")

    def _generate_sns_content(self, input_model: ContentInputSchema, warnings: List[str]) -> Dict[str, Any]:
        """SNS 홍보 문구 생성 (인스타그램, 블로그 등)"""

        if not self.client:
            return self._generate_fallback_content(input_model, "sns")

        prompt = f"""당신은 Fortimove Global의 SNS 마케터입니다.
다음 상품에 대한 SNS 홍보 포스트를 작성하십시오.

# 상품 정보
- 상품명: {input_model.product_name}
- 카테고리: {input_model.product_category or '미지정'}
- 주요 특징: {', '.join(input_model.key_features) if input_model.key_features else '없음'}
- 타겟 고객: {input_model.target_customer or '일반 소비자'}
- 플랫폼: {input_model.target_platform}

# 작성 원칙
1. **SNS 친화적**: 짧고 임팩트 있게 (150-200자)
2. **과장 금지**: 의료 효능, 최상급 표현 배제
3. **해시태그**: 관련성 높은 해시태그 5-7개
4. **톤앤매너**: {input_model.tone} - 친근하되 과하지 않게

# 출력 형식 (JSON)
{{
  "main_content": "SNS 메인 포스트 (150-200자)",
  "variations": ["대안1", "대안2", "대안3"],
  "hashtags": ["#해시태그1", "#해시태그2", "#해시태그3"]
}}

JSON만 반환하십시오."""

        try:
            response_obj = None
            response_text = self._llm_call(prompt, task_type="sns_content", max_tokens=1500)

            raw = response_text.strip()

            # JSON 추출
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)
            result["content_type"] = "sns"
            return result

        except Exception as e:
            logger.error(f"SNS 콘텐츠 생성 실패: {e}")
            return self._generate_fallback_content(input_model, "sns")

    def _generate_ad_content(self, input_model: ContentInputSchema, warnings: List[str]) -> Dict[str, Any]:
        """광고 문구 생성 (네이버 쇼핑, 쿠팡 등)"""

        if not self.client:
            return self._generate_fallback_content(input_model, "ad")

        prompt = f"""당신은 Fortimove Global의 퍼포먼스 마케터입니다.
다음 상품에 대한 광고 헤드라인을 작성하십시오.

# 상품 정보
- 상품명: {input_model.product_name}
- 카테고리: {input_model.product_category or '미지정'}
- 주요 특징: {', '.join(input_model.key_features) if input_model.key_features else '없음'}
- 가격: {input_model.price if input_model.price else '미정'}원
- 플랫폼: {input_model.target_platform}

# 작성 원칙
1. **짧고 명확**: 헤드라인 30자 이내, 서브카피 50자 이내
2. **과장 금지**: "최고", "1위" 등 검증 불가능한 표현 배제
3. **CTA 포함**: 구매 유도 문구 (예: "지금 확인하세요")
4. **숫자 활용**: 가격, 할인율 등 구체적 숫자 강조 가능

# 출력 형식 (JSON)
{{
  "ad_headlines": ["헤드라인1 (30자)", "헤드라인2", "헤드라인3"],
  "main_content": "광고 본문 (100자 이내)",
  "variations": ["대안1", "대안2"]
}}

JSON만 반환하십시오."""

        try:
            response_text = self._llm_call(prompt, task_type="ad_copy", max_tokens=1500)

            raw = response_text.strip()

            # JSON 추출
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)
            result["content_type"] = "ad"
            return result

        except Exception as e:
            logger.error(f"광고 콘텐츠 생성 실패: {e}")
            return self._generate_fallback_content(input_model, "ad")

    def _generate_alt_text(self, input_model: ContentInputSchema, warnings: List[str]) -> Dict[str, Any]:
        """이미지 대체 텍스트(alt text) 생성"""

        # Alt text는 간단하므로 룰 기반으로 생성
        alt_texts = []

        # 기본 alt text
        base_alt = f"{input_model.product_name}"
        if input_model.product_category:
            base_alt += f" - {input_model.product_category}"

        alt_texts.append(base_alt)

        # 특징 기반 alt text
        if input_model.key_features:
            for i, feature in enumerate(input_model.key_features[:3]):
                alt_texts.append(f"{input_model.product_name} {feature}")

        # 가격 포함 alt text
        if input_model.price:
            alt_texts.append(f"{input_model.product_name} {input_model.price:,.0f}원")

        return {
            "content_type": "alt_text",
            "main_content": base_alt,
            "image_alt_texts": alt_texts,
            "variations": []
        }

    def _generate_fallback_content(self, input_model: ContentInputSchema, content_type: str) -> Dict[str, Any]:
        """API 실패 시 폴백 콘텐츠"""

        fallback = {
            "content_type": content_type,
            "main_content": f"{input_model.product_name}",
            "variations": [],
            "warnings": ["LLM API 호출 실패 - 폴백 콘텐츠 생성됨"]
        }

        if content_type == "product_page":
            fallback["main_content"] = f"{input_model.product_name}\n\n"
            if input_model.product_description:
                fallback["main_content"] += input_model.product_description + "\n\n"
            if input_model.key_features:
                fallback["main_content"] += "주요 특징:\n" + "\n".join([f"- {f}" for f in input_model.key_features])

            fallback["seo_title"] = input_model.product_name
            fallback["seo_description"] = (input_model.product_description or input_model.product_name)[:120]

        elif content_type == "sns":
            fallback["main_content"] = f"{input_model.product_name}"
            if input_model.product_description:
                fallback["main_content"] += f"\n{input_model.product_description[:100]}"
            fallback["hashtags"] = [f"#{input_model.product_category}" if input_model.product_category else "#상품"]

        elif content_type == "ad":
            fallback["ad_headlines"] = [
                input_model.product_name,
                f"{input_model.product_name} - 지금 확인하세요",
                f"{input_model.product_name} 특가"
            ]
            fallback["main_content"] = input_model.product_name

        return fallback


def register_content_agent(registry):
    """Content Agent 등록"""
    registry.register("content", ContentAgent())


# ============================================================
# Multi-Channel Content Generation (Phase 2)
# ============================================================

class MultiChannelContentInputSchema(BaseModel):
    """멀티 채널 콘텐츠 생성 입력 스키마"""
    product_name: str
    product_category: Optional[str] = None
    key_features: List[str] = Field(default_factory=list)
    price: Optional[float] = None
    channels: List[str] = Field(default=["naver", "coupang"])  # 신규
    generate_usp: bool = True  # 신규: USP 생성 여부
    generate_options: bool = True  # 신규: 옵션 한글화 여부
    options: List[str] = Field(default_factory=list)  # 신규: 원본 옵션명
    compliance_mode: bool = True


class MultiChannelContentOutputSchema(BaseModel):
    """멀티 채널 콘텐츠 생성 출력 스키마"""
    naver_title: Optional[str] = None
    coupang_title: Optional[str] = None
    amazon_title: Optional[str] = None
    usp_points: List[str] = Field(default_factory=list)  # 핵심 USP 3개
    detail_description: str  # 금지표현 제거된 상세설명
    seo_tags: List[str] = Field(default_factory=list)  # SEO 태그 10개
    options_korean: Dict[str, str] = Field(default_factory=dict)  # 옵션명 한글화
    compliance_status: str = "safe"
    warnings: List[str] = Field(default_factory=list)


def execute_multichannel(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    채널별 콘텐츠 생성 (Phase 2 신규 메서드)
    
    템플릿 기반 (80%) + LLM 보조 (20%)
    """
    try:
        schema = MultiChannelContentInputSchema(**input_data)
        
        output = {
            "naver_title": self._generate_naver_title(schema),
            "coupang_title": self._generate_coupang_title(schema),
            "usp_points": self._generate_usp(schema) if schema.generate_usp else [],
            "detail_description": self._generate_detail_description(schema),
            "seo_tags": self._generate_seo_tags(schema),
            "options_korean": self._translate_options(schema.options) if schema.generate_options else {},
            "compliance_status": "safe",
            "warnings": []
        }
        
        # 컴플라이언스 체크
        if schema.compliance_mode:
            warnings = self._check_multichannel_compliance(output)
            output["warnings"] = warnings
            if warnings:
                output["compliance_status"] = "warning"
        
        return output
        
    except Exception as e:
        logger.error(f"멀티 채널 콘텐츠 생성 실패: {e}", exc_info=True)
        return {
            "detail_description": schema.product_name,
            "seo_tags": [schema.product_name],
            "usp_points": [],
            "options_korean": {},
            "compliance_status": "error",
            "warnings": [f"생성 실패: {str(e)}"]
        }


def _generate_naver_title(self, schema: MultiChannelContentInputSchema) -> str:
    """네이버 스마트스토어용 상품명 (템플릿 기반)"""
    # 네이버: 50자 제한
    parts = [schema.product_name]
    
    if schema.key_features:
        parts.append(schema.key_features[0])
    
    if schema.product_category:
        parts.append(schema.product_category)
    
    title = " | ".join(parts)
    
    # 50자 제한
    if len(title) > 50:
        title = title[:47] + "..."
    
    return title


def _generate_coupang_title(self, schema: MultiChannelContentInputSchema) -> str:
    """쿠팡용 상품명 (템플릿 기반)"""
    # 쿠팡: 100자 제한, [오늘출발] 태그 선호
    title = f"[오늘출발] {schema.product_name}"
    
    if schema.key_features:
        features_str = " ".join(schema.key_features[:2])
        title += f" {features_str}"
    
    # 100자 제한
    if len(title) > 100:
        title = title[:97] + "..."
    
    return title


def _generate_usp(self, schema: MultiChannelContentInputSchema) -> List[str]:
    """핵심 USP 3개 생성 (템플릿 기반)"""
    usp_points = []
    
    # key_features를 USP로 변환
    for i, feature in enumerate(schema.key_features[:3], 1):
        # 템플릿: "특징 - 설명"
        if "ml" in feature.lower() or "용량" in feature:
            usp_points.append(f"{feature} - 충분한 용량으로 오래 사용")
        elif "단열" in feature or "보온" in feature:
            usp_points.append(f"{feature} - 온도 유지로 신선하게")
        elif "휴대" in feature or "포터블" in feature:
            usp_points.append(f"{feature} - 언제 어디서나 편리하게")
        else:
            usp_points.append(f"{feature} - 프리미엄 품질")
    
    # 3개 미만이면 일반 USP 추가
    if len(usp_points) < 3:
        default_usps = [
            "안전한 소재 - 인체에 무해한 제품",
            "품질 보증 - 꼼꼼한 검수 후 배송",
            "빠른 배송 - 주문 후 1-2일 내 도착"
        ]
        usp_points.extend(default_usps[:3 - len(usp_points)])
    
    return usp_points[:3]


def _generate_detail_description(self, schema: MultiChannelContentInputSchema) -> str:
    """상세 설명 생성 (템플릿 기반)"""
    description = f"{schema.product_name}\n\n"
    
    if schema.key_features:
        description += "주요 특징:\n"
        for feature in schema.key_features:
            description += f"• {feature}\n"
        description += "\n"
    
    # 기본 안내 문구
    description += "제품 상세:\n"
    description += f"• 카테고리: {schema.product_category or '일반'}\n"
    
    if schema.price:
        description += f"• 가격: {schema.price:,.0f}원\n"
    
    description += "\n배송 안내:\n"
    description += "• 배송비: 무료 (일부 지역 제외)\n"
    description += "• 배송 기간: 주문 후 1-2일 (영업일 기준)\n"
    
    # 컴플라이언스: 금지 표현 제거
    for category, expressions in self.prohibited_expressions.items():
        for expr in expressions:
            description = description.replace(expr, "")
    
    return description


def _generate_seo_tags(self, schema: MultiChannelContentInputSchema) -> List[str]:
    """SEO 태그 10개 생성 (템플릿 기반)"""
    tags = []
    
    # 1. 상품명 기반
    product_name_clean = schema.product_name.replace(" ", "")
    tags.append(product_name_clean)
    
    # 2. 카테고리 기반
    if schema.product_category:
        tags.append(schema.product_category)
        tags.append(f"{schema.product_category}추천")
    
    # 3. key_features 기반
    for feature in schema.key_features[:3]:
        feature_clean = feature.replace(" ", "")
        tags.append(feature_clean)
    
    # 4. 조합형 태그
    if schema.product_category and schema.key_features:
        tags.append(f"{schema.product_category}{schema.key_features[0]}")
    
    # 5. 일반 태그
    default_tags = [
        "인기상품",
        "베스트셀러",
        "추천상품",
        "신상품",
        "프리미엄"
    ]
    
    # 10개 채우기
    tags.extend(default_tags)
    
    # 중복 제거 및 10개로 제한
    unique_tags = []
    for tag in tags:
        if tag not in unique_tags:
            unique_tags.append(tag)
        if len(unique_tags) >= 10:
            break
    
    return unique_tags[:10]


def _translate_options(self, options: List[str]) -> Dict[str, str]:
    """옵션명 한글화 (템플릿 기반)"""
    translated = {}
    
    for option in options:
        # 간단한 번역 룰
        original = option
        korean = option
        
        # 사이즈 번역
        if "small" in option.lower() or "s" == option.lower():
            korean = "소형"
        elif "medium" in option.lower() or "m" == option.lower():
            korean = "중형"
        elif "large" in option.lower() or "l" == option.lower():
            korean = "대형"
        elif "xl" in option.lower():
            korean = "특대형"
        
        # 용량 번역
        elif "ml" in option.lower():
            korean = option  # 그대로 유지
        elif "g" in option.lower():
            korean = option  # 그대로 유지
        
        # 색상 번역
        elif "black" in option.lower():
            korean = "블랙"
        elif "white" in option.lower():
            korean = "화이트"
        elif "red" in option.lower():
            korean = "레드"
        elif "blue" in option.lower():
            korean = "블루"
        
        translated[original] = korean
    
    return translated


def _check_multichannel_compliance(self, output: Dict[str, Any]) -> List[str]:
    """멀티 채널 콘텐츠 컴플라이언스 체크"""
    warnings = []
    
    # 제목 길이 체크
    if output.get('naver_title') and len(output['naver_title']) > 50:
        warnings.append("네이버 제목이 50자를 초과합니다")
    
    if output.get('coupang_title') and len(output['coupang_title']) > 100:
        warnings.append("쿠팡 제목이 100자를 초과합니다")
    
    # 금지 표현 체크
    detail = output.get('detail_description', '')
    for category, expressions in self.prohibited_expressions.items():
        for expr in expressions:
            if expr in detail:
                warnings.append(f"금지 표현 발견 ({category}): {expr}")
    
    return warnings


# ContentAgent 클래스에 메서드 추가
ContentAgent.execute_multichannel = execute_multichannel
ContentAgent._generate_naver_title = _generate_naver_title
ContentAgent._generate_coupang_title = _generate_coupang_title
ContentAgent._generate_usp = _generate_usp
ContentAgent._generate_detail_description = _generate_detail_description
ContentAgent._generate_seo_tags = _generate_seo_tags
ContentAgent._translate_options = _translate_options
ContentAgent._check_multichannel_compliance = _check_multichannel_compliance
