"""
Pricing Agent - Fortimove Premium Strategy (Multi-Country)
목적: 단순 마진 계산이 아닌, Curation Multiplier + Regulation Risk Cost를 반영한 프리미엄 가격 책정

비즈니스 로직:
- Fortimove는 '헬스케어 큐레이션 브랜드'로 포지셔닝
- 단순 직구 대행이 아닌 '전문가 검수 + 안전성 보장' 서비스
- Curation Multiplier (1.3~1.5): 카테고리별 전문성 가중치
- Regulation Risk Cost: 법적 리스크 대응 고정비 (인증, 보험, 법률 자문 등)
- 4개국 멀티소싱 대응: 중국(CNY), 일본(JPY), 미국(USD), 영국(GBP)
"""

from typing import Dict, Any, Type, Optional, Literal
from pydantic import BaseModel, Field
from agent_framework import BaseAgent, TaskResult, AgentStatus, register_agent
import logging
import urllib.request
import json as _json

logger = logging.getLogger(__name__)

# 지원 소싱 국가 코드
SourceCountry = Literal["CN", "JP", "US", "GB"]


# Input/Output Schemas
class PricingInput(BaseModel):
    """가격 책정 입력 (멀티 국가 지원)"""
    # 기존 필드 (하위 호환 유지 — source_country 미지정 시 CN 기본값)
    source_price_cny: Optional[float] = Field(None, description="소싱 원가 (CNY) — 하위 호환용, source_price로 대체 권장")

    # 멀티 국가 필드
    source_country: SourceCountry = Field(default="CN", description="소싱 국가 (CN/JP/US/GB)")
    source_price: Optional[float] = Field(None, description="소싱 원가 (해당 국가 통화)")
    shipping_fee_krw: Optional[float] = Field(None, description="물류비 (KRW)")
    category: str = Field(default="general", description="상품 카테고리")
    weight_kg: float = Field(default=0.5, description="무게 (kg)")
    product_name: Optional[str] = Field(None, description="상품명 (위험도 판단용)")

    # 선택적 오버라이드
    exchange_rate: Optional[float] = Field(None, description="환율 (직접 지정 시)")
    curation_multiplier: Optional[float] = Field(None, description="큐레이션 배율 오버라이드")


class PricingOutput(BaseModel):
    """가격 책정 결과"""
    source_country: str = Field(..., description="소싱 국가")
    source_currency: str = Field(..., description="소싱 통화")
    final_price: float = Field(..., description="최종 판매가 (KRW)")
    margin_rate: float = Field(..., description="마진율 (%)")
    margin_amount: float = Field(..., description="마진 금액 (KRW)")
    cost_breakdown: Dict[str, Any] = Field(..., description="비용 구성")
    strategy_notes: str = Field(..., description="가격 전략 설명")


