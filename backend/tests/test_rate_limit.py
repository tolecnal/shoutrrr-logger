"""Tests for the ingestion rate limiter's sliding-window count.

Covers the fingerprint-deduplication bypass fix: notifications that are
deduplicated (same fingerprint within the dedup window) update an existing
row's `occurrences`/`last_received_at` instead of inserting a new row, so the
rate-limit count must follow `last_received_at` rather than `received_at` —
otherwise repeated duplicates stop counting once the original row's
`received_at` ages out of the rate-limit window.
"""

from datetime import UTC, datetime, timedelta

from models import Notification
from repositories.notifications import notification_repository


class TestCountSinceDedup:
    async def test_deduped_notification_still_counts_after_received_at_ages_out(
        self, db, access_token
    ):
        _, tok = access_token
        now = datetime.now(UTC)

        # First received >60s ago, but repeatedly deduplicated since then:
        # occurrences keeps incrementing and last_received_at keeps moving
        # forward, while received_at stays fixed at the original time.
        n = Notification(
            token_id=tok.id,
            message="dup",
            received_at=now - timedelta(seconds=90),
            last_received_at=now - timedelta(seconds=5),
            occurrences=5,
        )
        db.add(n)
        await db.flush()

        since = now - timedelta(minutes=1)
        count = await notification_repository.count_since(db, token_id=tok.id, since=since)

        # Before the fix, this returned 0 (received_at < since), letting
        # repeated duplicates bypass the rate limiter indefinitely.
        assert count == 5

    async def test_old_non_deduped_notification_excluded(self, db, access_token):
        _, tok = access_token
        now = datetime.now(UTC)

        n = Notification(
            token_id=tok.id,
            message="old",
            received_at=now - timedelta(minutes=5),
            last_received_at=now - timedelta(minutes=5),
            occurrences=1,
        )
        db.add(n)
        await db.flush()

        since = now - timedelta(minutes=1)
        count = await notification_repository.count_since(db, token_id=tok.id, since=since)
        assert count == 0
