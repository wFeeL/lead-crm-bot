from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.ui.back_registry import render_back
from app.bot.ui.callbacks import NavCallback
from app.bot.ui.navigation import (
    MAIN_MENU_SCREEN_ID,
    go_home,
    pop,
)

# Sentinel callback for inline buttons that are purely informational
# (e.g. the "page X/Y" indicator on paginated lists). Handler just acks
# the callback so Telegram's spinner clears immediately.
NOOP_CALLBACK = "noop"


async def _render_main_menu(
    *,
    bot,
    chat_id: int,
    state: FSMContext,
    content,
    current_user,
    session: AsyncSession,
) -> None:
    from app.bot.routers.user.menu import render_and_show_main_menu
    from app.db.repositories.leads import LeadRepository

    repo = LeadRepository(session)
    leads_count = await repo.count_by_user(current_user.id)
    await render_and_show_main_menu(
        bot=bot,
        chat_id=chat_id,
        state=state,
        content=content,
        leads_count=leads_count,
    )


async def handle_nav(
    callback: CallbackQuery,
    callback_data: NavCallback,
    state: FSMContext,
    content=None,
    current_user=None,
    session: AsyncSession | None = None,
) -> None:
    """Universal navigation: back / home / cancel.

    - ``back``: pop the stack and re-render the previous screen via
      :mod:`app.bot.ui.back_registry`. If no renderer is registered (or we are
      already at the bottom), fall back to MAIN_MENU.
    - ``home``: reset the stack to ``[main_menu]`` and re-render MAIN_MENU
      (FSM data is preserved).
    - ``cancel``: clear state + data, then re-render MAIN_MENU.
    """
    if callback_data.action == "back":
        new_top = await pop(state)
        # No context for navigation — best-effort acknowledge.
        if content is None or current_user is None or session is None:
            await callback.answer()
            return

        # Already at MAIN_MENU as the bottom: nothing to pop further.
        if new_top is None or new_top == MAIN_MENU_SCREEN_ID:
            await _render_main_menu(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                state=state,
                content=content,
                current_user=current_user,
                session=session,
            )
            await callback.answer()
            return

        rendered = await render_back(
            new_top,
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        if not rendered:
            # Unknown screen — collapse to MAIN_MENU rather than leaving the
            # user staring at a stale message.
            await go_home(state)
            await _render_main_menu(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                state=state,
                content=content,
                current_user=current_user,
                session=session,
            )
        await callback.answer()
        return

    if callback_data.action == "home":
        await go_home(state)
    elif callback_data.action == "cancel":
        await state.set_state(None)
        await state.set_data({})

    # Render MAIN_MENU on home/cancel if we have context.
    if content is not None and current_user is not None and session is not None:
        await _render_main_menu(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            content=content,
            current_user=current_user,
            session=session,
        )

    await callback.answer()


async def handle_noop(callback: CallbackQuery) -> None:
    """Ack a no-op callback (e.g. the page-indicator button on a paginated list)."""
    await callback.answer()


def create_nav_router() -> Router:
    router = Router(name="nav")
    router.callback_query(NavCallback.filter())(handle_nav)
    router.callback_query(F.data == NOOP_CALLBACK)(handle_noop)
    return router


__all__ = ["NOOP_CALLBACK", "create_nav_router", "handle_nav", "handle_noop"]
