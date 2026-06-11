"""Request performance monitoring middleware.

Records one row in api_metric_logs per API request using a fire-and-forget
background task so there is zero added latency on the critical path.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from uuid import uuid4

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "shoutrrr_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "shoutrrr_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

logger = logging.getLogger(__name__)

# Paths excluded from tracking (docs, health, auth, and the performance endpoint itself)
_SKIP_PREFIXES = (
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/health",
    "/api/version",
    "/api/auth/",
    "/api/v1/admin/performance",
)


class PerformanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Only instrument versioned API endpoints; skip non-API and excluded paths
        if not path.startswith("/api/v1/") or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # After routing, scope["route"].path gives us the template
        # (e.g. /api/v1/notifications/{notification_id}) instead of the raw URL.
        route = request.scope.get("route")
        path_template: str = getattr(route, "path", path) if route else "<unmatched>"

        REQUEST_COUNT.labels(
            method=request.method, endpoint=path_template, status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=path_template).observe(
            duration_ms / 1000.0
        )

        asyncio.create_task(
            _persist(
                path=path_template,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        )

        return response


async def _persist(path: str, method: str, status_code: int, duration_ms: float) -> None:
    try:
        from database import async_session_factory  # noqa: PLC0415
        from models import ApiMetricLog  # noqa: PLC0415

        async with async_session_factory() as session:
            session.add(
                ApiMetricLog(
                    id=uuid4(),
                    path=path,
                    method=method,
                    status_code=status_code,
                    duration_ms=duration_ms,
                )
            )
            await session.commit()
    except Exception:
        logger.debug("Failed to persist API metric", exc_info=True)
