"""Integration tests for /api/v1/me/tabs."""

from schemas import MAX_LOG_TABS_PER_USER


def _payload(name="Tab", **filters):
    return {"name": name, "filters": filters}


class TestListTabs:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/me/tabs")
        assert resp.status_code == 401

    async def test_empty_for_new_user(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/me/tabs", headers=viewer_session_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateTab:
    async def test_creates_with_incrementing_positions(self, client, viewer_session_headers):
        first = await client.post(
            "/api/v1/me/tabs", json=_payload(name="A"), headers=viewer_session_headers
        )
        second = await client.post(
            "/api/v1/me/tabs", json=_payload(name="B"), headers=viewer_session_headers
        )
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["position"] == 0
        assert second.json()["position"] == 1

    async def test_rejects_empty_name(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/tabs", json={"name": "", "filters": {}}, headers=viewer_session_headers
        )
        assert resp.status_code == 422

    async def test_enforces_limit(self, client, viewer_session_headers, db, viewer_user):
        from models import LogTab

        for i in range(MAX_LOG_TABS_PER_USER):
            db.add(LogTab(user_id=viewer_user.id, name=f"t-{i}", filters={}, position=i))
        await db.flush()

        resp = await client.post(
            "/api/v1/me/tabs", json=_payload(name="too-many"), headers=viewer_session_headers
        )
        assert resp.status_code == 409

    async def test_allows_duplicate_names(self, client, viewer_session_headers):
        """Tabs (unlike saved searches) may share a name."""
        await client.post(
            "/api/v1/me/tabs", json=_payload(name="same"), headers=viewer_session_headers
        )
        resp = await client.post(
            "/api/v1/me/tabs", json=_payload(name="same"), headers=viewer_session_headers
        )
        assert resp.status_code == 201

    async def test_limit_is_admin_configurable(
        self, client, viewer_session_headers, admin_session_headers
    ):
        await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"max_log_tabs_per_user": 1}},
            headers=admin_session_headers,
        )
        first = await client.post(
            "/api/v1/me/tabs", json=_payload(name="A"), headers=viewer_session_headers
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/v1/me/tabs", json=_payload(name="B"), headers=viewer_session_headers
        )
        assert second.status_code == 409

    async def test_zero_limit_means_unlimited(
        self, client, viewer_session_headers, admin_session_headers
    ):
        await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"max_log_tabs_per_user": 0}},
            headers=admin_session_headers,
        )
        for name in ("A", "B", "C", "D"):
            resp = await client.post(
                "/api/v1/me/tabs", json=_payload(name=name), headers=viewer_session_headers
            )
            assert resp.status_code == 201


class TestUpdateTab:
    async def test_rename_and_filters(self, client, viewer_session_headers):
        created = await client.post(
            "/api/v1/me/tabs", json=_payload(name="orig"), headers=viewer_session_headers
        )
        tid = created.json()["id"]
        resp = await client.patch(
            f"/api/v1/me/tabs/{tid}",
            json={"name": "renamed", "filters": {"query": "x", "scope": "global"}},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "renamed"
        assert data["filters"]["scope"] == "global"

    async def test_cannot_update_other_users_tab(
        self, client, viewer_session_headers, admin_session_headers
    ):
        created = await client.post(
            "/api/v1/me/tabs", json=_payload(name="admins"), headers=admin_session_headers
        )
        tid = created.json()["id"]
        resp = await client.patch(
            f"/api/v1/me/tabs/{tid}",
            json={"name": "hijack"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404


class TestReorderTabs:
    async def test_reorder(self, client, viewer_session_headers):
        ids = []
        for name in ("A", "B", "C"):
            r = await client.post(
                "/api/v1/me/tabs", json=_payload(name=name), headers=viewer_session_headers
            )
            ids.append(r.json()["id"])

        # Reverse order
        resp = await client.put(
            "/api/v1/me/tabs/order",
            json={"ids": list(reversed(ids))},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        ordered = [t["id"] for t in resp.json()]
        assert ordered == list(reversed(ids))

    async def test_partial_reorder_appends_unlisted(self, client, viewer_session_headers):
        ids = []
        for name in ("A", "B", "C"):
            r = await client.post(
                "/api/v1/me/tabs", json=_payload(name=name), headers=viewer_session_headers
            )
            ids.append(r.json()["id"])

        # Only mention the last one; the other two should follow in prior order.
        resp = await client.put(
            "/api/v1/me/tabs/order",
            json={"ids": [ids[2]]},
            headers=viewer_session_headers,
        )
        ordered = [t["id"] for t in resp.json()]
        assert ordered[0] == ids[2]
        assert set(ordered[1:]) == {ids[0], ids[1]}

    async def test_ignores_foreign_ids(self, client, viewer_session_headers, admin_session_headers):
        mine = await client.post(
            "/api/v1/me/tabs", json=_payload(name="mine"), headers=viewer_session_headers
        )
        admins = await client.post(
            "/api/v1/me/tabs", json=_payload(name="admins"), headers=admin_session_headers
        )
        resp = await client.put(
            "/api/v1/me/tabs/order",
            json={"ids": [admins.json()["id"], mine.json()["id"]]},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        ordered = [t["id"] for t in resp.json()]
        assert ordered == [mine.json()["id"]]


class TestDeleteTab:
    async def test_delete_own(self, client, viewer_session_headers):
        created = await client.post(
            "/api/v1/me/tabs", json=_payload(), headers=viewer_session_headers
        )
        tid = created.json()["id"]
        resp = await client.delete(f"/api/v1/me/tabs/{tid}", headers=viewer_session_headers)
        assert resp.status_code == 204
        list_resp = await client.get("/api/v1/me/tabs", headers=viewer_session_headers)
        assert list_resp.json() == []
