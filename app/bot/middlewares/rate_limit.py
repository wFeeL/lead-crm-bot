from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.exceptions import RateLimitExceededError
from app.services.rate_limit import RedisRateLimiter


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis | None, settings: Settings, *, event_type: str) -> None:
        self.limiter = RedisRateLimiter(redis)
        self.settings = settings
        self.event_type = event_type

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        try:
            await self.limiter.hit(
                key=f"{self.event_type}_rate:{user.id}",
                limit=self.settings.rate_limit_messages_per_minute,
                window_seconds=60,
            )
        except RateLimitExceededError:
            if isinstance(event, CallbackQuery):
                await event.answer(
                    "Слишком много действий. Попробуйте чуть позже.",
                    show_alert=True,
                )
            elif isinstance(event, Message):
                await event.answer("Слишком много сообщений. Попробуйте чуть позже.")
            return None
        return await handler(event, data)
