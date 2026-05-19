"""NotificationService must wire webhooks + email correctly without breaking Telegram delivery."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.core.config import Settings
from app.services.email import EmailService
from app.services.notifications import NotificationService
from app.services.webhooks import (
    EVENT_LEAD_CREATED,
    EVENT_LEAD_DELETED,
    EVENT_LEAD_STATUS_CHANGED,
    WebhookService,
)


def _make_lead():
    return SimpleNamespace(
        id=42,
        public_id="TG-000042",
        status="new",
        priority="normal",
        title="t",
        description="d",
        contact_name="C",
        contact_phone="+700",
        contact_username="u",
        category=SimpleNamespace(id=1, slug="other", title="Other"),
        user=SimpleNamespace(telegram_id=100, username="u", first_name="C"),
        assigned_admin_id=None,
        created_at=datetime(2026, 5, 19, tzinfo=UTC),
        closed_at=None,
        close_reason=None,
        answers=[],
        files=[],
        comments=[],
    )


@pytest.mark.asyncio
async def test_notify_new_lead_calls_email_and_webhook():
    bot = AsyncMock()
    settings = Settings(admin_ids=[1])

    email = EmailService(settings, send_func=AsyncMock())
    email.send_new_lead = AsyncMock(return_value=True)

    webhooks = WebhookService(settings)
    webhooks.fire_lead_event = AsyncMock(return_value=[True])

    service = NotificationService(bot, settings, webhooks=webhooks, email=email)
    lead = _make_lead()
    await service.notify_new_lead(lead)

    email.send_new_lead.assert_awaited_once_with(lead)
    webhooks.fire_lead_event.assert_awaited_once_with(EVENT_LEAD_CREATED, lead)
    bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_notify_new_lead_swallows_email_errors():
    bot = AsyncMock()
    settings = Settings(admin_ids=[1])

    email = EmailService(settings)
    email.send_new_lead = AsyncMock(side_effect=RuntimeError("SMTP down"))
    webhooks = WebhookService(settings)
    webhooks.fire_lead_event = AsyncMock(return_value=[])

    service = NotificationService(bot, settings, webhooks=webhooks, email=email)
    # Must not raise even though email blew up.
    await service.notify_new_lead(_make_lead())
    bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_notify_new_lead_swallows_webhook_errors():
    bot = AsyncMock()
    settings = Settings(admin_ids=[1])
    email = EmailService(settings)
    email.send_new_lead = AsyncMock(return_value=False)
    webhooks = WebhookService(settings)
    webhooks.fire_lead_event = AsyncMock(side_effect=RuntimeError("hook down"))

    service = NotificationService(bot, settings, webhooks=webhooks, email=email)
    await service.notify_new_lead(_make_lead())  # must not raise


@pytest.mark.asyncio
async def test_notify_client_status_fires_status_changed_webhook():
    bot = AsyncMock()
    settings = Settings(admin_ids=[1])
    email = EmailService(settings)
    webhooks = WebhookService(settings)
    webhooks.fire_lead_event = AsyncMock(return_value=[])

    service = NotificationService(bot, settings, webhooks=webhooks, email=email)
    lead = _make_lead()
    await service.notify_client_status(lead)
    webhooks.fire_lead_event.assert_awaited_once_with(EVENT_LEAD_STATUS_CHANGED, lead)


@pytest.mark.asyncio
async def test_notify_lead_deleted_fires_deleted_webhook_only():
    bot = AsyncMock()
    settings = Settings(admin_ids=[1])
    email = EmailService(settings)
    email.send_new_lead = AsyncMock()  # must NOT be called
    webhooks = WebhookService(settings)
    webhooks.fire_lead_event = AsyncMock(return_value=[])

    service = NotificationService(bot, settings, webhooks=webhooks, email=email)
    await service.notify_lead_deleted(_make_lead())
    webhooks.fire_lead_event.assert_awaited_once()
    args, kwargs = webhooks.fire_lead_event.call_args
    assert args[0] == EVENT_LEAD_DELETED
    email.send_new_lead.assert_not_called()
    # No Telegram message for delete (admin already saw the action).
    bot.send_message.assert_not_called()
