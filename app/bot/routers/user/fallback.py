"""Catch-all handler for messages no other router claimed.

aiogram dispatches routers in registration order — anything left unmatched
after the in-flow routers (menu, lead_create, my_leads, etc.) falls through
here. Common cases:

- User types random text in MAIN_MENU instead of tapping a button.
- User sends a sticker / GIF / poll the bot doesn't process.
- User typed an unknown command like ``/foo``.

For the user this looks like "the bot ignored me", which feels broken. The
fallback acks the message with a short, friendly instruction so they always
know what they're supposed to do.
"""

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router(name="fallback")


_HELP_TEXT = (
    "🤔 Я не понял сообщение.\n\n"
    "Используйте кнопки под сообщением выше или одну из команд:\n"
    "• /start — главное меню\n"
    "• /menu — вернуться в меню\n"
    "• /cancel — отменить текущее действие"
)


@router.message()
async def on_unknown_message(message: Message, state: FSMContext) -> None:
    # We don't clear FSM here — the user might be in the middle of a wizard
    # and just sent the wrong thing. The wizard's own fallback handlers in
    # lead_create.py take precedence, so reaching this handler means the
    # message is *outside* any tracked flow. A short hint is enough.
    await message.answer(_HELP_TEXT)
