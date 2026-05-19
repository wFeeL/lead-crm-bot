"""Outbound webhook dispatcher.

Fires JSON POSTs at one or more endpoints on lead lifecycle events. The
receiver can verify the request authenticity via the ``X-Webhook-Signature``
header (hex HMAC-SHA256 over the body, using ``WEBHOOK_SECRET``).

Configured entirely through env (``WEBHOOK_URLS``, ``WEBHOOK_SECRET``,
``WEBHOOK_TIMEOUT_SECONDS``, ``WEBHOOK_MAX_RETRIES``). Empty ``WEBHOOK_URLS``
disables dispatch — the service becomes a cheap no-op.

Designed to **never** block the bot's main flow: each dispatch is awaited
internally but wrapped in ``try/except`` so a downed receiver can't fail a
lead creation. Use ``fire(...)`` from a service layer, not from a handler.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models.lead import Lead

logger = get_logger(__name__)


# Stable string identifiers — these are the receiver's contract.
EVENT_LEAD_CREATED = "lead.created"
EVENT_LEAD_STATUS_CHANGED = "lead.status_changed"
EVENT_LEAD_DELETED = "lead.deleted"


def _lead_payload(lead: Lead) -> dict[str, Any]:
    """Serialise a Lead to a stable JSON-friendly dict for receivers."""
    user = getattr(lead, "user", None)
    return {
        "id": lead.id,
        "public_id": lead.public_id,
        "status": lead.status,
        "priority": lead.priority,
        "title": lead.title,
        "description": lead.description,
        "contact_name": lead.contact_name,
        "contact_phone": lead.contact_phone,
        "contact_username": lead.contact_username,
        "category": {
            "id": getattr(lead.category, "id", None),
            "slug": getattr(lead.category, "slug", None),
            "title": getattr(lead.category, "title", None),
        }
        if getattr(lead, "category", None)
        else None,
        "user": {
            "telegram_id": getattr(user, "telegram_id", None),
            "username": getattr(user, "username", None),
            "first_name": getattr(user, "first_name", None),
        }
        if user is not None
        else None,
        "assigned_admin_id": getattr(lead, "assigned_admin_id", None),
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "closed_at": lead.closed_at.isoformat() if lead.closed_at else None,
        "close_reason": lead.close_reason,
        "answers": [
            {
                "key": a.key,
                "question_text": getattr(getattr(a, "question", None), "question_text", None),
                "value_text": a.value_text,
            }
            for a in getattr(lead, "answers", None) or []
        ],
    }


def _sign(body: bytes, secret: str | None) -> str | None:
    if not secret:
        return None
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff: 0.5s, 1s, 2s, ... — cap at 8s."""
    return min(0.5 * (2**attempt), 8.0)


class WebhookService:
    """Async webhook dispatcher with HMAC signing and exponential-backoff retries."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client  # tests inject a stub client

    @property
    def enabled(self) -> bool:
        return bool(self.settings.webhook_urls)

    def _make_envelope(self, event: str, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "event": event,
            "occurred_at": datetime.now(UTC).isoformat(),
            "data": data,
        }

    async def _post_one(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> bool:
        """Single endpoint with retries. Returns True on 2xx, False after exhausting."""
        last_exc: Exception | None = None
        for attempt in range(self.settings.webhook_max_retries):
            try:
                resp = await client.post(url, content=body, headers=headers)
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exc = exc
            else:
                if 200 <= resp.status_code < 300:
                    return True
                if 500 <= resp.status_code < 600:
                    # Server error — retry. Otherwise treat 4xx as terminal.
                    last_exc = httpx.HTTPStatusError(
                        f"server returned {resp.status_code}", request=resp.request, response=resp
                    )
                else:
                    logger.warning(
                        "webhook_dropped url=%s status=%d (4xx — not retrying)",
                        url,
                        resp.status_code,
                    )
                    return False
            if attempt + 1 < self.settings.webhook_max_retries:
                await asyncio.sleep(_backoff_seconds(attempt))
        logger.warning(
            "webhook_failed url=%s after %d attempts: %s",
            url,
            self.settings.webhook_max_retries,
            last_exc,
        )
        return False

    async def fire(self, event: str, data: dict[str, Any]) -> Sequence[bool]:
        """POST to every configured endpoint. Returns one result per endpoint."""
        if not self.enabled:
            return ()

        envelope = self._make_envelope(event, data)
        body = json.dumps(envelope, ensure_ascii=False, default=str).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": f"{self.settings.app_name}/leadbot-webhook",
            "X-Webhook-Event": event,
        }
        signature = _sign(body, self.settings.webhook_secret)
        if signature:
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        async def _run(client: httpx.AsyncClient) -> list[bool]:
            return await asyncio.gather(
                *(self._post_one(client, url, body, headers) for url in self.settings.webhook_urls)
            )

        if self._client is not None:
            return await _run(self._client)
        async with httpx.AsyncClient(timeout=self.settings.webhook_timeout_seconds) as client:
            return await _run(client)

    async def fire_lead_event(self, event: str, lead: Lead) -> Sequence[bool]:
        """Convenience wrapper — serialises ``lead`` then delegates to :meth:`fire`."""
        return await self.fire(event, _lead_payload(lead))
