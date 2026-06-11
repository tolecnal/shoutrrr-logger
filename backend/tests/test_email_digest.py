"""Regression tests for services/email_digest.py — the periodic alert-digest job.

A previous version used `not UserAlert.email_sent` (and similar) inside a
`.where()` clause. Python evaluates `not <InstrumentedAttribute>` to a plain
``False`` *before* the query is built, which SQLAlchemy compiles to
``WHERE false`` — so the digest job never found any alerts to send.
"""

import asyncio

from models import AlertRule, AppSetting, UserAlert
from services import email_digest


async def _enable_email_alerts(db):
    db.add(AppSetting(key="email_alerts_enabled", value=1))
    db.add(AppSetting(key="smtp_host", value="smtp.example.com"))
    db.add(AppSetting(key="smtp_port", value=587))
    db.add(AppSetting(key="smtp_from", value="alerts@example.com"))
    await db.flush()


async def test_process_email_digests_sends_for_unsent_alerts(
    client, db, viewer_user, sample_notification, monkeypatch
):
    await _enable_email_alerts(db)

    rule = AlertRule(
        user_id=viewer_user.id,
        name="My Rule",
        match_pattern="x",
        send_email=True,
    )
    db.add(rule)
    await db.flush()

    alert = UserAlert(
        user_id=viewer_user.id,
        notification_id=sample_notification.id,
        rule_id=rule.id,
    )
    db.add(alert)
    await db.commit()

    captured = []

    async def _fake_send_email_async(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(email_digest, "send_email_async", _fake_send_email_async)

    await email_digest.process_email_digests()
    await asyncio.sleep(0)  # let the asyncio.create_task'd send run

    assert len(captured) == 1
    assert captured[0]["to_addr"] == viewer_user.email

    await db.refresh(alert)
    assert alert.email_sent is True


async def test_process_email_digests_skips_already_sent_alerts(
    client, db, viewer_user, sample_notification, monkeypatch
):
    await _enable_email_alerts(db)

    rule = AlertRule(
        user_id=viewer_user.id,
        name="My Rule",
        match_pattern="x",
        send_email=True,
    )
    db.add(rule)
    await db.flush()

    alert = UserAlert(
        user_id=viewer_user.id,
        notification_id=sample_notification.id,
        rule_id=rule.id,
        email_sent=True,
    )
    db.add(alert)
    await db.commit()

    captured = []

    async def _fake_send_email_async(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(email_digest, "send_email_async", _fake_send_email_async)

    await email_digest.process_email_digests()
    await asyncio.sleep(0)

    assert captured == []
