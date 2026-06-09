"""Tests for GET /api/v1/admin/performance — auth and query-param validation."""

import pytest
from sqlalchemy.exc import OperationalError


class TestApiPerformanceAuth:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/admin/performance")
        assert resp.status_code == 401

    async def test_viewer_is_forbidden(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/admin/performance", headers=viewer_session_headers)
        assert resp.status_code == 403


class TestApiPerformanceValidation:
    async def test_window_hours_below_minimum_rejected(self, client, admin_session_headers):
        resp = await client.get(
            "/api/v1/admin/performance",
            params={"window_hours": 0},
            headers=admin_session_headers,
        )
        assert resp.status_code == 422

    async def test_window_hours_above_maximum_rejected(self, client, admin_session_headers):
        resp = await client.get(
            "/api/v1/admin/performance",
            params={"window_hours": 169},
            headers=admin_session_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.xfail(
        raises=OperationalError,
        strict=False,
        reason="percentile_cont is PostgreSQL-specific; SQLite test DB raises OperationalError",
    )
    async def test_boundary_values_accepted(self, client, admin_session_headers):
        """1 h and 168 h are at the valid boundaries; FastAPI must not reject them with 422."""
        for hours in (1, 168):
            resp = await client.get(
                "/api/v1/admin/performance",
                params={"window_hours": hours},
                headers=admin_session_headers,
            )
            assert resp.status_code != 422
