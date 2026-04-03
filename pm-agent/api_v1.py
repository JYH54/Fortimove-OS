"""
API v1 라우터
- 모든 기존 엔드포인트를 /api/v1 프리픽스로 그룹화
- 향후 /api/v2 추가 시 하위 호환성 유지
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["API v1"])

# v1 API는 기존 엔드포인트를 래핑
# 현재는 기존 /api/ 엔드포인트가 직접 노출되어 있으므로,
# 점진적으로 이 라우터로 이전 예정

@router.get("/version")
def api_version():
    """API 버전 정보"""
    return {
        "api_version": "v1",
        "app_version": "2.0.0",
        "supported_versions": ["v1"],
        "deprecation_notice": None
    }
