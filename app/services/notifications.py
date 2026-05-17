from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import Settings
from app.core.constants import STATUS_TITLES
from app.core.logging import get_logger
from app.db.models.lead import Lead
from app.services.formatting import format_lead_summary

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    async def notify_new_lead(self, lead: Lead) -> None:
        """Notify admins about a new lead. Includes a button to open ADMIN_LEAD_DETAIL."""
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

    async def notify_client_status(self, lead: Lead) -> None:
        label = STATUS_TITLES.get(lead.status, lead.status)
        try:
            await self.bot.send_message(
                lead.user.telegram_id,
                f"Статус вашей заявки {lead.public_id or lead.id} изменён: {label}.",
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
