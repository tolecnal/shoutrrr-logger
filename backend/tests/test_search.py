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

    async def test_search_invalid_regex_returns_422(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        resp = await client.get(
            "/api/v1/notifications?q=message:/[unclosed/", headers=admin_session_headers
        )
        assert resp.status_code == 422
        assert "Invalid regex pattern" in resp.json()["detail"]

    async def test_search_overlong_regex_returns_422(
        self, client: AsyncClient, admin_session_headers, search_notifications
    ):
        pattern = "a" * 201
        resp = await client.get(
            f"/api/v1/notifications?q=message:/{pattern}/", headers=admin_session_headers
        )
        assert resp.status_code == 422
        assert "too long" in resp.json()["detail"]


class TestSearchExactVsSubstring:
    """Quoted terms match the whole field exactly; unquoted terms are substring
    (with * / ? wildcards)."""

    @pytest.fixture
    async def sender_notifications(self, db: AsyncSession, access_token):
        notifs = [
            Notification(token_id=access_token[1].id, title="A", message="m", sender_name="github"),
            Notification(
                token_id=access_token[1].id, title="B", message="m", sender_name="github-actions"
            ),
        ]
        db.add_all(notifs)
        await db.commit()
        return notifs

    async def test_quoted_value_matches_exact_field(
        self, client: AsyncClient, admin_session_headers, sender_notifications
    ):
        # sender:"github" → only the sender that equals "github".
        resp = await client.get(
            '/api/v1/notifications?q=sender:"github"', headers=admin_session_headers
        )
        assert resp.status_code == 200
        data = resp.json()["items"]
        assert len(data) == 1
        assert data[0]["sender_name"] == "github"

    async def test_quoted_value_is_case_insensitive(
        self, client: AsyncClient, admin_session_headers, sender_notifications
    ):
        resp = await client.get(
            '/api/v1/notifications?q=sender:"GitHub"', headers=admin_session_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    async def test_unquoted_value_is_substring(
        self, client: AsyncClient, admin_session_headers, sender_notifications
    ):
        # sender:github → substring → both "github" and "github-actions".
        resp = await client.get(
            "/api/v1/notifications?q=sender:github", headers=admin_session_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2


class TestSearchRobustness:
    async def test_syntax_error_returns_422(self, client: AsyncClient, admin_session_headers):
        resp = await client.get("/api/v1/notifications?q=(", headers=admin_session_headers)
        assert resp.status_code == 422
        assert "Invalid search query" in resp.json()["detail"]

    async def test_overlong_query_rejected(self, client: AsyncClient, admin_session_headers):
        resp = await client.get(
            "/api/v1/notifications?q=" + ("a" * 2001), headers=admin_session_headers
        )
        assert resp.status_code == 422  # FastAPI max_length validation

    async def test_deeply_nested_query_does_not_500(
        self, client: AsyncClient, admin_session_headers
    ):
        # Many bare terms previously recursed past the limit -> HTTP 500.
        # Now bounded by MAX_TOKENS -> a clean 422, never a 500.
        q = "+".join(["x"] * 400)  # '+' is URL-encoded space-equivalent term separator
        resp = await client.get(f"/api/v1/notifications?q={q}", headers=admin_session_headers)
        assert resp.status_code == 422
        assert "too complex" in resp.json()["detail"]
