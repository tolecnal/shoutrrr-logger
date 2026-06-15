"""Integration tests for /api/v1/me/saved-searches."""

from schemas import MAX_SAVED_SEARCHES_PER_USER
from services.saved_searches import saved_search_service


def _payload(name="My search", **filters):
    base = {"query": "sender:icinga2", "scope": "all"}
    base.update(filters)
    return {"name": name, "filters": base}


class TestListSavedSearches:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/me/saved-searches")
        assert resp.status_code == 401

    async def test_empty_for_new_user(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/me/saved-searches", headers=viewer_session_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateSavedSearch:
    async def test_creates_and_persists_filters(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/saved-searches",
            json=_payload(query="severity:critical", scope="mine"),
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My search"
        assert data["filters"]["query"] == "severity:critical"
        assert data["filters"]["scope"] == "mine"
        # Defaults fill in for omitted fields
        assert data["filters"]["time_range"] == "all"
        assert data["filters"]["group_values"] == []

    async def test_rejects_empty_name(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/saved-searches",
            json={"name": "", "filters": {}},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 422

    async def test_rejects_invalid_scope(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/saved-searches",
            json={"name": "x", "filters": {"scope": "everything"}},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 422

    async def test_rejects_duplicate_name(self, client, viewer_session_headers):
        await client.post(
            "/api/v1/me/saved-searches",
            json=_payload(name="dup"),
            headers=viewer_session_headers,
        )
        resp = await client.post(
            "/api/v1/me/saved-searches",
            json=_payload(name="dup"),
            headers=viewer_session_headers,
        )
        assert resp.status_code == 409

    async def test_enforces_limit(self, client, viewer_session_headers, db, viewer_user):
        from models import SavedSearch

        for i in range(MAX_SAVED_SEARCHES_PER_USER):
            db.add(SavedSearch(user_id=viewer_user.id, name=f"s-{i}", filters={}))
        await db.flush()

        resp = await client.post(
            "/api/v1/me/saved-searches",
            json=_payload(name="one-too-many"),
            headers=viewer_session_headers,
        )
        assert resp.status_code == 409

    async def test_limit_is_admin_configurable(
        self, client, viewer_session_headers, admin_session_headers
    ):
        await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"max_saved_searches_per_user": 1}},
            headers=admin_session_headers,
        )
        first = await client.post(
            "/api/v1/me/saved-searches",
            json=_payload(name="A"),
            headers=viewer_session_headers,
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/v1/me/saved-searches",
            json=_payload(name="B"),
            headers=viewer_session_headers,
        )
        assert second.status_code == 409


class TestUpdateSavedSearch:
    async def _create(self, client, headers, **kw):
        resp = await client.post("/api/v1/me/saved-searches", json=_payload(**kw), headers=headers)
        return resp.json()

    async def test_rename_and_update_filters(self, client, viewer_session_headers):
        created = await self._create(client, viewer_session_headers, name="orig")
        resp = await client.patch(
            f"/api/v1/me/saved-searches/{created['id']}",
            json={"name": "renamed", "filters": {"query": "severity:warning"}},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "renamed"
        assert data["filters"]["query"] == "severity:warning"

    async def test_rename_collision_rejected(self, client, viewer_session_headers):
        await self._create(client, viewer_session_headers, name="taken")
        other = await self._create(client, viewer_session_headers, name="other")
        resp = await client.patch(
            f"/api/v1/me/saved-searches/{other['id']}",
            json={"name": "taken"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 409

    async def test_nonexistent_returns_404(self, client, viewer_session_headers):
        resp = await client.patch(
            "/api/v1/me/saved-searches/00000000-0000-0000-0000-000000000000",
            json={"name": "x"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404


class TestDeleteSavedSearch:
    async def test_delete_own(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/saved-searches", json=_payload(), headers=viewer_session_headers
        )
        sid = resp.json()["id"]
        resp = await client.delete(
            f"/api/v1/me/saved-searches/{sid}", headers=viewer_session_headers
        )
        assert resp.status_code == 204
        list_resp = await client.get("/api/v1/me/saved-searches", headers=viewer_session_headers)
        assert list_resp.json() == []


class TestIsolation:
    async def test_does_not_leak_across_users(
        self, client, viewer_session_headers, admin_session_headers
    ):
        await client.post(
            "/api/v1/me/saved-searches",
            json=_payload(name="admin-only"),
            headers=admin_session_headers,
        )
        resp = await client.get("/api/v1/me/saved-searches", headers=viewer_session_headers)
        assert resp.json() == []


class TestServiceLayer:
    async def test_to_out_round_trips_filters(self, db, viewer_user):
        from schemas import SavedSearchCreate

        out = await saved_search_service.create_search(
            db,
            SavedSearchCreate.model_validate(
                {"name": "svc", "filters": {"query": "a", "group_values": ["x", "y"]}}
            ),
            viewer_user.id,
        )
        assert out.filters.query == "a"
        assert out.filters.group_values == ["x", "y"]
