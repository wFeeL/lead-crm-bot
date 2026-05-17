from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.ui.callbacks import NavCallback
from app.bot.ui.navigation import go_home, pop


async def handle_nav(
    callback: CallbackQuery,
    callback_data: NavCallback,
    state: FSMContext,
) -> None:
    """Universal navigation: back / home / cancel.

    Step 1 only manages FSM state. Rendering MAIN_MENU is the responsibility of
    Step 2 (when MAIN_MENU is implemented).

    - back   : pops the nav stack.
    - home   : clears the stack down to MAIN_MENU.
    - cancel : clears FSM state entirely + clears the stack.
    """
    if callback_data.action == "back":
        await pop(state)
    elif callback_data.action == "home":
        await go_home(state)
    elif callback_data.action == "cancel":
        await state.set_state(None)
        await state.set_data({})

    await callback.answer()


def create_nav_router() -> Router:
    """Create and return a fresh nav Router with all navigation handlers registered."""
    router = Router(name="nav")
    router.callback_query(NavCallback.filter())(handle_nav)
    return router