@register_agent("pricing")
class PricingAgent(BaseAgent):
    """
    Pricing Agent (Multi-Country)

    Features:
    - 4개국 소싱 지원: 중국(CN), 일본(JP), 미국(US), 영국(GB)
    - 실시간 환율 조회 (fallback: 보수적 고정 환율)
    - 국가별 관세율/물류비 자동 적용
    - 카테고리별 Curation Multiplier
    - Regulation Risk Cost (고정비)
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

    # ── 국가별 설정 테이블 ──────────────────────────────────

    # 통화 코드
    COUNTRY_CURRENCY = {
        "CN": "CNY",
        "JP": "JPY",
        "US": "USD",
        "GB": "GBP",
    }

    # 통화 심볼
    CURRENCY_SYMBOL = {
        "CNY": "¥",
        "JPY": "¥",
        "USD": "$",
        "GBP": "£",
    }

    # 보수적 고정 환율 (KRW per 1 외화) — 실시간 조회 실패 시 fallback
    # 원칙: 회사에 불리한(=높은) 환율 적용
    DEFAULT_EXCHANGE_RATES = {
        "CNY": 200.0,     # 위안 (보수적)
        "JPY": 10.5,      # 엔화 (보수적)
        "USD": 1450.0,    # 달러 (보수적)
        "GBP": 1850.0,    # 파운드 (보수적)
    }

    # 국가별 관세율 (보수적 비관치)
    # 간이세율 기준, 카테고리별 차등
    CUSTOMS_RATES = {
        "CN": {
            "wellness": 0.20, "supplement": 0.20, "beauty": 0.20,
            "healthcare": 0.08, "fitness": 0.13, "food": 0.20, "general": 0.13,
        },
        "JP": {
            "wellness": 0.15, "supplement": 0.15, "beauty": 0.15,
            "healthcare": 0.08, "fitness": 0.10, "food": 0.15, "general": 0.10,
        },
        "US": {
            "wellness": 0.13, "supplement": 0.13, "beauty": 0.13,
            "healthcare": 0.08, "fitness": 0.10, "food": 0.13, "general": 0.10,
        },
        "GB": {
            "wellness": 0.18, "supplement": 0.18, "beauty": 0.18,
            "healthcare": 0.08, "fitness": 0.13, "food": 0.18, "general": 0.13,
        },
    }

    # 국가별 kg당 국제배송비 (KRW) — 보수적 상한치
    SHIPPING_RATES_PER_KG = {
        "CN": 5000,       # 중국: 가장 저렴
        "JP": 8000,       # 일본: EMS 기준
        "US": 12000,      # 미국: 항공 기준
        "GB": 15000,      # 영국: 항공 + 긴 리드타임
    }

    # 국가별 최소 배송비 (KRW)
    SHIPPING_MINIMUM = {
        "CN": 3000,
        "JP": 5000,
        "US": 8000,
        "GB": 10000,
    }

    # 국가별 면세 한도 (KRW 환산, US$150 = 약 217,500원 등)
    DUTY_FREE_THRESHOLD_KRW = {
        "CN": 215000,     # US$150 상당
        "JP": 215000,
        "US": 215000,
        "GB": 215000,
    }

    # ── 환율 캐시 ──────────────────────────────────────────
    _rate_cache: Dict[str, float] = {}

    def __init__(self):
        super().__init__("pricing")

    @property
    def input_schema(self) -> Type[BaseModel]:
        return PricingInput

    @property
    def output_schema(self) -> Type[BaseModel]:
        return PricingOutput

    # ── 환율 조회 ──────────────────────────────────────────

    def _fetch_live_rate(self, currency: str) -> Optional[float]:
        """실시간 환율 조회 (한국수출입은행 대안: exchangerate-api)"""
        if currency in self._rate_cache:
            return self._rate_cache[currency]
        try:
            url = f"https://open.er-api.com/v6/latest/{currency}"
            req = urllib.request.Request(url, headers={"User-Agent": "Fortimove/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = _json.loads(resp.read().decode())
            if data.get("result") == "success":
                krw_rate = data["rates"].get("KRW")
                if krw_rate:
                    self._rate_cache[currency] = krw_rate
                    logger.info(f"📈 실시간 환율 조회 성공: 1 {currency} = {krw_rate:,.2f} KRW")
                    return krw_rate
        except Exception as e:
            logger.warning(f"⚠️ 환율 API 조회 실패 ({currency}): {e} — 보수적 고정 환율 사용")
        return None

    def _get_exchange_rate(self, currency: str, override: Optional[float] = None) -> float:
        """환율 결정: 수동 오버라이드 > 실시간 조회 > 보수적 fallback"""
        if override:
            return override
        live = self._fetch_live_rate(currency)
        if live:
            # 보수적 원칙: 실시간 환율에 3% 버퍼 추가 (회사 불리한 방향)
            return live * 1.03
        return self.DEFAULT_EXCHANGE_RATES[currency]

    # ── 메인 실행 ──────────────────────────────────────────

    def _do_execute(self, input_model: PricingInput) -> Dict[str, Any]:
        """
        가격 책정 실행 (멀티 국가)

        공식:
        최종가 = (원가KRW + 물류비 + 관부가세) * Curation_Multiplier + Regulation_Risk_Cost
        """
        country = input_model.source_country
        currency = self.COUNTRY_CURRENCY[country]
        symbol = self.CURRENCY_SYMBOL[currency]

        # 하위 호환: source_price 없으면 source_price_cny 사용
        source_price_foreign = input_model.source_price or input_model.source_price_cny or 0
        if source_price_foreign <= 0:
            raise ValueError("소싱 원가(source_price 또는 source_price_cny)가 필요합니다.")

        # 1. 환율 적용
        exchange_rate = self._get_exchange_rate(currency, input_model.exchange_rate)
        source_price_krw = source_price_foreign * exchange_rate

        # 2. 물류비 계산 (국가별)
        if input_model.shipping_fee_krw:
            shipping_fee = input_model.shipping_fee_krw
        else:
            rate_per_kg = self.SHIPPING_RATES_PER_KG[country]
            minimum = self.SHIPPING_MINIMUM[country]
            shipping_fee = max(minimum, input_model.weight_kg * rate_per_kg)

        # 3. 관부가세 계산 (국가별 + 카테고리별)
        category = input_model.category.lower()
        country_customs = self.CUSTOMS_RATES.get(country, self.CUSTOMS_RATES["CN"])
        customs_rate = country_customs.get(category, country_customs["general"])

        # 면세 한도 체크 (보수적: 한도 초과 시 전액 과세)
        duty_free = self.DUTY_FREE_THRESHOLD_KRW[country]
        if source_price_krw < duty_free:
            customs_tax = 0
            customs_note = f"면세 (원가 {source_price_krw:,.0f}원 < 한도 {duty_free:,.0f}원)"
        else:
            customs_tax = source_price_krw * customs_rate
            customs_note = f"과세 {customs_rate*100:.0f}% (원가 {source_price_krw:,.0f}원 ≥ 한도 {duty_free:,.0f}원)"

        # 4. 기본 원가
        base_cost = source_price_krw + shipping_fee + customs_tax

        # 5. Curation Multiplier 적용
        if input_model.curation_multiplier:
            curation_multiplier = input_model.curation_multiplier
        else:
            curation_multiplier = self.CURATION_MULTIPLIERS.get(
                category,
                self.CURATION_MULTIPLIERS["general"]
            )

        # 6. Regulation Risk Cost
        regulation_cost = self.REGULATION_COSTS.get(
            category,
            self.REGULATION_COSTS["general"]
        )

        # 7. 최종 가격 계산
        final_price = (base_cost * curation_multiplier) + regulation_cost

        # 8. 마진 계산
        margin_amount = final_price - base_cost - regulation_cost
        margin_rate = (margin_amount / final_price) * 100 if final_price > 0 else 0

        # 9. 비용 구성
        cost_breakdown = {
            "source_country": country,
            "source_currency": currency,
            "source_price_foreign": round(source_price_foreign, 2),
            "exchange_rate": round(exchange_rate, 2),
            "source_price_krw": round(source_price_krw, 0),
            "shipping_fee_krw": round(shipping_fee, 0),
            "customs_rate_pct": round(customs_rate * 100, 1),
            "customs_tax_krw": round(customs_tax, 0),
            "base_cost_krw": round(base_cost, 0),
            "curation_markup_krw": round(base_cost * (curation_multiplier - 1), 0),
            "regulation_risk_cost_krw": regulation_cost,
            "final_price_krw": round(final_price, 0),
            "margin_amount_krw": round(margin_amount, 0),
        }

        # 10. 국가별 전략 설명
        country_names = {"CN": "중국", "JP": "일본", "US": "미국", "GB": "영국"}
        strategy_notes = (
            f"[Fortimove Premium Pricing — {country_names[country]} 소싱]\n"
            f"• 소싱국: {country_names[country]} ({currency})\n"
            f"• 카테고리: {category.upper()} (큐레이션 배율: {curation_multiplier}x)\n"
            f"• 원가: {symbol}{source_price_foreign:,.2f} × {exchange_rate:,.2f}원 = {source_price_krw:,.0f}원\n"
            f"• 물류비: {shipping_fee:,.0f}원 ({input_model.weight_kg}kg, {country_names[country]} 기준)\n"
            f"• 관부가세: {customs_tax:,.0f}원 — {customs_note}\n"
            f"• 규제 리스크 대응 고정비: {regulation_cost:,.0f}원\n"
            f"• 최종 판매가: {final_price:,.0f}원 (마진율: {margin_rate:.1f}%)"
        )

        logger.info(
            f"💰 Pricing 완료 [{country}]: "
            f"{input_model.product_name or '상품'} - {final_price:,.0f}원 (마진율: {margin_rate:.1f}%)"
        )

        return {
            "source_country": country,
            "source_currency": currency,
            "final_price": round(final_price, 0),
            "margin_rate": round(margin_rate, 2),
            "margin_amount": round(margin_amount, 0),
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
    # Unit Test — 4개국 시나리오
    agent = PricingAgent()

    test_cases = [
        {
            "name": "중국 소싱 (하위 호환 — source_price_cny)",
            "input": {
                "source_price_cny": 50.0,
                "category": "wellness",
                "weight_kg": 0.3,
                "product_name": "프리미엄 비타민 C"
            }
        },
        {
            "name": "일본 소싱 — 콜라겐 파우더",
            "input": {
                "source_country": "JP",
                "source_price": 3500,
                "category": "supplement",
                "weight_kg": 0.4,
                "product_name": "일본 콜라겐 파우더"
            }
        },
        {
            "name": "미국 소싱 — 피트니스 밴드",
            "input": {
                "source_country": "US",
                "source_price": 29.99,
                "category": "fitness",
                "weight_kg": 0.3,
                "product_name": "미국 저항 밴드 세트"
            }
        },
        {
            "name": "영국 소싱 — 오가닉 티",
            "input": {
                "source_country": "GB",
                "source_price": 18.50,
                "category": "food",
                "weight_kg": 0.5,
                "product_name": "영국 오가닉 허브티"
            }
        },
    ]

    for tc in test_cases:
        print("=" * 80)
        print(f"[TEST] {tc['name']}")
        print("=" * 80)

        result = agent.execute(tc["input"])

        print(f"  Status: {result.status}")
        if result.is_success():
            out = result.output
            print(f"  소싱국: {out.get('source_country', 'CN')} ({out.get('source_currency', 'CNY')})")
            print(f"  최종 판매가: {out['final_price']:,.0f}원")
            print(f"  마진율: {out['margin_rate']}%")
            print(f"  마진 금액: {out['margin_amount']:,.0f}원")
            print(f"\n  비용 구성:")
            for k, v in out['cost_breakdown'].items():
                if isinstance(v, (int, float)):
                    print(f"    {k}: {v:,.2f}")
                else:
                    print(f"    {k}: {v}")
            print(f"\n  전략 노트:\n{out['strategy_notes']}")
        else:
            print(f"  ERROR: {result.error}")
        print()
