"""Tests for plugin usage aggregation (PluginUsageRepository.record_dispatch).

These guard the daily upsert: repeated dispatches for the same
(date, plugin_id, profile_id) must accumulate into a single row, including for
global profiles where user_id is NULL — the case the original 4-column unique
index broke.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from models import PluginUsageDaily
from repositories.plugin_usage import plugin_usage_repo

DAY = datetime(2026, 6, 14, tzinfo=UTC)


@pytest.mark.asyncio
async def test_record_dispatch_aggregates_global_profile(db):
    """Global profile (user_id IS NULL) must upsert into one row, not append."""
    profile_id = uuid4()

    await plugin_usage_repo.record_dispatch(
        db,
        plugin_id="slack",
        profile_id=profile_id,
        user_id=None,
        is_success=True,
        duration_ms=10.0,
        day=DAY,
    )
    await plugin_usage_repo.record_dispatch(
        db,
        plugin_id="slack",
        profile_id=profile_id,
        user_id=None,
        is_success=False,
        duration_ms=30.0,
        day=DAY,
    )
    await db.commit()

    rows = (
        (
            await db.execute(
                select(PluginUsageDaily).where(PluginUsageDaily.profile_id == profile_id)
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1, "global-profile dispatches must aggregate into a single daily row"
    row = rows[0]
    assert row.user_id is None
    assert row.success_count == 1
    assert row.error_count == 1
    assert row.total_duration_ms == 40.0


@pytest.mark.asyncio
async def test_record_dispatch_aggregates_user_profile(db):
    """User-scoped profile dispatches accumulate too."""
    profile_id = uuid4()
    user_id = uuid4()

    for _ in range(3):
        await plugin_usage_repo.record_dispatch(
            db,
            plugin_id="ntfy",
            profile_id=profile_id,
            user_id=user_id,
            is_success=True,
            duration_ms=5.0,
            day=DAY,
        )
    await db.commit()

    rows = (
        (
            await db.execute(
                select(PluginUsageDaily).where(PluginUsageDaily.profile_id == profile_id)
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1
    assert rows[0].success_count == 3
    assert rows[0].error_count == 0
    assert rows[0].total_duration_ms == 15.0
    assert rows[0].user_id == user_id


@pytest.mark.asyncio
async def test_record_dispatch_distinct_profiles_get_distinct_rows(db):
    """Different profiles (or different days) stay separate."""
    p1, p2 = uuid4(), uuid4()
    other_day = datetime(2026, 6, 15, tzinfo=UTC)

    await plugin_usage_repo.record_dispatch(
        db,
        plugin_id="slack",
        profile_id=p1,
        user_id=None,
        is_success=True,
        duration_ms=1.0,
        day=DAY,
    )
    await plugin_usage_repo.record_dispatch(
        db,
        plugin_id="slack",
        profile_id=p2,
        user_id=None,
        is_success=True,
        duration_ms=1.0,
        day=DAY,
    )
    await plugin_usage_repo.record_dispatch(
        db,
        plugin_id="slack",
        profile_id=p1,
        user_id=None,
        is_success=True,
        duration_ms=1.0,
        day=other_day,
    )
    await db.commit()

    rows = (await db.execute(select(PluginUsageDaily))).scalars().all()
    assert len(rows) == 3
