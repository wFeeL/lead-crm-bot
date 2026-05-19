from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

MY_LEAD_CANCEL_REASON_SCREEN_ID = "my_lead_cancel_reason"

# Convention: the LAST entry in each close_reasons list is the "custom" prompt.
# Profiles can translate the label freely (e.g. "Своя причина" → "Другая причина" →
# "Other reason") without breaking the branch that opens a free-text prompt.
# Documented in docs/CUSTOMIZATION.md.


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
    reasons: list[str] = list(content.texts.close_reasons.cancelled or [])
    if not reasons:
        # Safety net: ensure a custom-reason path exists even with empty YAML.
        reasons = ["Своя причина"]
    last_index = len(reasons) - 1

    extra: list[list[InlineKeyboardButton]] = []
    for i, reason in enumerate(reasons):
        action = "custom" if i == last_index else "pick"
        cb = CancelReasonCallback(action=action, lead_id=lead_id, index=i).pack()
        extra.append([InlineKeyboardButton(text=reason, callback_data=cb)])

    text = "🚫 <b>Отмена заявки</b>\n\nВыберите причину или укажите свою:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=MY_LEAD_CANCEL_REASON_SCREEN_ID, text=text, keyboard=keyboard)
