from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup

from app.bot.states.admin_flow import AdminFlowState
from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen

ADMIN_SEARCH_PROMPT_SCREEN_ID = "admin_search_prompt"


def render_admin_search_prompt(*, stack: Sequence[str]) -> Screen:
    text = (
        "🔎 <b>Поиск заявок</b>\n\n"
        "Отправьте одним сообщением:\n"
        "• часть номера телефона (например <code>9990000</code>)\n"
        "• @username клиента\n"
        "• номер заявки (например <code>TG-000042</code>)\n"
        "• Telegram-ID клиента (только цифры)\n\n"
        "Поиск нечувствителен к регистру. Удалённые заявки в результаты не попадают."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(
        screen_id=ADMIN_SEARCH_PROMPT_SCREEN_ID,
        text=text,
        keyboard=keyboard,
        next_state=AdminFlowState.searching,
    )
