"""
Pricing Agent - Fortimove Premium Strategy
목적: 단순 마진 계산이 아닌, Curation Multiplier + Regulation Risk Cost를 반영한 프리미엄 가격 책정

비즈니스 로직:
- Fortimove는 '헬스케어 큐레이션 브랜드'로 포지셔닝
- 단순 직구 대행이 아닌 '전문가 검수 + 안전성 보장' 서비스
- Curation Multiplier (1.3~1.5): 카테고리별 전문성 가중치
- Regulation Risk Cost: 법적 리스크 대응 고정비 (인증, 보험, 법률 자문 등)
"""

from typing import Dict, Any, Type, Optional
from pydantic import BaseModel, Field
from agent_framework import BaseAgent, TaskResult, AgentStatus, register_agent
import logging

logger = logging.getLogger(__name__)


# Input/Output Schemas
class PricingInput(BaseModel):
    """가격 책정 입력 (11개 원가 변수 + 멀티국가)"""
    source_price_cny: float = Field(..., description="소싱 원가 (소싱국 통화, 필드명은 레거시 호환)")
    shipping_fee_krw: Optional[float] = Field(None, description="물류비 (KRW, 미입력 시 무게 기반 자동 계산)")
    category: str = Field(default="general", description="상품 카테고리")
    weight_kg: float = Field(default=0.5, description="무게 (kg)")
    product_name: Optional[str] = Field(None, description="상품명 (위험도 판단용)")

    # 멀티국가 지원
    source_country: str = Field(default="CN", description="소싱 국가 (CN/US/JP/VN)")

    # 선택적 오버라이드
    exchange_rate: Optional[float] = Field(None, description="환율 (직접 지정 시, 미입력 시 국가별 기본값)")
    curation_multiplier: Optional[float] = Field(None, description="큐레이션 배율 오버라이드")

    # 실무 원가 변수
    platform_fee_rate: Optional[float] = Field(None, description="플랫폼 수수료율 (쿠팡 10.8%, 네이버 5.5%)")
    packaging_fee_krw: Optional[float] = Field(None, description="포장비 (KRW, 기본: 1000)")
    inspection_fee_krw: Optional[float] = Field(None, description="검수비 (KRW, 기본: 500)")
    return_rate: Optional[float] = Field(None, description="반품률 (0.0~1.0, 기본: 0.03)")


class PricingOutput(BaseModel):
    """가격 책정 결과"""
    final_price: float = Field(..., description="최종 판매가 (KRW)")
    final_price_krw: float = Field(0, description="최종 판매가 별칭 (호환용)")
    margin_rate: float = Field(..., description="순마진율 (%)")
    margin_amount: float = Field(..., description="순마진 금액 (KRW)")
    breakeven_qty: int = Field(0, description="손익분기 수량")
    pricing_decision: str = Field("", description="등록가능/재검토/제외")
    cost_breakdown: Dict[str, float] = Field(..., description="비용 구성")
    strategy_notes: str = Field(..., description="가격 전략 설명")


