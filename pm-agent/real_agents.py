"""
실제 에이전트 래퍼 (BaseAgent 인터페이스 구현) Phase 4
- BaseHttpAgent 공통 래퍼 도입
- Pydantic 커스텀 Schema 도입
- 무결한 상태 조회를 위한 DailyScoutStatusAgent 분리
"""
import logging
import requests
import re
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel, Field

from agent_framework import BaseAgent, TaskResult, AgentStatus

logger = logging.getLogger(__name__)

class BaseHttpAgent(BaseAgent):
    """
    공통 HTTP 클라이언트 처리를 담당하는 추상 클래스
    타임아웃, 예외 컨텍스트 정규화, 로깅 처리
    """
    def request_api(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        timeout = kwargs.pop('timeout', 30)
        try:
            logger.info(f"🌐 HTTP {method.upper()} -> {url}")
            response = requests.request(method, url, timeout=timeout, **kwargs)
            
            if response.status_code != 200:
                logger.error(f"❌ HTTP 비정상 응답: {response.status_code} - {response.text[:200]}")
                raise RuntimeError(f"HTTP Error {response.status_code}: {response.text[:100]}")
                
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"⏳ HTTP 타임아웃 발생 ({timeout}초)")
            raise RuntimeError("API Timeout")
        except requests.exceptions.ConnectionError:
            logger.error(f"🔌 HTTP 연결 실패: {url}")
            raise RuntimeError("API Connection Error - 서버가 다운되었을 수 있습니다.")
        except Exception as e:
            if not isinstance(e, RuntimeError):
                logger.error(f"🔥 HTTP 클라이언트 예외: {str(e)}")
            raise

# ---------------------------------------------------------
# Image Localization Agent Schema
# ---------------------------------------------------------

class ImageInputSchema(BaseModel):
    image_files: List[str]
    moodtone: str = "premium"
    brand_type: str = "fortimove_global"
    product_name: Optional[str] = None
    generate_seo: bool = True
    auto_replace_risks: bool = True

class ImageOutputSchema(BaseModel):
    job_id: Optional[str] = None
    status: Optional[str] = None
    processed_images: List[Dict[str, Any]] = Field(default_factory=list)
    analysis_report: Dict[str, Any] = Field(default_factory=dict)
    seo_metadata: Optional[Dict[str, Any]] = None
    processing_time_seconds: Optional[float] = None

