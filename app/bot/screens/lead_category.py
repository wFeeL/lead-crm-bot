from collections.abc import Sequence
from typing import Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

LEAD_CATEGORY_SCREEN_ID = "lead_category"


class LeadCategoryCallback(CallbackData, prefix="lead_cat"):
    slug: str


def render_lead_category(
    *,
    content: ContentService,
    categories: list[Any],
    stack: Sequence[str],
) -> Screen:
    if not categories:
        text = "Категории не настроены. Обратитесь к администратору."
        keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
        return Screen(screen_id=LEAD_CATEGORY_SCREEN_ID, text=text, keyboard=keyboard)

    text = "📝 <b>Новая заявка</b>\n\nВыберите категорию:"
    extra = [
        [
            InlineKeyboardButton(
                text=category.title,
                callback_data=LeadCategoryCallback(slug=category.slug).pack(),
            )
        ]
        for category in categories
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=LEAD_CATEGORY_SCREEN_ID, text=text, keyboard=keyboard)
