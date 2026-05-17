from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.states.support import SupportState
from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

SUPPORT_SCREEN_ID = "support"
SUPPORT_WRITING_SCREEN_ID = "support_writing"


class SupportCallback(CallbackData, prefix="support"):
    action: Literal["write"]


def render_support(*, content: ContentService, stack: Sequence[str]) -> Screen:
    brand = content.brand
    text = (
        f"💬 <b>Связаться с менеджером</b>\n\n"
        f"{brand.support_intro}\n\n"
        f"Менеджер: {brand.manager_username}\n"
        f"Телефон: {brand.manager_phone}\n"
        f"Рабочие часы: {brand.working_hours}\n\n"
        f"Можете написать вопрос прямо здесь — мы ответим как обычной заявке."
    )
    extra = [
        [
            InlineKeyboardButton(
                text="✉️ Написать менеджеру",
                callback_data=SupportCallback(action="write").pack(),
            )
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=SUPPORT_SCREEN_ID, text=text, keyboard=keyboard)


def render_support_writing(*, content: ContentService, stack: Sequence[str]) -> Screen:
    text = (
        "✍️ <b>Опишите ваш вопрос</b>\n\n"
        "Отправьте текст одним сообщением. Менеджер свяжется с вами как только сможет."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(
        screen_id=SUPPORT_WRITING_SCREEN_ID,
        text=text,
        keyboard=keyboard,
        next_state=SupportState.writing_message,
    )
