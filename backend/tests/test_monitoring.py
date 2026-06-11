import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_monitoring_health_unauthorized(client: AsyncClient):
    resp = await client.get("/api/v1/monitoring/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_monitoring_health_authorized(client: AsyncClient, admin_session_headers):
    # 1. Create token
    resp = await client.post(
        "/api/v1/admin/monitoring-tokens",
        json={"name": "Health Monitor"},
        headers=admin_session_headers,
    )
    assert resp.status_code == 201
    raw_token = resp.json()["raw_token"]

    # 2. Test health check
    resp2 = await client.get(
        "/api/v1/monitoring/health", headers={"Authorization": f"Bearer {raw_token}"}
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["db_connected"] is True
    assert "users_total" in data


@pytest.mark.asyncio
async def test_monitoring_health_authorized_with_trailing_space(
    client: AsyncClient, admin_session_headers
):
    resp = await client.post(
        "/api/v1/admin/monitoring-tokens",
        json={"name": "Health Monitor 2"},
        headers=admin_session_headers,
    )
    raw_token = resp.json()["raw_token"]

    # Ensure trailing spaces don't break token verification
    resp2 = await client.get(
        "/api/v1/monitoring/health", headers={"Authorization": f"Bearer {raw_token}   "}
    )
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_monitoring_health_inactive_token(client: AsyncClient, admin_session_headers):
    resp = await client.post(
        "/api/v1/admin/monitoring-tokens",
        json={"name": "Health Monitor 3"},
        headers=admin_session_headers,
    )
    token_data = resp.json()
    raw_token = token_data["raw_token"]
    token_id = token_data["id"]

    # Deactivate token
    await client.patch(
        f"/api/v1/admin/monitoring-tokens/{token_id}",
        json={"is_active": False},
        headers=admin_session_headers,
    )

    # Test health check
    resp2 = await client.get(
        "/api/v1/monitoring/health", headers={"Authorization": f"Bearer {raw_token}"}
    )
    assert resp2.status_code == 401
