import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from app.bot.ui.navigation import get_root_message_id, set_root_message_id
from app.bot.ui.screen import Screen

logger = logging.getLogger(__name__)


async def render_screen(
    *,
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    screen: Screen,
    force_new: bool = False,
) -> int:
    """Render the screen on the user's root message, or send a new one.

    Returns the resulting message_id (root). Updates FSM data root_message_id.
    If screen.next_state is set, transitions the FSM to that state after render.
    If force_new is True, always send a new message and update root to it —
    used at hand-off points (lead summary, opening admin detail) where the user
    must visually see a fresh message.

    Reply-keyboard is NOT handled here — screens that need one are responsible
    for sending a separate prompt message after this call.
    """
    root_id = await get_root_message_id(state)
    result_id: int
    if not force_new and root_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=root_id,
                text=screen.text,
                reply_markup=screen.keyboard,
            )
            result_id = root_id
        except TelegramBadRequest as exc:
            logger.info("root_message_edit_failed_falling_back_to_send: %s", exc)
            sent = await bot.send_message(
                chat_id=chat_id,
                text=screen.text,
                reply_markup=screen.keyboard,
            )
            await set_root_message_id(state, sent.message_id)
            result_id = sent.message_id
    else:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=screen.text,
            reply_markup=screen.keyboard,
        )
        await set_root_message_id(state, sent.message_id)
        result_id = sent.message_id

    if screen.next_state is not None:
        await state.set_state(screen.next_state)

    return result_id