class ImageLocalizationAgent(BaseHttpAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return ImageInputSchema
    @property
    def output_schema(self) -> Type[BaseModel]:
        return ImageOutputSchema

    def __init__(self, base_url: str = "http://localhost:8000"):
        super().__init__("image_localization")
        self.api_endpoint = f"{base_url}/api/v1/process"

    def _do_execute(self, input_model: ImageInputSchema) -> Dict[str, Any]:
        files = []
        for file_path in input_model.image_files:
            try:
                files.append(('files', open(file_path, 'rb')))
            except FileNotFoundError:
                logger.error(f"Cannot find image: {file_path}")

        if not files:
            raise ValueError("No valid image files provided to upload.")

        data = {
            'moodtone': input_model.moodtone,
            'brand_type': input_model.brand_type,
            'generate_seo': str(input_model.generate_seo).lower(),
            'auto_replace_risks': str(input_model.auto_replace_risks).lower()
        }
        if input_model.product_name:
            data['product_name'] = input_model.product_name

        try:
            result = self.request_api('POST', self.api_endpoint, files=files, data=data, timeout=300)
        finally:
            for _, f in files:
                f.close()

        return result

# ---------------------------------------------------------
# Margin Check Agent Schema
# ---------------------------------------------------------

class MarginInputSchema(BaseModel):
    action: str = "get_stats"  # get_stats, search_products, check_margin, calculate_margin
    product_id: Optional[int] = None
    search_query: Optional[str] = None
    region: Optional[str] = None
    limit: int = 10
    # 원가 구조 계산을 위한 새 필드
    source_price_cny: Optional[float] = None       # 매입가 (위안)
    exchange_rate: Optional[float] = 1350.0        # 환율 (기본값: 1350원)
    shipping_fee_krw: Optional[float] = None       # 국제배송비 (원)
    platform_fee_rate: Optional[float] = 0.15      # 플랫폼 수수료율 (기본값: 15%)
    discount_rate: Optional[float] = 0.0           # 할인율
    weight_kg: Optional[float] = 0.5               # 상품 무게 (기본값: 0.5kg)
    packaging_fee_krw: Optional[float] = 1000.0    # 포장비 (기본값: 1000원)
    inspection_fee_krw: Optional[float] = 500.0    # 검수비 (기본값: 500원)
    target_margin_rate: Optional[float] = 0.30     # 목표 마진율 (기본값: 30%)

class MarginOutputSchema(BaseModel):
    action: str
    product_data: Optional[Dict[str, Any]] = None
    stats_data: Optional[Dict[str, Any]] = None
    count: Optional[int] = None
    analysis: Optional[Dict[str, Any]] = None
    # 상세 마진 분석 결과
    cost_breakdown: Optional[Dict[str, Any]] = None   # 원가 세부 내역
    margin_analysis: Optional[Dict[str, Any]] = None  # 마진 분석
    final_decision: Optional[str] = None              # 등록 가능/재검토/제외
    risk_warnings: Optional[List[str]] = None         # 리스크 경고

class MarginCheckAgent(BaseHttpAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return MarginInputSchema
    @property
    def output_schema(self) -> Type[BaseModel]:
        return MarginOutputSchema

    def __init__(self, base_url: str = "http://localhost:8050"):
        super().__init__("margin_check")
        self.base_url = base_url

    def _do_execute(self, input_model: MarginInputSchema) -> Dict[str, Any]:
        if input_model.action == 'get_stats':
            res = self.request_api('GET', f"{self.base_url}/api/stats")
            return {"action": "get_stats", "stats_data": res.get('data')}

        elif input_model.action == 'search_products':
            params = {'limit': input_model.limit}
            if input_model.search_query: params['search'] = input_model.search_query
            if input_model.region: params['region'] = input_model.region
            res = self.request_api('GET', f"{self.base_url}/api/products", params=params)
            return {"action": "search_products", "product_data": res.get('data'), "count": res.get('count')}

        elif input_model.action == 'check_margin':
            if not input_model.product_id:
                raise ValueError("product_id is strictly required for check_margin action")

            res = self.request_api('GET', f"{self.base_url}/api/product/{input_model.product_id}")
            data = res.get('data', {})

            # Safe price casting logic using Regex fallback
            price_str = str(data.get('price', '0'))
            cleaned = re.sub(r'[^\d.]', '', price_str)
            try:
                price = float(cleaned) if cleaned else 0.0
            except ValueError:
                price = 0.0

            margin_rate = 0.3
            estimated_margin = price * margin_rate

            return {
                "action": "check_margin",
                "product_data": data,
                "analysis": {
                    "raw_price": price_str,
                    "parsed_price": price,
                    "estimated_margin": estimated_margin,
                    "margin_rate": margin_rate,
                    "recommendation": "통과" if estimated_margin > 5000 else "보류"
                }
            }

        elif input_model.action == 'calculate_margin':
            # 새로운 액션: 실제 원가 구조 기반 마진 계산
            return self._calculate_detailed_margin(input_model)

        else:
            raise ValueError(f"Unknown action: {input_model.action}")

    def _calculate_detailed_margin(self, input_model: MarginInputSchema) -> Dict[str, Any]:
        """실제 원가 구조 기반 상세 마진 계산"""

        # 1. 원가 계산
        source_price_krw = (input_model.source_price_cny or 0) * input_model.exchange_rate

        # 배송비 계산 (무게 기반 - 1kg당 15,000원 가정)
        if input_model.shipping_fee_krw is not None:
            shipping_fee = input_model.shipping_fee_krw
        else:
            shipping_fee = input_model.weight_kg * 15000  # 1kg당 15,000원

        total_cost = (
            source_price_krw +
            shipping_fee +
            input_model.packaging_fee_krw +
            input_model.inspection_fee_krw
        )

        # 2. 손익분기 판매가 계산
        # 손익분기: (총 원가) / (1 - 수수료율 - 할인율)
        fee_and_discount = input_model.platform_fee_rate + input_model.discount_rate
        if fee_and_discount >= 1.0:
            raise ValueError("수수료율 + 할인율이 100%를 초과할 수 없습니다")

        break_even_price = total_cost / (1 - fee_and_discount)

        # 3. 목표 마진 판매가 계산
        # 목표 마진: (총 원가) / (1 - 수수료율 - 할인율 - 목표 마진율)
        target_denominator = 1 - fee_and_discount - input_model.target_margin_rate
        if target_denominator <= 0:
            target_price = break_even_price * 2  # fallback
        else:
            target_price = total_cost / target_denominator

        # 4. 순이익 계산 (목표 가격 기준)
        gross_revenue = target_price
        platform_fee = gross_revenue * input_model.platform_fee_rate
        discount_amount = gross_revenue * input_model.discount_rate
        total_deduction = platform_fee + discount_amount
        net_profit = gross_revenue - total_cost - total_deduction
        net_margin_rate = (net_profit / gross_revenue * 100) if gross_revenue > 0 else 0

        # 5. 리스크 경고 생성
        risk_warnings = []

        # 배송비 비중 경고 (원가 대비 40% 초과)
        shipping_ratio = (shipping_fee / source_price_krw * 100) if source_price_krw > 0 else 0
        if shipping_ratio > 40:
            risk_warnings.append(f"⚠️ 배송비 비중 과다: {shipping_ratio:.1f}% (원가 대비)")

        # 순이익률 경고
        if net_margin_rate < 0:
            risk_warnings.append(f"🔴 적자 위험: 순이익률 {net_margin_rate:.1f}%")
        elif net_margin_rate < 15:
            risk_warnings.append(f"🟡 낮은 마진: 순이익률 {net_margin_rate:.1f}% (권장: 15% 이상)")

        # 총 원가 > 판매가 (설정 오류)
        if total_cost > target_price * 0.9:
            risk_warnings.append("⚠️ 원가가 판매가에 근접 - 가격 구조 재검토 필요")

        # 6. 최종 판정
        if net_margin_rate < 0:
            final_decision = "제외"
        elif net_margin_rate < 15:
            final_decision = "재검토"
        else:
            final_decision = "등록 가능"

        # 7. 결과 반환
        return {
            "action": "calculate_margin",
            "cost_breakdown": {
                "source_price_cny": input_model.source_price_cny,
                "exchange_rate": input_model.exchange_rate,
                "source_price_krw": round(source_price_krw, 0),
                "shipping_fee_krw": round(shipping_fee, 0),
                "packaging_fee_krw": round(input_model.packaging_fee_krw, 0),
                "inspection_fee_krw": round(input_model.inspection_fee_krw, 0),
                "total_cost_krw": round(total_cost, 0),
                "weight_kg": input_model.weight_kg,
                "shipping_ratio_percent": round(shipping_ratio, 1)
            },
            "margin_analysis": {
                "break_even_price": round(break_even_price, 0),
                "target_price": round(target_price, 0),
                "platform_fee_rate": input_model.platform_fee_rate,
                "discount_rate": input_model.discount_rate,
                "platform_fee_amount": round(platform_fee, 0),
                "discount_amount": round(discount_amount, 0),
                "total_deduction": round(total_deduction, 0),
                "net_profit": round(net_profit, 0),
                "net_margin_rate": round(net_margin_rate, 1),
                "target_margin_rate": input_model.target_margin_rate * 100
            },
            "final_decision": final_decision,
            "risk_warnings": risk_warnings
        }

# ---------------------------------------------------------
# Daily Scout Status Agent Schema
# ---------------------------------------------------------

class DailyScoutStatusInputSchema(BaseModel):
    region: str = "us"

class DailyScoutStatusOutputSchema(BaseModel):
    scanned_count: int
    saved_count: int
    region_stats: Dict[str, int]
    last_run_date: str

class DailyScoutStatusAgent(BaseHttpAgent):
    """
    명시적으로 대시보드의 크롤링 상태(Status)만 확인하는 에이전트.
    크롤링 실행(Trigger)을 대리하는 것처럼 행동하지 않습니다.
    """
    @property
    def input_schema(self) -> Type[BaseModel]:
        return DailyScoutStatusInputSchema
    @property
    def output_schema(self) -> Type[BaseModel]:
        return DailyScoutStatusOutputSchema

    def __init__(self, base_url: str = "http://localhost:8050"):
        super().__init__("daily_scout_status")
        self.stats_endpoint = f"{base_url}/api/stats"

    def _do_execute(self, input_model: DailyScoutStatusInputSchema) -> Dict[str, Any]:
        self.logger.info(f"🔎 Daily Scout DB 적재 상태 확인 (지역 권고 무시, 통합 집계 조회)")
        res = self.request_api('GET', self.stats_endpoint)
        data = res.get('data', {})
        
        return {
            "scanned_count": data.get('total', 0),
            "saved_count": data.get('total', 0),
            "region_stats": data.get('region_stats', {}),
            "last_run_date": data.get('date', "unknown")
        }


def register_real_agents():
    """
    에이전트 등록 함수

    Decorator 패턴 도입 후:
    - sourcing, content, pricing은 @register_agent 데코레이터로 자동 등록
    - import만 하면 자동으로 AgentRegistry에 추가됨
    - 아래 에이전트들은 Decorator 미적용 (Legacy 수동 등록)
    """
    from agent_framework import AgentRegistry

    # Decorator 적용 에이전트는 import만으로 자동 등록됨
    from sourcing_agent import SourcingAgent
    from content_agent import ContentAgent
    from pricing_agent import PricingAgent

    # Legacy 에이전트들은 수동 등록 유지 (추후 Decorator 전환 예정)
    registry = AgentRegistry()
    registry.register("image_localization", ImageLocalizationAgent())
    registry.register("margin_check", MarginCheckAgent())
    registry.register("daily_scout_status", DailyScoutStatusAgent())

    return registry
