import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def search_notifications(db: AsyncSession, access_token):
    # Create diverse notifications to test advanced search
    notifications = [
        Notification(
            token_id=access_token[1].id,
            title="Database Error",
            message="Connection timeout to 10.0.0.1",
            sender_name="db-service",
            severity="error",
            tags=["env:prod", "team:backend"],
        ),
        Notification(
            token_id=access_token[1].id,
            title="System OK",
            message="All services running normally.",
            sender_name="health-checker",
            severity="info",
            tags=["env:prod"],
        ),
        Notification(
            token_id=access_token[1].id,
            title="Deployment Started",
            message="Deploying v1.2.3 to staging.",
            sender_name="ci-cd",
            severity="info",
            tags=["env:staging", "team:devops"],
        ),
        Notification(
            token_id=access_token[1].id,
            title="Memory Warning",
            message="Node reached 90% memory utilization.",
            sender_name="monitor",
            severity="warning",
            tags=["env:prod", "resource:memory"],
        ),
    ]
    db.add_all(notifications)
    await db.commit()
    return notifications


class TestAdvancedSearch:
    async def test_search_by_title_field(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        resp = await client.get(
            '/api/v1/notifications?q=title:"Memory Warning"', headers=admin_session_headers
        )
        assert resp.status_code == 200
        data = resp.json()["items"]
        assert len(data) == 1
        assert data[0]["title"] == "Memory Warning"

    async def test_search_by_message_regex(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        # Match "timeout to <ip>"
        resp = await client.get(
            "/api/v1/notifications?q=message:/timeout.*10\\.0\\.0\\.1/",
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["items"]
        assert len(data) == 1
        assert data[0]["message"] == "Connection timeout to 10.0.0.1"

    async def test_search_by_tag(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        resp = await client.get(
            "/api/v1/notifications?q=tag:team:backend", headers=admin_session_headers
        )
        assert resp.status_code == 200
        data = resp.json()["items"]
        assert len(data) == 1
        assert "team:backend" in data[0]["tags"]

    async def test_search_by_tag_regex(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        # Match tags starting with "team:"
        resp = await client.get(
            "/api/v1/notifications?q=tag:/team:.*/", headers=admin_session_headers
        )
        assert resp.status_code == 200
        data = resp.json()["items"]
        assert len(data) == 2
        assert any(t.startswith("team:") for t in data[0]["tags"])
        assert any(t.startswith("team:") for t in data[1]["tags"])

    async def test_search_multiple_conditions(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        # mix severity, tag, and free text
        resp = await client.get(
            "/api/v1/notifications?q=severity:info tag:env:prod normally",
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["items"]
        assert len(data) == 1
        assert data[0]["title"] == "System OK"

    async def test_search_sender_field(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        resp = await client.get(
            "/api/v1/notifications?q=sender:ci-cd", headers=admin_session_headers
        )
        assert resp.status_code == 200
        data = resp.json()["items"]
        assert len(data) == 1
        assert data[0]["sender_name"] == "ci-cd"
