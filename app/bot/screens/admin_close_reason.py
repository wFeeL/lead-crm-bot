from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_CLOSE_REASON_SCREEN_ID = "admin_close_reason"
CUSTOM_REASON_LABEL = "Своя причина"


class AdminCloseReasonCallback(CallbackData, prefix="adm_close"):
    action: Literal["pick", "custom", "skip"]
    lead_id: int
    target_status: str
    index: int = -1


def render_admin_close_reason(
    *,
    content: ContentService,
    lead_id: int,
    target_status: str,  # "done" or "rejected"
    stack: Sequence[str],
) -> Screen:
    is_rejected = target_status == "rejected"
    reasons = (
        content.texts.close_reasons.rejected if is_rejected else content.texts.close_reasons.done
    )
    extra = []
    for i, reason in enumerate(reasons):
        cb_action = "custom" if reason == CUSTOM_REASON_LABEL else "pick"
        extra.append(
            [
                InlineKeyboardButton(
                    text=reason,
                    callback_data=AdminCloseReasonCallback(
                        action=cb_action,
                        lead_id=lead_id,
                        target_status=target_status,
                        index=i,
                    ).pack(),
                )
            ]
        )
    if not is_rejected:
        # DONE: optional reason — allow skipping.
        extra.append(
            [
                InlineKeyboardButton(
                    text="⏭ Без причины",
                    callback_data=AdminCloseReasonCallback(
                        action="skip",
                        lead_id=lead_id,
                        target_status=target_status,
                    ).pack(),
                )
            ]
        )

    intro = "Укажите причину отказа" if is_rejected else "Краткое резюме (можно пропустить)"
    text = f"{intro}:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_CLOSE_REASON_SCREEN_ID, text=text, keyboard=keyboard)