@register_agent("pricing")
class PricingAgent(BaseAgent):
    """
    Pricing Agent

    Features:
    - 환율 자동 조회 (fallback: 195 KRW/CNY)
    - 카테고리별 Curation Multiplier
    - Regulation Risk Cost (고정비)
    - 관부가세 자동 계산
    """

    # 카테고리별 Curation Multiplier
    CURATION_MULTIPLIERS = {
        "wellness": 1.5,      # 건강기능식품: 최고 전문성
        "supplement": 1.45,   # 영양제
        "beauty": 1.4,        # 뷰티/화장품
        "healthcare": 1.5,    # 헬스케어 기기
        "fitness": 1.35,      # 운동용품
        "food": 1.4,          # 식품
        "general": 1.3,       # 일반 상품 (최소값)
    }

    # Regulation Risk Cost (카테고리별 고정비)
    REGULATION_COSTS = {
        "wellness": 15000,    # 건강기능식품: 인증, 보험 비용
        "supplement": 12000,  # 영양제
        "beauty": 8000,       # 뷰티
        "healthcare": 20000,  # 의료기기류: 최고 리스크
        "fitness": 5000,      # 운동용품
        "food": 10000,        # 식품
        "general": 3000,      # 일반 상품
    }

    DEFAULT_EXCHANGE_RATE = 195.0  # KRW/CNY (레거시 기본값)
    DEFAULT_TAX_RATE = 0.10        # 관부가세 10% (간이세율, 레거시 기본값)

    def __init__(self):
        super().__init__("pricing")

    @property
    def input_schema(self) -> Type[BaseModel]:
        return PricingInput

    @property
    def output_schema(self) -> Type[BaseModel]:
        return PricingOutput

    # 플랫폼별 기본 수수료율
    PLATFORM_FEE_RATES = {
        "smartstore": 0.055,   # 네이버 스마트스토어 5.5%
        "coupang": 0.108,      # 쿠팡 10.8%
        "gmarket": 0.12,       # 지마켓 12%
        "default": 0.08,       # 기본값 8%
    }

    def _do_execute(self, input_model: PricingInput) -> Dict[str, Any]:
        """
        가격 책정 실행 (11개 원가 변수 반영)

        공식:
        총원가 = 소싱원가(KRW) + 물류비 + 관부가세 + 포장비 + 검수비 + 규제비
        최종가 = 총원가 × Curation_Multiplier
        순마진 = 최종가 - 총원가 - 플랫폼수수료 - 반품손실
        """

        # 0. 국가별 설정 로드
        from country_config import get_country
        country = get_country(input_model.source_country)

        # 1. 환율 적용 (국가별 기본값)
        if input_model.exchange_rate:
            exchange_rate = input_model.exchange_rate
        elif country:
            exchange_rate = country.exchange_rate
        else:
            exchange_rate = self.DEFAULT_EXCHANGE_RATE

        source_price_krw = input_model.source_price_cny * exchange_rate

        # 2. 물류비 계산 (국가별 기본값)
        if input_model.shipping_fee_krw is not None:
            shipping_fee = input_model.shipping_fee_krw
        elif country:
            shipping_fee = max(country.shipping_min_krw, input_model.weight_kg * country.shipping_per_kg_krw)
        else:
            shipping_fee = max(3000, input_model.weight_kg * 5000)

        # 3. 관부가세 (국가별 관세율)
        tax_rate = country.customs_tax_rate if country else self.DEFAULT_TAX_RATE
        customs_tax = source_price_krw * tax_rate

        # 4. 포장비 + 검수비
        packaging_fee = input_model.packaging_fee_krw if input_model.packaging_fee_krw is not None else 1000
        inspection_fee = input_model.inspection_fee_krw if input_model.inspection_fee_krw is not None else 500

        # 5. 카테고리별 설정
        category = input_model.category.lower()
        curation_multiplier = (
            input_model.curation_multiplier
            or self.CURATION_MULTIPLIERS.get(category, self.CURATION_MULTIPLIERS["general"])
        )
        regulation_cost = self.REGULATION_COSTS.get(category, self.REGULATION_COSTS["general"])

        # 6. 총 원가 (판매가 결정 전)
        total_cost = source_price_krw + shipping_fee + customs_tax + packaging_fee + inspection_fee + regulation_cost

        # 7. 최종 판매가
        final_price_raw = (source_price_krw + shipping_fee + customs_tax) * curation_multiplier + regulation_cost + packaging_fee + inspection_fee
        # 100원 단위 반올림 (이커머스 관행)
        final_price = round(final_price_raw / 100) * 100

        # 8. 플랫폼 수수료
        platform_fee_rate = input_model.platform_fee_rate if input_model.platform_fee_rate is not None else self.PLATFORM_FEE_RATES["default"]
        platform_fee = final_price * platform_fee_rate

        # 9. 반품 손실
        return_rate = input_model.return_rate if input_model.return_rate is not None else 0.03
        return_loss = final_price * return_rate

        # 10. 순마진 계산
        net_margin = final_price - total_cost - platform_fee - return_loss
        net_margin_rate = (net_margin / final_price) * 100 if final_price > 0 else 0

        # 11. 손익분기 수량 (규제비를 고정비로 간주)
        per_unit_margin = net_margin + regulation_cost  # 규제비 제외한 단위 마진
        breakeven_qty = max(1, int(regulation_cost / per_unit_margin)) if per_unit_margin > 0 else 999

        # 12. 판정
        if net_margin_rate >= 25:
            pricing_decision = "등록가능"
        elif net_margin_rate >= 15:
            pricing_decision = "재검토"
        else:
            pricing_decision = "제외"

        # 비용 구성
        cost_breakdown = {
            "source_price_krw": round(source_price_krw),
            "shipping_fee_krw": round(shipping_fee),
            "customs_tax_krw": round(customs_tax),
            "packaging_fee_krw": round(packaging_fee),
            "inspection_fee_krw": round(inspection_fee),
            "regulation_risk_cost_krw": regulation_cost,
            "total_cost_krw": round(total_cost),
            "curation_markup_krw": round(final_price - total_cost),
            "platform_fee_krw": round(platform_fee),
            "return_loss_krw": round(return_loss),
            "final_price_krw": round(final_price),
            "net_margin_krw": round(net_margin),
        }

        # 전략 설명
        country_name = country.name_ko if country else "중국"
        currency = country.currency if country else "CNY"
        strategy_notes = (
            f"[Fortimove Premium Pricing - 11변수 모델]\n"
            f"• 소싱국: {country_name} ({input_model.source_country})\n"
            f"• 카테고리: {category.upper()} (큐레이션 배율: {curation_multiplier}x)\n"
            f"• 소싱원가: {input_model.source_price_cny} {currency} × {exchange_rate}원 = {source_price_krw:,.0f}원\n"
            f"• 물류비: {shipping_fee:,.0f}원 ({input_model.weight_kg}kg)\n"
            f"• 관부가세: {customs_tax:,.0f}원 ({tax_rate*100:.0f}%)\n"
            f"• 포장비: {packaging_fee:,.0f}원 / 검수비: {inspection_fee:,.0f}원\n"
            f"• 규제 리스크 비용: {regulation_cost:,.0f}원\n"
            f"• 플랫폼 수수료: {platform_fee:,.0f}원 ({platform_fee_rate*100:.1f}%)\n"
            f"• 반품 손실: {return_loss:,.0f}원 (반품률 {return_rate*100:.1f}%)\n"
            f"───────────────────\n"
            f"• 최종 판매가: ₩{final_price:,.0f}\n"
            f"• 순마진: ₩{net_margin:,.0f} ({net_margin_rate:.1f}%)\n"
            f"• 손익분기: {breakeven_qty}개\n"
            f"• 판정: {pricing_decision}"
        )

        logger.info(f"💰 Pricing: {input_model.product_name or '상품'} → ₩{final_price:,.0f} (순마진 {net_margin_rate:.1f}%) [{pricing_decision}]")

        return {
            "final_price": round(final_price),
            "final_price_krw": round(final_price),
            "margin_rate": round(net_margin_rate, 2),
            "margin_amount": round(net_margin),
            "breakeven_qty": breakeven_qty,
            "pricing_decision": pricing_decision,
            "cost_breakdown": cost_breakdown,
            "strategy_notes": strategy_notes,
        }


