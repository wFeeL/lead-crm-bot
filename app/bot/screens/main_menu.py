from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.screen import Screen
from app.services.content import ContentService

MAIN_MENU_SCREEN_ID = "main_menu"


class MainMenuCallback(CallbackData, prefix="menu"):
    """Callback for buttons on the main menu screen."""

    action: Literal["create_lead", "my_leads", "support", "faq"]


def render_main_menu(*, content: ContentService, leads_count: int = 0) -> Screen:
    """Render the main menu.

    `leads_count` interpolates into the My-Leads button label.
    """
    try:
        title = content.text("main_menu.title", count=leads_count)
    except (KeyError, ValueError):
        title = content.text("main_menu.title")

    my_leads_label = f"📋 Мои заявки ({leads_count})" if leads_count else "📋 Мои заявки"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Оставить заявку",
                    callback_data=MainMenuCallback(action="create_lead").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=my_leads_label,
                    callback_data=MainMenuCallback(action="my_leads").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Связаться с менеджером",
                    callback_data=MainMenuCallback(action="support").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ FAQ",
                    callback_data=MainMenuCallback(action="faq").pack(),
                )
            ],
        ]
    )

    return Screen(screen_id=MAIN_MENU_SCREEN_ID, text=title, keyboard=keyboard)
