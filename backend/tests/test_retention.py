"""Tests for the hourly retention/purge logic added for api_metric_logs and
audit_logs, plus the api_metrics_retention_days / audit_log_retention_days
settings that drive it (see services.api_metrics / services.audit_logs)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from models import ApiMetricLog, AuditLog
from services.api_metrics import api_metric_service
from services.audit_logs import audit_log_service


class TestApiMetricLogRetention:
    async def test_purge_old_deletes_only_expired_rows(self, db):
        now = datetime.now(UTC)
        old = ApiMetricLog(
            path="/api/v1/notifications",
            method="GET",
            status_code=200,
            duration_ms=12.5,
            created_at=now - timedelta(days=40),
        )
        recent = ApiMetricLog(
            path="/api/v1/notifications",
            method="GET",
            status_code=200,
            duration_ms=10.0,
            created_at=now - timedelta(days=1),
        )
        db.add_all([old, recent])
        await db.flush()

        deleted = await api_metric_service.purge_old(db, retention_days=30)
        await db.flush()

        assert deleted == 1
        remaining = (await db.execute(select(ApiMetricLog))).scalars().all()
        assert [r.id for r in remaining] == [recent.id]

    async def test_purge_old_noop_when_nothing_expired(self, db):
        now = datetime.now(UTC)
        recent = ApiMetricLog(
            path="/api/v1/notifications",
            method="GET",
            status_code=200,
            duration_ms=10.0,
            created_at=now - timedelta(days=1),
        )
        db.add(recent)
        await db.flush()

        deleted = await api_metric_service.purge_old(db, retention_days=30)

        assert deleted == 0


class TestAuditLogRetention:
    async def test_purge_old_deletes_only_expired_rows(self, db):
        now = datetime.now(UTC)
        old = AuditLog(
            actor_username="admin",
            action="user.create",
            target_type="user",
            created_at=now - timedelta(days=400),
        )
        recent = AuditLog(
            actor_username="admin",
            action="user.create",
            target_type="user",
            created_at=now - timedelta(days=1),
        )
        db.add_all([old, recent])
        await db.flush()

        deleted = await audit_log_service.purge_old(db, retention_days=365)
        await db.flush()

        assert deleted == 1
        remaining = (await db.execute(select(AuditLog))).scalars().all()
        assert [r.id for r in remaining] == [recent.id]

    async def test_purge_old_noop_when_nothing_expired(self, db):
        now = datetime.now(UTC)
        recent = AuditLog(
            actor_username="admin",
            action="user.create",
            target_type="user",
            created_at=now - timedelta(days=1),
        )
        db.add(recent)
        await db.flush()

        deleted = await audit_log_service.purge_old(db, retention_days=365)

        assert deleted == 0


class TestRetentionSettingsExposed:
    async def test_admin_settings_include_new_retention_keys(self, client, admin_session_headers):
        resp = await client.get("/api/v1/admin/settings", headers=admin_session_headers)
        assert resp.status_code == 200
        by_key = {s["key"]: s for s in resp.json()}

        assert by_key["api_metrics_retention_days"]["value"] == 30
        assert by_key["api_metrics_retention_days"]["default"] == 30

        assert by_key["audit_log_retention_days"]["value"] == 365
        assert by_key["audit_log_retention_days"]["default"] == 365
