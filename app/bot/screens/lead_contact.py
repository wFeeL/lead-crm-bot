from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

LEAD_CONTACT_PROMPT_SCREEN_ID = "lead_contact_prompt"


def render_lead_contact_prompt(
    *,
    content: ContentService,
    stack: Sequence[str],
) -> Screen:
    text = (
        "📞 <b>Контакт для связи</b>\n\n"
        "Нажмите кнопку под клавиатурой, чтобы отправить телефон, "
        "или напишите @username / номер вручную."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(screen_id=LEAD_CONTACT_PROMPT_SCREEN_ID, text=text, keyboard=keyboard)


def make_contact_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
