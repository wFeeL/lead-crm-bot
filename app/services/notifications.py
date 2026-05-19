from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import Settings
from app.core.constants import STATUS_TITLES
from app.core.logging import get_logger
from app.db.models.lead import Lead
from app.services.email import EmailService
from app.services.formatting import format_lead_summary
from app.services.webhooks import (
    EVENT_LEAD_CREATED,
    EVENT_LEAD_DELETED,
    EVENT_LEAD_STATUS_CHANGED,
    WebhookService,
)

logger = get_logger(__name__)


class NotificationService:
    """Fan-out for outbound channels: Telegram + (optional) webhooks + email.

    Webhook and email services are constructed lazily and become no-ops if
    their configuration is empty, so this class is safe to use even in
    environments where only Telegram is configured.
    """

    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        *,
        webhooks: WebhookService | None = None,
        email: EmailService | None = None,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self._webhooks = webhooks
        self._email = email

    @property
    def webhooks(self) -> WebhookService:
        if self._webhooks is None:
            self._webhooks = WebhookService(self.settings)
        return self._webhooks

    @property
    def email(self) -> EmailService:
        if self._email is None:
            self._email = EmailService(self.settings)
        return self._email

    async def notify_new_lead(self, lead: Lead) -> None:
        """Notify admins about a new lead (Telegram + optional email + webhook)."""
        from app.bot.screens.admin_lead_list import AdminLeadListCallback

        text = f"Новая заявка\n\n{format_lead_summary(lead)}"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Открыть заявку",
                        callback_data=AdminLeadListCallback(
                            action="open", lead_id=lead.id, page=1
                        ).pack(),
                    )
                ]
            ]
        )

        targets = list(self.settings.admin_ids)
        if self.settings.manager_group_id is not None:
            targets.append(self.settings.manager_group_id)
        for target in targets:
            try:
                await self.bot.send_message(target, text, reply_markup=keyboard)
            except Exception as exc:
                logger.warning(
                    "admin_notification_failed target=%s lead_id=%s error=%s",
                    target,
                    lead.id,
                    exc,
                )

        # Side channels — each one is a no-op if disabled. Failures are swallowed
        # at the service layer so a downed SMTP / receiver can't kill lead creation.
        try:
            await self.email.send_new_lead(lead)
        except Exception as exc:  # noqa: BLE001 — belt-and-braces
            logger.warning("email_send_unexpected_error lead_id=%s error=%s", lead.id, exc)
        try:
            await self.webhooks.fire_lead_event(EVENT_LEAD_CREATED, lead)
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook_fire_unexpected_error lead_id=%s error=%s", lead.id, exc)

    async def notify_client_status(self, lead: Lead) -> None:
        label = STATUS_TITLES.get(lead.status, lead.status)
        try:
            await self.bot.send_message(
                lead.user.telegram_id,
                f"Статус вашей заявки {lead.public_id or lead.id} изменён: {label}.",
            )
        except Exception as exc:
            logger.warning("client_notification_failed lead_id=%s error=%s", lead.id, exc)
        # Notify external systems about the status change.
        try:
            await self.webhooks.fire_lead_event(EVENT_LEAD_STATUS_CHANGED, lead)
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook_fire_unexpected_error lead_id=%s error=%s", lead.id, exc)

    async def notify_client_comment(self, lead: Lead, comment_text: str) -> None:
        try:
            await self.bot.send_message(
                lead.user.telegram_id,
                f"Комментарий к заявке {lead.public_id or lead.id}:\n\n{comment_text}",
            )
        except Exception as exc:
            logger.warning("client_comment_notification_failed lead_id=%s error=%s", lead.id, exc)

    async def notify_lead_deleted(self, lead: Lead) -> None:
        """Webhook-only notification — admins already saw the action in the UI."""
        try:
            await self.webhooks.fire_lead_event(EVENT_LEAD_DELETED, lead)
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook_fire_unexpected_error lead_id=%s error=%s", lead.id, exc)
