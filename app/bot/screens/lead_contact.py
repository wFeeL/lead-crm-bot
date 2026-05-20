"""Contact-collection step.

Unlike every other screen in the bot, this step lives in **a single message**
with a reply-keyboard (the "📞 Поделиться номером" button uses Telegram's
``request_contact`` mechanism, which only works from a reply-keyboard). We
intentionally don't add inline Back/Home here — that would force two messages
on the user, which they rightly complained about. To leave this step, /cancel
typed as a slash command still works via EscapeMiddleware.
"""

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.ui.navigation import get_root_message_id, set_root_message_id
from app.bot.ui.render import _delete_root_best_effort

LEAD_CONTACT_PROMPT_SCREEN_ID = "lead_contact_prompt"

_PROMPT_TEXT = (
    "📞 <b>Контакт для связи</b>\n\n"
    "Нажмите кнопку ниже, чтобы поделиться номером, "
    "или напишите @username / номер вручную."
)


def make_contact_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def send_contact_prompt(*, bot: Bot, chat_id: int, state: FSMContext) -> int:
    """Send the contact-prompt as a single message and update root_message_id.

    Drops any existing root first (best-effort) so the chat doesn't end up
    with both a previous screen and the contact prompt visible at once.
    """
    root_id = await get_root_message_id(state)
    if root_id is not None:
        await _delete_root_best_effort(bot, chat_id, root_id)
    sent = await bot.send_message(
        chat_id=chat_id,
        text=_PROMPT_TEXT,
        reply_markup=make_contact_reply_keyboard(),
    )
    await set_root_message_id(state, sent.message_id)
    return sent.message_id
