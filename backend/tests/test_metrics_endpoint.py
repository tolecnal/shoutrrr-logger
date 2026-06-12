"""Tests for the optional METRICS_TOKEN guard on GET /metrics."""

from config import settings


async def test_metrics_open_when_no_token_configured(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "python_info" in resp.text or "shoutrrr" in resp.text


async def test_metrics_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "scrape-secret")
    resp = await client.get("/metrics")
    assert resp.status_code == 401


async def test_metrics_accepts_correct_token(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "scrape-secret")
    resp = await client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
    assert resp.status_code == 200


async def test_metrics_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "scrape-secret")
    resp = await client.get("/metrics", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401
