"""Admin-only endpoint for API performance statistics."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import User
from schemas import ApiPerformanceStats
from services.api_metrics import api_metric_service

router = APIRouter(prefix="/admin/performance", tags=["performance"])


@router.get("", response_model=ApiPerformanceStats, summary="API performance statistics")
async def get_performance_stats(
    window_hours: int = Query(24, ge=1, le=168, description="Look-back window (1–168 hours)"),
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiPerformanceStats:
    data = await api_metric_service.get_stats(db, window_hours=window_hours)
    return ApiPerformanceStats.model_validate(data)
