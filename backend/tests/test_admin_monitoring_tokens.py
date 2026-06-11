import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models import MonitoringToken


@pytest.mark.asyncio
async def test_create_monitoring_token(client: AsyncClient, admin_session_headers, db):
    resp = await client.post(
        "/api/v1/admin/monitoring-tokens",
        json={"name": "Test Token"},
        headers=admin_session_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Token"
    assert "raw_token" in data
    assert data["is_active"] is True

    stmt = select(MonitoringToken).where(MonitoringToken.id == uuid.UUID(data["id"]))
    result = await db.execute(stmt)
    token = result.scalar_one_or_none()
    assert token is not None
    assert token.name == "Test Token"


@pytest.mark.asyncio
async def test_list_monitoring_tokens(client: AsyncClient, admin_session_headers, db):
    await client.post(
        "/api/v1/admin/monitoring-tokens",
        json={"name": "Test Token"},
        headers=admin_session_headers,
    )
    resp = await client.get("/api/v1/admin/monitoring-tokens", headers=admin_session_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Test Token"
    assert "raw_token" not in data[0]


@pytest.mark.asyncio
async def test_update_monitoring_token(client: AsyncClient, admin_session_headers, db):
    resp = await client.post(
        "/api/v1/admin/monitoring-tokens",
        json={"name": "Test Token"},
        headers=admin_session_headers,
    )
    token_id = resp.json()["id"]

    resp2 = await client.patch(
        f"/api/v1/admin/monitoring-tokens/{token_id}",
        json={"name": "Updated Token", "is_active": False},
        headers=admin_session_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Updated Token"
    assert resp2.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_monitoring_token(client: AsyncClient, admin_session_headers, db):
    resp = await client.post(
        "/api/v1/admin/monitoring-tokens",
        json={"name": "Test Token"},
        headers=admin_session_headers,
    )
    token_id = resp.json()["id"]

    resp2 = await client.delete(
        f"/api/v1/admin/monitoring-tokens/{token_id}", headers=admin_session_headers
    )
    assert resp2.status_code == 204

    resp3 = await client.get("/api/v1/admin/monitoring-tokens", headers=admin_session_headers)
    ids = [t["id"] for t in resp3.json()]
    assert token_id not in ids
