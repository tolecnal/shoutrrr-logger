"""
Tests for the Gmail-style selected-delete endpoint and its permission model:

  POST /api/v1/notifications/delete  {ids: [...]}

Permission model (deletability, narrower than visibility):
  - admins may delete anything they can see
  - viewers may delete ONLY notifications from their own non-global tokens —
    not global, not orphaned, not other users' private — even though they can
    *see* global notifications.

Also covers `can_delete` on the list response and the tightening of the
existing filter-based bulk delete for viewers.
"""

import pytest
from sqlalchemy import select

from auth import generate_raw_token, hash_token
from models import AccessToken, Notification


async def _notif(db, token_id, *, title="n", message="m") -> Notification:
    n = Notification(token_id=token_id, sender_name="s", title=title, message=message)
    db.add(n)
    await db.flush()
    await db.refresh(n)
    return n


@pytest.fixture
async def global_token(db, admin_user) -> AccessToken:
    tok = AccessToken(
        user_id=admin_user.id,
        name="global",
        token_hash=hash_token(generate_raw_token()),
        is_global=True,
    )
    db.add(tok)
    await db.flush()
    return tok


@pytest.fixture
async def viewer_private_token(db, viewer_user) -> AccessToken:
    tok = AccessToken(
        user_id=viewer_user.id,
        name="viewer-priv",
        token_hash=hash_token(generate_raw_token()),
        is_global=False,
    )
    db.add(tok)
    await db.flush()
    return tok


@pytest.fixture
async def other_private_token(db, admin_user) -> AccessToken:
    # A private token owned by someone other than the viewer.
    tok = AccessToken(
        user_id=admin_user.id,
        name="other-priv",
        token_hash=hash_token(generate_raw_token()),
        is_global=False,
    )
    db.add(tok)
    await db.flush()
    return tok


async def _exists(db, nid) -> bool:
    return (
        await db.execute(select(Notification.id).where(Notification.id == nid))
    ).scalar_one_or_none() is not None


class TestSelectedDeletePermissions:
    async def test_viewer_can_delete_own_private(
        self, client, db, viewer_session_headers, viewer_private_token
    ):
        n = await _notif(db, viewer_private_token.id)
        await db.commit()
        resp = await client.post(
            "/api/v1/notifications/delete",
            json={"ids": [str(n.id)]},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"requested": 1, "deleted": 1}
        assert not await _exists(db, n.id)

    async def test_viewer_cannot_delete_global(
        self, client, db, viewer_session_headers, global_token
    ):
        n = await _notif(db, global_token.id)
        await db.commit()
        resp = await client.post(
            "/api/v1/notifications/delete",
            json={"ids": [str(n.id)]},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"requested": 1, "deleted": 0}  # skipped
        assert await _exists(db, n.id)  # still there

    async def test_viewer_cannot_delete_other_users_private(
        self, client, db, viewer_session_headers, other_private_token
    ):
        n = await _notif(db, other_private_token.id)
        await db.commit()
        resp = await client.post(
            "/api/v1/notifications/delete",
            json={"ids": [str(n.id)]},
            headers=viewer_session_headers,
        )
        assert resp.json() == {"requested": 1, "deleted": 0}
        assert await _exists(db, n.id)

    async def test_viewer_cannot_delete_orphaned(self, client, db, viewer_session_headers):
        n = await _notif(db, None)  # token deleted → orphaned
        await db.commit()
        resp = await client.post(
            "/api/v1/notifications/delete",
            json={"ids": [str(n.id)]},
            headers=viewer_session_headers,
        )
        assert resp.json() == {"requested": 1, "deleted": 0}
        assert await _exists(db, n.id)

    async def test_viewer_mixed_selection_deletes_only_permitted(
        self, client, db, viewer_session_headers, viewer_private_token, global_token
    ):
        mine = await _notif(db, viewer_private_token.id)
        glob = await _notif(db, global_token.id)
        await db.commit()
        resp = await client.post(
            "/api/v1/notifications/delete",
            json={"ids": [str(mine.id), str(glob.id)]},
            headers=viewer_session_headers,
        )
        assert resp.json() == {"requested": 2, "deleted": 1}
        assert not await _exists(db, mine.id)
        assert await _exists(db, glob.id)

    async def test_admin_can_delete_global_and_others(
        self, client, db, admin_session_headers, global_token, viewer_private_token
    ):
        glob = await _notif(db, global_token.id)
        priv = await _notif(db, viewer_private_token.id)
        await db.commit()
        resp = await client.post(
            "/api/v1/notifications/delete",
            json={"ids": [str(glob.id), str(priv.id)]},
            headers=admin_session_headers,
        )
        assert resp.json() == {"requested": 2, "deleted": 2}
        assert not await _exists(db, glob.id)
        assert not await _exists(db, priv.id)


class TestSelectedDeleteValidation:
    async def test_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/notifications/delete", json={"ids": ["00000000-0000-0000-0000-000000000000"]}
        )
        assert resp.status_code == 401

    async def test_empty_ids_rejected(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/notifications/delete", json={"ids": []}, headers=viewer_session_headers
        )
        assert resp.status_code == 422

    async def test_too_many_ids_rejected(self, client, viewer_session_headers):
        ids = ["00000000-0000-0000-0000-000000000000"] * 501
        resp = await client.post(
            "/api/v1/notifications/delete", json={"ids": ids}, headers=viewer_session_headers
        )
        assert resp.status_code == 422


class TestCanDeleteFlag:
    async def test_list_marks_can_delete_per_row(
        self, client, db, viewer_session_headers, viewer_private_token, global_token
    ):
        mine = await _notif(db, viewer_private_token.id, title="mine")
        glob = await _notif(db, global_token.id, title="glob")
        await db.commit()
        resp = await client.get("/api/v1/notifications", headers=viewer_session_headers)
        assert resp.status_code == 200
        by_id = {item["id"]: item["can_delete"] for item in resp.json()["items"]}
        assert by_id[str(mine.id)] is True
        assert by_id[str(glob.id)] is False

    async def test_admin_can_delete_everything_in_list(
        self, client, db, admin_session_headers, global_token, viewer_private_token
    ):
        glob = await _notif(db, global_token.id)
        priv = await _notif(db, viewer_private_token.id)
        await db.commit()
        resp = await client.get("/api/v1/notifications", headers=admin_session_headers)
        by_id = {item["id"]: item["can_delete"] for item in resp.json()["items"]}
        assert by_id[str(glob.id)] is True
        assert by_id[str(priv.id)] is True


class TestBulkDeleteTightening:
    async def test_viewer_bulk_delete_skips_global(
        self, client, db, viewer_session_headers, viewer_private_token, global_token
    ):
        """A viewer's filter-based bulk delete must not remove global
        notifications it can see — only its own deletable rows."""
        mine = await _notif(db, viewer_private_token.id)
        glob = await _notif(db, global_token.id)
        await db.commit()

        resp = await client.request(
            "DELETE", "/api/v1/notifications", headers=viewer_session_headers
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1
        assert not await _exists(db, mine.id)
        assert await _exists(db, glob.id)  # global survived
