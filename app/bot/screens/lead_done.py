from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.screens.main_menu import MainMenuCallback
from app.bot.ui.callbacks import NavCallback
from app.bot.ui.screen import Screen
from app.services.content import ContentService

LEAD_DONE_SCREEN_ID = "lead_done"


def render_lead_done(*, content: ContentService, public_id: str) -> Screen:
    eta = content.brand.eta_response_hours
    text = (
        f"✅ <b>Заявка №{public_id} принята!</b>\n\n"
        f"Менеджер свяжется с вами в течение {eta} часов.\n"
        f"Следить за статусом можно в разделе «Мои заявки»."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Ещё заявка",
                    callback_data=MainMenuCallback(action="create_lead").pack(),
                ),
                InlineKeyboardButton(
                    text="📋 Мои заявки",
                    callback_data=MainMenuCallback(action="my_leads").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Меню",
                    callback_data=NavCallback(action="home").pack(),
                )
            ],
        ]
    )
    return Screen(screen_id=LEAD_DONE_SCREEN_ID, text=text, keyboard=keyboard)
