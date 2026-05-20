from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen

ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID = "admin_lead_delete_confirm"


class AdminLeadDeleteCallback(CallbackData, prefix="adm_del"):
    action: Literal["confirm", "cancel"]
    lead_id: int


def render_admin_lead_delete_confirm(
    *,
    public_id: str,
    lead_id: int,
    stack: Sequence[str],
) -> Screen:
    text = (
        f"🗑 <b>Удалить заявку №{public_id}?</b>\n\n"
        "Заявка будет скрыта из всех списков (клиентских и админских) и помечена как удалённая. "
        "Данные сохраняются в БД для истории.\n\n"
        "Это действие нельзя отменить из интерфейса.\n"
        "Чтобы отменить — нажмите «⬅ Назад»."
    )
    # Only the destructive action lives here; canceling is the nav-footer Back —
    # avoids two visually-equivalent "back" buttons on one screen.
    extra = [
        [
            InlineKeyboardButton(
                text="✅ Удалить",
                callback_data=AdminLeadDeleteCallback(action="confirm", lead_id=lead_id).pack(),
            )
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(
        screen_id=ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID,
        text=text,
        keyboard=keyboard,
    )
