from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_MENU_SCREEN_ID = "admin_menu"


class AdminMenuCallback(CallbackData, prefix="adm_menu"):
    action: Literal[
        "new",
        "contacted",
        "in_progress",
        "waiting",
        "all",
        "hot",
        "csv",
        "stats",
        "search",
        "period",
    ]


def render_admin_menu(
    *,
    content: ContentService,
    status_counts: dict[str, int],
    hot_count: int,
    company_name: str,
) -> Screen:
    text = (
        f"🛠 <b>Админ-панель — {company_name}</b>\n\n"
        f"🆕 Новые: {status_counts.get('new', 0)}\n"
        f"📞 Связались: {status_counts.get('contacted', 0)}\n"
        f"🛠 В работе: {status_counts.get('in_progress', 0)}\n"
        f"⏳ Ждут клиента: {status_counts.get('waiting', 0)}\n\n"
        f"🔥 Срочных и высоких: {hot_count}"
    )

    def _btn(text: str, action: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=text, callback_data=AdminMenuCallback(action=action).pack()
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🆕 Новые", "new"), _btn("📞 Связались", "contacted")],
            [_btn("🛠 В работе", "in_progress"), _btn("⏳ Ждут", "waiting")],
            [_btn("🔥 Срочные", "hot"), _btn("📋 Все", "all")],
            [_btn("🔎 Поиск", "search"), _btn("📅 Период", "period")],
            [_btn("📤 CSV", "csv"), _btn("📊 Статистика дня", "stats")],
        ]
    )
    return Screen(screen_id=ADMIN_MENU_SCREEN_ID, text=text, keyboard=keyboard)