def register_pricing_agent():
    """Registry에 에이전트 등록"""
    from agent_framework import AgentRegistry
    registry = AgentRegistry()
    registry.register("pricing", PricingAgent())
    logger.info("✅ Pricing Agent registered")


if __name__ == "__main__":
    # Unit Test
    print("=" * 80)
    print("Pricing Agent Unit Test")
    print("=" * 80)

    agent = PricingAgent()

    # Test Case 1: Wellness 상품
    test_input = {
        "source_price_cny": 50.0,
        "category": "wellness",
        "weight_kg": 0.3,
        "product_name": "프리미엄 비타민 C"
    }

    result = agent.execute(test_input)

    print(f"\n✅ Status: {result.status}")
    print(f"📊 Final Price: {result.output['final_price']:,.0f}원")
    print(f"💰 Margin Rate: {result.output['margin_rate']}%")
    print(f"\n📋 Cost Breakdown:")
    for k, v in result.output['cost_breakdown'].items():
        print(f"   • {k}: {v:,.0f}원")

    print(f"\n📝 Strategy Notes:")
    print(result.output['strategy_notes'])

    # Test Case 2: General 상품
    print("\n" + "=" * 80)
    print("Test Case 2: General Product")
    print("=" * 80)

    test_input_2 = {
        "source_price_cny": 30.0,
        "category": "general",
        "weight_kg": 0.5,
        "product_name": "스테인리스 텀블러"
    }

    result_2 = agent.execute(test_input_2)
    print(f"\n✅ Final Price: {result_2.output['final_price']:,.0f}원")
    print(f"💰 Margin Rate: {result_2.output['margin_rate']}%")
