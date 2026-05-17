from aiogram import Bot

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models.lead import Lead
from app.services.formatting import format_lead_summary

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    async def notify_new_lead(self, lead: Lead, reply_markup=None) -> None:
        text = f"Новая заявка\n\n{format_lead_summary(lead)}"
        targets = list(self.settings.admin_ids)
        if self.settings.manager_group_id is not None:
            targets.append(self.settings.manager_group_id)
        for target in targets:
            try:
                await self.bot.send_message(target, text, reply_markup=reply_markup)
            except Exception as exc:
                logger.warning(
                    "admin_notification_failed target=%s lead_id=%s error=%s",
                    target,
                    lead.id,
                    exc,
                )

    async def notify_client_status(self, lead: Lead) -> None:
        try:
            await self.bot.send_message(
                lead.user.telegram_id,
                f"Статус вашей заявки {lead.public_id or lead.id} изменен: {lead.status}.",
            )
        except Exception as exc:
            logger.warning("client_notification_failed lead_id=%s error=%s", lead.id, exc)

    async def notify_client_comment(self, lead: Lead, comment_text: str) -> None:
        try:
            await self.bot.send_message(
                lead.user.telegram_id,
                f"Комментарий к заявке {lead.public_id or lead.id}:\n\n{comment_text}",
            )
        except Exception as exc:
            logger.warning("client_comment_notification_failed lead_id=%s error=%s", lead.id, exc)
