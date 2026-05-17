from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.ui.callbacks import NavCallback
from app.bot.ui.navigation import go_home, pop


async def handle_nav(
    callback: CallbackQuery,
    callback_data: NavCallback,
    state: FSMContext,
    content=None,
    current_user=None,
    session: AsyncSession | None = None,
) -> None:
    """Universal navigation: back / home / cancel.

    home and cancel re-render MAIN_MENU as the (existing) root. back pops the
    stack — re-rendering of the now-top screen is the responsibility of the
    feature handler that pushed it (Step 3+ will wire generic back-render).
    """
    if callback_data.action == "back":
        await pop(state)
        await callback.answer()
        return

    if callback_data.action == "home":
        await go_home(state)
    elif callback_data.action == "cancel":
        await state.set_state(None)
        await state.set_data({})

    # Render MAIN_MENU on home/cancel if we have context.
    if content is not None and current_user is not None and session is not None:
        from app.bot.routers.user.menu import render_and_show_main_menu
        from app.db.repositories.leads import LeadRepository

        repo = LeadRepository(session)
        leads_count = await repo.count_by_user(current_user.id)
        await render_and_show_main_menu(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            content=content,
            leads_count=leads_count,
        )

    await callback.answer()


def create_nav_router() -> Router:
    router = Router(name="nav")
    router.callback_query(NavCallback.filter())(handle_nav)
    return router
