from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.ui.navigation import ROOT_MESSAGE_ID_KEY


async def is_root_message(callback: CallbackQuery, state: FSMContext) -> bool:
    """Return True when the callback came from the current root message.

    Returns False for stale callbacks (old buttons after root moved) or when no
    root has been established yet.
    """
    if callback.message is None:
        return False
    data = await state.get_data()
    root_id = data.get(ROOT_MESSAGE_ID_KEY)
    if root_id is None:
        return False
    return int(root_id) == int(callback.message.message_id)
