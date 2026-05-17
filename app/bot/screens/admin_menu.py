from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_MENU_SCREEN_ID = "admin_menu"


class AdminMenuCallback(CallbackData, prefix="adm_menu"):
    action: Literal["new", "contacted", "in_progress", "waiting", "all", "hot", "csv", "stats"]


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
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🆕 Новые", callback_data=AdminMenuCallback(action="new").pack()),
            InlineKeyboardButton(text="📞 Связались", callback_data=AdminMenuCallback(action="contacted").pack()),
        ],
        [
            InlineKeyboardButton(text="🛠 В работе", callback_data=AdminMenuCallback(action="in_progress").pack()),
            InlineKeyboardButton(text="⏳ Ждут", callback_data=AdminMenuCallback(action="waiting").pack()),
        ],
        [
            InlineKeyboardButton(text="🔥 Срочные", callback_data=AdminMenuCallback(action="hot").pack()),
            InlineKeyboardButton(text="📋 Все", callback_data=AdminMenuCallback(action="all").pack()),
        ],
        [
            InlineKeyboardButton(text="📤 CSV", callback_data=AdminMenuCallback(action="csv").pack()),
            InlineKeyboardButton(text="📊 Статистика дня", callback_data=AdminMenuCallback(action="stats").pack()),
        ],
    ])
    return Screen(screen_id=ADMIN_MENU_SCREEN_ID, text=text, keyboard=keyboard)
