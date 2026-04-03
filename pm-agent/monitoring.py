"""
모니터링 통합 모듈
- Sentry: 에러 트래킹 + 성능 모니터링
- Prometheus: 메트릭 수집
- 구조화된 로깅
"""

import os
import logging
import time
from functools import wraps
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ============================================================
# Sentry Integration
# ============================================================

_sentry_initialized = False


def init_sentry():
    """Sentry SDK 초기화. SENTRY_DSN이 설정된 경우에만 활성화."""
    global _sentry_initialized
    sentry_dsn = os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        logger.info("Sentry DSN not configured — error tracking disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "development"),
            release=os.getenv("APP_VERSION", "2.0.0"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_RATE", "0.1")),
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            send_default_pii=False,
        )
        _sentry_initialized = True
        logger.info("Sentry initialized successfully")
    except ImportError:
        logger.warning("sentry-sdk not installed — pip install sentry-sdk[fastapi]")
    except Exception as e:
        logger.error(f"Sentry initialization failed: {e}")


def capture_exception(error: Exception, context: Optional[dict] = None):
    """Sentry에 예외 전송 (설정된 경우)"""
    if not _sentry_initialized:
        return
    try:
        import sentry_sdk
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_exception(error)
    except Exception:
        pass


# ============================================================
# Prometheus Metrics
# ============================================================

_metrics_initialized = False
_request_count = None
_request_duration = None
_agent_execution_count = None
_agent_execution_duration = None
_active_requests = None


def init_prometheus():
    """Prometheus 메트릭 초기화."""
    global _metrics_initialized, _request_count, _request_duration
    global _agent_execution_count, _agent_execution_duration, _active_requests

    try:
        from prometheus_client import Counter, Histogram, Gauge

        _request_count = Counter(
            "fortimove_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"]
        )
        _request_duration = Histogram(
            "fortimove_http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"]
        )
        _agent_execution_count = Counter(
            "fortimove_agent_executions_total",
            "Total agent executions",
            ["agent_name", "status"]
        )
        _agent_execution_duration = Histogram(
            "fortimove_agent_execution_duration_seconds",
            "Agent execution duration",
            ["agent_name"]
        )
        _active_requests = Gauge(
            "fortimove_active_requests",
            "Currently active requests"
        )

        _metrics_initialized = True
        logger.info("Prometheus metrics initialized")
    except ImportError:
        logger.warning("prometheus-client not installed — metrics disabled")


def track_request(method: str, endpoint: str, status: int, duration: float):
    """HTTP 요청 메트릭 기록."""
    if not _metrics_initialized:
        return
    _request_count.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    _request_duration.labels(method=method, endpoint=endpoint).observe(duration)


def track_agent_execution(agent_name: str, status: str, duration: float):
    """에이전트 실행 메트릭 기록."""
    if not _metrics_initialized:
        return
    _agent_execution_count.labels(agent_name=agent_name, status=status).inc()
    _agent_execution_duration.labels(agent_name=agent_name).observe(duration)


def get_metrics_response():
    """Prometheus /metrics 엔드포인트용 응답 생성."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return generate_latest(), CONTENT_TYPE_LATEST
    except ImportError:
        return b"# prometheus-client not installed\n", "text/plain"


# ============================================================
# Middleware for FastAPI
# ============================================================

def setup_monitoring(app):
    """FastAPI 앱에 모니터링 미들웨어 추가."""
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware

    init_sentry()
    init_prometheus()

    class MonitoringMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start_time = time.time()
            if _active_requests:
                _active_requests.inc()

            try:
                response = await call_next(request)
                duration = time.time() - start_time
                track_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status=response.status_code,
                    duration=duration
                )
                return response
            except Exception as e:
                duration = time.time() - start_time
                track_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status=500,
                    duration=duration
                )
                capture_exception(e, {"path": request.url.path})
                raise
            finally:
                if _active_requests:
                    _active_requests.dec()

    app.add_middleware(MonitoringMiddleware)

    # Prometheus metrics endpoint
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        data, content_type = get_metrics_response()
        return Response(content=data, media_type=content_type)

    logger.info("Monitoring middleware configured")
