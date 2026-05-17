from collections.abc import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

FAQ_SCREEN_ID = "faq"
FAQ_ANSWER_SCREEN_ID = "faq_answer"


class FaqCallback(CallbackData, prefix="faq"):
    """Index into the FAQ entries from texts.yaml."""

    index: int


def render_faq(*, content: ContentService, stack: Sequence[str]) -> Screen:
    extra_rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=entry.q, callback_data=FaqCallback(index=i).pack())]
        for i, entry in enumerate(content.faq)
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra_rows))
    title = "❓ Часто задаваемые вопросы\n\nВыберите вопрос:"
    return Screen(screen_id=FAQ_SCREEN_ID, text=title, keyboard=keyboard)


def render_faq_answer(*, content: ContentService, index: int, stack: Sequence[str]) -> Screen:
    if index < 0 or index >= len(content.faq):
        raise IndexError(f"FAQ index {index} out of range")
    entry = content.faq[index]
    text = f"<b>{entry.q}</b>\n\n{entry.a}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(screen_id=FAQ_ANSWER_SCREEN_ID, text=text, keyboard=keyboard)
