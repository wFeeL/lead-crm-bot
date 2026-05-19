"""Outbound email notifications.

Thin wrapper around :mod:`aiosmtplib` for sending plain-text emails to the
admin recipients listed in ``SMTP_ADMIN_EMAILS``. Disabled-by-default: if
``SMTP_HOST`` is empty, every method becomes a cheap no-op.

Designed to be safe to call from request handlers — errors are caught and
logged, never re-raised, so a misconfigured SMTP server can't break the
bot's main flow.
"""

from __future__ import annotations

from email.message import EmailMessage
from typing import Any

import aiosmtplib

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models.lead import Lead

logger = get_logger(__name__)


def _format_lead_email(lead: Lead) -> tuple[str, str]:
    """Return ``(subject, body)`` for a new-lead notification email."""
    subject = f"[Заявка №{lead.public_id or lead.id}] {lead.title}"

    category_title = getattr(getattr(lead, "category", None), "title", None) or "—"
    lines: list[str] = [
        f"Новая заявка №{lead.public_id or lead.id}",
        "",
        f"Категория: {category_title}",
        f"Статус: {lead.status}",
        f"Приоритет: {lead.priority}",
        f"Контакт: {lead.contact_phone or lead.contact_username or '—'}",
        f"Имя: {lead.contact_name or '—'}",
        "",
        "Описание:",
        lead.description or "—",
    ]
    answers = list(getattr(lead, "answers", None) or [])
    if answers:
        lines.append("")
        lines.append("Ответы клиента:")
        for a in answers:
            qtext = getattr(getattr(a, "question", None), "question_text", None) or a.key
            lines.append(f"  • {qtext}: {a.value_text or '—'}")
    return subject, "\n".join(lines)


class EmailService:
    """Async SMTP notifier.

    ``send_raw()`` and ``send_new_lead()`` swallow errors. Caller decides
    whether to await the result — failures are logged and do not propagate.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        send_func: Any | None = None,
    ) -> None:
        self.settings = settings
        # Tests inject a stub send function with the same signature as
        # ``aiosmtplib.send`` so we don't touch a real SMTP server.
        self._send_func = send_func or aiosmtplib.send

    @property
    def enabled(self) -> bool:
        return bool(self.settings.smtp_host) and bool(self.settings.smtp_admin_emails)

    async def send_raw(self, subject: str, body: str, recipients: list[str] | None = None) -> bool:
        """Send a plain-text email. Returns ``True`` on success, ``False`` otherwise."""
        if not self.settings.smtp_host:
            logger.debug("email_disabled (SMTP_HOST is empty)")
            return False
        targets = recipients or list(self.settings.smtp_admin_emails)
        if not targets:
            logger.debug("email_disabled (no admin recipients configured)")
            return False
        sender = self.settings.smtp_from or self.settings.smtp_user or "leadbot@localhost"

        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(targets)
        message["Subject"] = subject
        message.set_content(body)

        try:
            await self._send_func(
                message,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                start_tls=self.settings.smtp_starttls,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — never block the bot on SMTP errors
            logger.warning(
                "email_failed host=%s port=%s recipients=%s error=%s",
                self.settings.smtp_host,
                self.settings.smtp_port,
                targets,
                exc,
            )
            return False

    async def send_new_lead(self, lead: Lead) -> bool:
        """Notify admins about a new lead. No-op when disabled."""
        if not self.enabled:
            return False
        subject, body = _format_lead_email(lead)
        return await self.send_raw(subject, body)
