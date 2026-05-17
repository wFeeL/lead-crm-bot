from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

ESCAPE_COMMANDS = ("/cancel", "/menu", "/start")


class EscapeMiddleware(BaseMiddleware):
    """Clears FSM and routes /cancel /menu to MAIN_MENU; /start passes through.

    For /cancel and /menu the middleware short-circuits the chain after rendering
    MAIN_MENU. /start passes through to the start handler which sends a fresh root.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.text not in ESCAPE_COMMANDS:
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        if state is not None:
            await state.set_state(None)
            await state.set_data({})

        if event.text == "/start":
            return await handler(event, data)

        # /cancel and /menu: render MAIN_MENU directly.
        # Late imports here to avoid circular imports (menu router → middleware via dispatcher).
        from app.bot.routers.user.menu import render_and_show_main_menu
        from app.db.repositories.leads import LeadRepository

        content = data.get("content")
        current_user = data.get("current_user")
        session = data.get("session")

        if state is None or content is None or current_user is None or session is None:
            return None  # Silent — can't render without context.

        repo = LeadRepository(session)
        leads_count = await repo.count_by_user(current_user.id)
        await render_and_show_main_menu(
            bot=event.bot,
            chat_id=event.chat.id,
            state=state,
            content=content,
            leads_count=leads_count,
        )
        return None
