"""Unit tests for the outbound webhook dispatcher."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from app.core.config import Settings
from app.services.webhooks import (
    EVENT_LEAD_CREATED,
    EVENT_LEAD_STATUS_CHANGED,
    WebhookService,
    _lead_payload,
    _sign,
)


def _settings(**overrides) -> Settings:
    base = {
        "webhook_urls": ["https://example.invalid/hook"],
        "webhook_secret": "topsecret",
        "webhook_timeout_seconds": 5.0,
        "webhook_max_retries": 3,
    }
    base.update(overrides)
    return Settings(**base)


def _make_lead(**overrides):
    base = {
        "id": 42,
        "public_id": "TG-000042",
        "status": "new",
        "priority": "normal",
        "title": "T",
        "description": "D",
        "contact_name": "Client",
        "contact_phone": "+79990000000",
        "contact_username": "client",
        "category": SimpleNamespace(id=1, slug="other", title="Other"),
        "user": SimpleNamespace(telegram_id=100, username="client", first_name="Client"),
        "assigned_admin_id": None,
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        "closed_at": None,
        "close_reason": None,
        "answers": [
            SimpleNamespace(
                key="goal",
                value_text="нужен бот",
                question=SimpleNamespace(question_text="Что нужно?"),
            )
        ],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------- pure helpers ----------


def test_sign_returns_hex_hmac_sha256():
    body = b'{"event":"x"}'
    signature = _sign(body, "secret")
    expected = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert signature == expected


def test_sign_returns_none_when_no_secret():
    assert _sign(b"x", None) is None
    assert _sign(b"x", "") is None


def test_lead_payload_serializes_all_relevant_fields():
    lead = _make_lead()
    payload = _lead_payload(lead)
    assert payload["public_id"] == "TG-000042"
    assert payload["category"]["slug"] == "other"
    assert payload["user"]["telegram_id"] == 100
    assert payload["created_at"].startswith("2026-05-19T10:00")
    assert payload["answers"][0]["question_text"] == "Что нужно?"


def test_lead_payload_handles_missing_relations():
    lead = _make_lead(user=None, category=None, answers=None)
    payload = _lead_payload(lead)
    assert payload["user"] is None
    assert payload["category"] is None
    assert payload["answers"] == []


# ---------- disabled mode ----------


@pytest.mark.asyncio
async def test_fire_is_noop_when_no_urls_configured():
    service = WebhookService(_settings(webhook_urls=[]))
    assert not service.enabled
    assert await service.fire(EVENT_LEAD_CREATED, {}) == ()


# ---------- happy path with MockTransport ----------


@pytest.mark.asyncio
async def test_fire_posts_signed_envelope_to_each_url():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        s = _settings(webhook_urls=["https://a.invalid/h", "https://b.invalid/h"])
        service = WebhookService(s, client=client)
        results = await service.fire(EVENT_LEAD_CREATED, {"foo": "bar"})

    assert results == [True, True]
    assert {req.url.host for req in seen} == {"a.invalid", "b.invalid"}
    # Envelope shape.
    body = json.loads(seen[0].content)
    assert body["event"] == EVENT_LEAD_CREATED
    assert body["data"] == {"foo": "bar"}
    assert "occurred_at" in body
    # HMAC signature header.
    sig_header = seen[0].headers["X-Webhook-Signature"]
    assert sig_header.startswith("sha256=")
    expected = hmac.new(b"topsecret", seen[0].content, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected}"
    # Event header echoed.
    assert seen[0].headers["X-Webhook-Event"] == EVENT_LEAD_CREATED


@pytest.mark.asyncio
async def test_fire_omits_signature_header_when_secret_missing():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = WebhookService(_settings(webhook_secret=None), client=client)
        await service.fire(EVENT_LEAD_CREATED, {})

    assert "X-Webhook-Signature" not in seen[0].headers


# ---------- retries ----------


@pytest.mark.asyncio
async def test_fire_retries_on_5xx_then_succeeds(monkeypatch):
    # Avoid real sleep during exponential backoff.
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    attempts: list[int] = []

    def handler(req):
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(500)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = WebhookService(_settings(webhook_max_retries=3), client=client)
        results = await service.fire(EVENT_LEAD_STATUS_CHANGED, {})

    assert results == [True]
    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_fire_does_not_retry_4xx(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    calls: list[int] = []

    def handler(req):
        calls.append(1)
        return httpx.Response(400)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = WebhookService(_settings(webhook_max_retries=5), client=client)
        results = await service.fire(EVENT_LEAD_CREATED, {})

    assert results == [False]
    assert len(calls) == 1  # 4xx terminates immediately


@pytest.mark.asyncio
async def test_fire_returns_false_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    def handler(req):
        raise httpx.ConnectError("boom", request=req)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = WebhookService(_settings(webhook_max_retries=2), client=client)
        results = await service.fire(EVENT_LEAD_CREATED, {})

    assert results == [False]


# ---------- fire_lead_event wrapper ----------


@pytest.mark.asyncio
async def test_fire_lead_event_uses_lead_payload():
    captured: list[bytes] = []

    def handler(req):
        captured.append(req.content)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = WebhookService(_settings(), client=client)
        await service.fire_lead_event(EVENT_LEAD_CREATED, _make_lead())

    body = json.loads(captured[0])
    assert body["data"]["public_id"] == "TG-000042"
    assert body["data"]["user"]["telegram_id"] == 100
