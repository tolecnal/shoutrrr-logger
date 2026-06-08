"""
Integration tests for GET /api/v1/notifications — pagination and search.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification


async def _seed(
    db: AsyncSession, token_id, count: int, base_msg: str = "msg"
) -> list[Notification]:
    rows = []
    for i in range(count):
        n = Notification(
            token_id=token_id,
            sender_name="host",
            message=f"{base_msg}-{i}",
        )
        db.add(n)
        rows.append(n)
    await db.flush()
    return rows


class TestListNotifications:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 401

    async def test_empty_returns_zero(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/notifications", headers=viewer_session_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["pages"] == 1

    async def test_pagination_page_size(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        await _seed(db, tok.id, 25)
        resp = await client.get(
            "/api/v1/notifications",
            params={"page": 1, "page_size": 10},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["pages"] == 3

    async def test_second_page(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        await _seed(db, tok.id, 5)
        resp = await client.get(
            "/api/v1/notifications",
            params={"page": 2, "page_size": 3},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2  # 5 total, 3 on page 1 → 2 on page 2

    async def test_search_matches_message(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        db.add(Notification(token_id=tok.id, message="container updated successfully"))
        db.add(Notification(token_id=tok.id, message="startup complete"))
        await db.flush()
        resp = await client.get(
            "/api/v1/notifications",
            params={"q": "updated"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "updated" in data["items"][0]["message"]

    async def test_search_matches_title(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        db.add(Notification(token_id=tok.id, message="some message", title="Deployment Error"))
        db.add(Notification(token_id=tok.id, message="other message", title="Success"))
        await db.flush()
        resp = await client.get(
            "/api/v1/notifications",
            params={"q": "Error"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Deployment Error"

    async def test_viewer_can_read(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/notifications", headers=viewer_session_headers)
        assert resp.status_code == 200

    async def test_admin_can_read(self, client, admin_session_headers):
        resp = await client.get("/api/v1/notifications", headers=admin_session_headers)
        assert resp.status_code == 200


class TestGetNotification:
    async def test_get_existing(self, client, viewer_session_headers, sample_notification):
        resp = await client.get(
            f"/api/v1/notifications/{sample_notification.id}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(sample_notification.id)
        assert data["message"] == sample_notification.message

    async def test_get_nonexistent_returns_404(self, client, viewer_session_headers):
        resp = await client.get(
            "/api/v1/notifications/00000000-0000-0000-0000-000000000000",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404

    async def test_custom_fields_populated(
        self, client, viewer_session_headers, sample_notification
    ):
        """sample_notification has a raw_payload with hostname and severity."""
        resp = await client.get(
            f"/api/v1/notifications/{sample_notification.id}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["custom_fields"]["hostname"] == "test-host"
        assert data["custom_fields"]["severity"] == "info"
