import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from app.bot.ui.navigation import get_root_message_id, set_root_message_id
from app.bot.ui.screen import Screen

logger = logging.getLogger(__name__)


async def _delete_root_best_effort(bot: Bot, chat_id: int, message_id: int) -> None:
    """Best-effort delete of the previous root message.

    Telegram refuses to delete messages older than 48h (or messages the bot
    didn't send), which is fine — we don't want to crash a state transition
    over a stale message. Just log and move on.
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:  # noqa: BLE001 — non-fatal cleanup
        logger.debug("root_message_delete_skipped chat=%s msg=%s err=%s", chat_id, message_id, exc)


async def render_screen(
    *,
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    screen: Screen,
    force_new: bool = False,
) -> int:
    """Render the screen on the user's root message, or send a fresh one.

    Returns the resulting message_id (the new root) and updates FSM data
    ``root_message_id``. If ``screen.next_state`` is set, transitions the FSM
    to that state after rendering.

    Modes:
    - **Default (force_new=False)**: try to edit the existing root in place
      so the chat stays compact. Falls back to a deletion+send pair if the
      edit fails (e.g. the user deleted the message manually). The old root
      is never left behind as a duplicate.
    - **force_new=True**: used for hand-off / prompt screens where the user
      is about to provide input and must visually see the request as the
      latest message. The OLD root is deleted first (best-effort) so the
      chat doesn't accumulate stale prompts.

    Reply-keyboard is NOT handled here — screens that need a reply-keyboard
    are responsible for sending their own dedicated message.
    """
    root_id = await get_root_message_id(state)

    if not force_new and root_id is not None:
        # Try editing in place — the cheap, no-spam path.
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=root_id,
                text=screen.text,
                reply_markup=screen.keyboard,
            )
            if screen.next_state is not None:
                await state.set_state(screen.next_state)
            return root_id
        except TelegramBadRequest as exc:
            # Edit failed (e.g. message deleted by the user or 48h timeout).
            # Fall through to delete-then-send below so we don't leave a
            # duplicate next to the new root.
            logger.info("root_message_edit_failed: %s", exc)

    # force_new OR fallback path: drop the old root before sending the new one
    # so chat history stays as a single live screen instead of a long stream.
    if root_id is not None:
        await _delete_root_best_effort(bot, chat_id, root_id)

    sent = await bot.send_message(
        chat_id=chat_id,
        text=screen.text,
        reply_markup=screen.keyboard,
    )
    await set_root_message_id(state, sent.message_id)

    if screen.next_state is not None:
        await state.set_state(screen.next_state)

    return sent.message_id
