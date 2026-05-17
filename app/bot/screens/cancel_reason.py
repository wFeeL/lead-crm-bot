from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

MY_LEAD_CANCEL_REASON_SCREEN_ID = "my_lead_cancel_reason"
CUSTOM_REASON_LABEL = "Своя причина"


class CancelReasonCallback(CallbackData, prefix="cancel_reason"):
    action: Literal["pick", "custom"]
    lead_id: int
    index: int = -1  # -1 for action="custom"


def render_cancel_reason(
    *,
    content: ContentService,
    lead_id: int,
    stack: Sequence[str],
) -> Screen:
    reasons: list[str] = list(content.texts.close_reasons.cancelled or [CUSTOM_REASON_LABEL])
    extra: list[list[InlineKeyboardButton]] = []
    for i, reason in enumerate(reasons):
        if reason == CUSTOM_REASON_LABEL:
            cb = CancelReasonCallback(action="custom", lead_id=lead_id, index=i).pack()
        else:
            cb = CancelReasonCallback(action="pick", lead_id=lead_id, index=i).pack()
        extra.append([InlineKeyboardButton(text=reason, callback_data=cb)])

    text = "🚫 <b>Отмена заявки</b>\n\nВыберите причину или укажите свою:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=MY_LEAD_CANCEL_REASON_SCREEN_ID, text=text, keyboard=keyboard)
