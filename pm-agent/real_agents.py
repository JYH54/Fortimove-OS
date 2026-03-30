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
    action: str = "get_stats"
    product_id: Optional[int] = None
    search_query: Optional[str] = None
    region: Optional[str] = None
    limit: int = 10

class MarginOutputSchema(BaseModel):
    action: str
    product_data: Optional[Dict[str, Any]] = None
    stats_data: Optional[Dict[str, Any]] = None
    count: Optional[int] = None
    analysis: Optional[Dict[str, Any]] = None

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
            cleaned = re.sub(r'[^\d.]', '', price_str) # extract digits and dots only
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

        else:
            raise ValueError(f"Unknown action: {input_model.action}")

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
    from agent_framework import AgentRegistry
    registry = AgentRegistry()
    registry.register("image_localization", ImageLocalizationAgent())
    registry.register("margin_check", MarginCheckAgent())
    registry.register("daily_scout_status", DailyScoutStatusAgent())
    return registry
