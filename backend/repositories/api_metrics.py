"""Database access layer for API performance metrics."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ApiMetricLog


class ApiMetricRepository:
    async def summary(self, session: AsyncSession, *, window_hours: int) -> dict:
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        stmt = select(
            func.count().label("total_requests"),
            func.avg(ApiMetricLog.duration_ms).label("avg_ms"),
            func.percentile_cont(0.95).within_group(ApiMetricLog.duration_ms).label("p95_ms"),
            func.sum(case((ApiMetricLog.status_code >= 500, 1), else_=0)).label("error_count"),
        ).where(ApiMetricLog.created_at >= cutoff)

        row = (await session.execute(stmt)).mappings().first()
        if not row or not row["total_requests"]:
            return {"total_requests": 0, "avg_ms": 0.0, "p95_ms": 0.0, "error_rate": 0.0}

        total = row["total_requests"]
        errors = int(row["error_count"] or 0)
        return {
            "total_requests": total,
            "avg_ms": round(float(row["avg_ms"] or 0), 2),
            "p95_ms": round(float(row["p95_ms"] or 0), 2),
            "error_rate": round(errors / total * 100, 2),
        }

    async def by_endpoint(self, session: AsyncSession, *, window_hours: int) -> list[dict]:
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        stmt = (
            select(
                ApiMetricLog.path,
                ApiMetricLog.method,
                func.count().label("request_count"),
                func.avg(ApiMetricLog.duration_ms).label("avg_ms"),
                func.percentile_cont(0.5).within_group(ApiMetricLog.duration_ms).label("p50_ms"),
                func.percentile_cont(0.95).within_group(ApiMetricLog.duration_ms).label("p95_ms"),
                func.percentile_cont(0.99).within_group(ApiMetricLog.duration_ms).label("p99_ms"),
                func.sum(case((ApiMetricLog.status_code >= 500, 1), else_=0)).label("error_count"),
            )
            .where(ApiMetricLog.created_at >= cutoff)
            .group_by(ApiMetricLog.path, ApiMetricLog.method)
            .order_by(func.count().desc())
        )
        rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def by_hour(self, session: AsyncSession, *, window_hours: int) -> list[dict]:
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        hour_trunc = func.date_trunc("hour", ApiMetricLog.created_at)
        stmt = (
            select(
                hour_trunc.label("hour"),
                func.count().label("count"),
                func.avg(ApiMetricLog.duration_ms).label("avg_ms"),
            )
            .where(ApiMetricLog.created_at >= cutoff)
            .group_by(hour_trunc)
            .order_by(hour_trunc)
        )
        rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def delete_older_than(self, session: AsyncSession, cutoff: datetime) -> int:
        result = await session.execute(delete(ApiMetricLog).where(ApiMetricLog.created_at < cutoff))
        return result.rowcount  # type: ignore[return-value]


api_metric_repository = ApiMetricRepository()
