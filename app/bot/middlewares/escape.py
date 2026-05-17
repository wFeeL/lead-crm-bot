from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

ESCAPE_COMMANDS = ("/cancel", "/menu", "/start")


class EscapeMiddleware(BaseMiddleware):
    """Clears FSM state when the user issues /start, /menu, or /cancel.

    /start passes through to the regular start handler (which renders MAIN_MENU).
    /cancel and /menu short-circuit: downstream handlers are NOT invoked.

    Step 2 will hook MAIN_MENU rendering directly into this middleware so /cancel
    and /menu always land the user on a fresh root. For now the middleware only
    manages FSM cleanup.
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
        return None
