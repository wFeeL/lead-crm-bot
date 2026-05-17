from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TelegramUser

from app.core.config import Settings
from app.core.security import is_admin
from app.db.repositories.users import UserRepository


class UserMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user: TelegramUser | None = data.get("event_from_user")
        session = data.get("session")
        if telegram_user is not None and session is not None:
            repository = UserRepository(session)
            data["current_user"] = await repository.upsert_telegram_user(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                is_admin=is_admin(telegram_user.id, self.settings),
            )
        return await handler(event, data)
