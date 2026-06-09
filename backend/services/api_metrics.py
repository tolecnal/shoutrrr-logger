"""Business logic for API performance metrics."""

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.api_metrics import ApiMetricRepository, api_metric_repository


class ApiMetricService:
    def __init__(self, repo: ApiMetricRepository = api_metric_repository) -> None:
        self._repo = repo

    async def get_stats(self, session: AsyncSession, *, window_hours: int = 24) -> dict:
        summary = await self._repo.summary(session, window_hours=window_hours)
        endpoints = await self._repo.by_endpoint(session, window_hours=window_hours)
        hourly = await self._repo.by_hour(session, window_hours=window_hours)

        by_endpoint = []
        for ep in endpoints:
            count = int(ep["request_count"])
            errors = int(ep["error_count"] or 0)
            by_endpoint.append(
                {
                    "path": ep["path"],
                    "method": ep["method"],
                    "request_count": count,
                    "avg_ms": round(float(ep["avg_ms"] or 0), 2),
                    "p50_ms": round(float(ep["p50_ms"] or 0), 2),
                    "p95_ms": round(float(ep["p95_ms"] or 0), 2),
                    "p99_ms": round(float(ep["p99_ms"] or 0), 2),
                    "error_count": errors,
                    "error_rate": round(errors / count * 100, 2) if count > 0 else 0.0,
                }
            )

        by_hour = [
            {
                "time": h["hour"].isoformat(),
                "count": int(h["count"]),
                "avg_ms": round(float(h["avg_ms"] or 0), 2),
            }
            for h in hourly
        ]

        return {
            **summary,
            "by_endpoint": by_endpoint,
            "by_hour": by_hour,
            "window_hours": window_hours,
        }


api_metric_service = ApiMetricService()
