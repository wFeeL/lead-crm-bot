from datetime import timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.escape import EscapeMiddleware
from app.bot.middlewares.rate_limit import RateLimitMiddleware
from app.bot.middlewares.user import UserMiddleware
from app.bot.routers.admin import leads as admin_leads
from app.bot.routers.user import lead_create, my_leads, start
from app.bot.routers.user.faq import router as faq_router
from app.bot.routers.user.menu import router as menu_router
from app.bot.routers.user.support import router as support_router
from app.bot.ui.handler import create_nav_router
from app.core.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings, redis: Redis | None = None) -> Dispatcher:
    storage = (
        RedisStorage(
            redis=redis,
            state_ttl=timedelta(hours=settings.fsm_ttl_hours),
            data_ttl=timedelta(hours=settings.fsm_ttl_hours),
        )
        if redis is not None
        else MemoryStorage()
    )
    dispatcher = Dispatcher(storage=storage)

    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(DbSessionMiddleware())
        observer.outer_middleware(UserMiddleware(settings))

    dispatcher.message.middleware(EscapeMiddleware())
    dispatcher.message.middleware(RateLimitMiddleware(redis, settings, event_type="message"))
    dispatcher.callback_query.middleware(
        RateLimitMiddleware(redis, settings, event_type="callback")
    )

    dispatcher.include_router(create_nav_router())
    dispatcher.include_router(menu_router)
    dispatcher.include_router(faq_router)
    dispatcher.include_router(support_router)
    dispatcher.include_router(lead_create.router)
    dispatcher.include_router(my_leads.router)
    dispatcher.include_router(admin_leads.router)
    dispatcher.include_router(start.router)
    return dispatcher
