"""Unit tests for the email-notification service."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.core.config import Settings
from app.services.email import EmailService, _format_lead_email


def _settings(**overrides) -> Settings:
    base = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "user@example.com",
        "smtp_password": "pw",
        "smtp_from": "bot@example.com",
        "smtp_starttls": True,
        "smtp_admin_emails": ["a@example.com", "b@example.com"],
    }
    base.update(overrides)
    return Settings(**base)


def _make_lead(**overrides):
    base = {
        "id": 7,
        "public_id": "TG-000007",
        "status": "new",
        "priority": "high",
        "title": "Заявка на сайт",
        "description": "Хочу лендинг",
        "contact_name": "Иван",
        "contact_phone": "+79991112233",
        "contact_username": "ivan",
        "category": SimpleNamespace(title="Сайт"),
        "answers": [
            SimpleNamespace(
                key="features",
                value_text="форма заявки + телефон",
                question=SimpleNamespace(question_text="Какие функции?"),
            )
        ],
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------- formatting ----------


def test_format_lead_email_includes_public_id_and_category():
    subject, body = _format_lead_email(_make_lead())
    assert "TG-000007" in subject
    assert "Заявка на сайт" in subject
    assert "Сайт" in body
    assert "+79991112233" in body


def test_format_lead_email_renders_question_text_when_available():
    subject, body = _format_lead_email(_make_lead())
    assert "Какие функции?" in body
    assert "форма заявки + телефон" in body


def test_format_lead_email_handles_missing_relations():
    lead = _make_lead(category=None, answers=None)
    _, body = _format_lead_email(lead)
    # Doesn't crash and still shows the contact line.
    assert "+79991112233" in body


# ---------- disabled mode ----------


@pytest.mark.asyncio
async def test_send_new_lead_is_noop_when_smtp_host_empty():
    sent: list = []

    async def stub(message, **kw):
        sent.append(message)

    service = EmailService(_settings(smtp_host=None), send_func=stub)
    assert not service.enabled
    assert await service.send_new_lead(_make_lead()) is False
    assert sent == []


@pytest.mark.asyncio
async def test_send_new_lead_is_noop_when_admin_emails_empty():
    async def stub(message, **kw):
        raise AssertionError("must not be called")

    service = EmailService(_settings(smtp_admin_emails=[]), send_func=stub)
    assert not service.enabled
    assert await service.send_new_lead(_make_lead()) is False


# ---------- happy path ----------


@pytest.mark.asyncio
async def test_send_new_lead_calls_aiosmtplib_with_correct_args():
    captured = {}

    async def stub(message, **kw):
        captured["to"] = message["To"]
        captured["from"] = message["From"]
        captured["subject"] = message["Subject"]
        captured["body"] = message.get_content()
        captured["kw"] = kw

    service = EmailService(_settings(), send_func=stub)
    ok = await service.send_new_lead(_make_lead())
    assert ok is True
    assert captured["from"] == "bot@example.com"
    assert "a@example.com" in captured["to"]
    assert "b@example.com" in captured["to"]
    assert "TG-000007" in captured["subject"]
    assert "+79991112233" in captured["body"]
    assert captured["kw"]["hostname"] == "smtp.example.com"
    assert captured["kw"]["port"] == 587
    assert captured["kw"]["start_tls"] is True


@pytest.mark.asyncio
async def test_send_raw_with_explicit_recipients_overrides_default():
    captured = {}

    async def stub(message, **kw):
        captured["to"] = message["To"]

    service = EmailService(_settings(), send_func=stub)
    ok = await service.send_raw("S", "B", recipients=["override@example.com"])
    assert ok is True
    assert captured["to"] == "override@example.com"


# ---------- failure mode ----------


@pytest.mark.asyncio
async def test_send_raw_returns_false_on_smtp_exception():
    async def stub(message, **kw):
        raise RuntimeError("SMTP exploded")

    service = EmailService(_settings(), send_func=stub)
    # Failure must NOT propagate (callers can't be allowed to fail).
    result = await service.send_raw("S", "B")
    assert result is False


@pytest.mark.asyncio
async def test_send_falls_back_to_user_when_no_explicit_from():
    captured = {}

    async def stub(message, **kw):
        captured["from"] = message["From"]

    service = EmailService(_settings(smtp_from=None), send_func=stub)
    await service.send_raw("S", "B")
    assert captured["from"] == "user@example.com"


# ---------- enabled flag ----------


def test_enabled_requires_both_host_and_recipients():
    assert EmailService(_settings()).enabled
    assert not EmailService(_settings(smtp_host=None)).enabled
    assert not EmailService(_settings(smtp_admin_emails=[])).enabled
