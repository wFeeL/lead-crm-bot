from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.routers import admin, health, webhooks
from app.bot.create import create_bot, create_dispatcher
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    settings = get_settings()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.bot = create_bot(settings)
    app.state.dispatcher = create_dispatcher(settings, app.state.redis)
    try:
        yield
    finally:
        await app.state.bot.session.close()
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(webhooks.router)
    app.include_router(admin.router)
    return app


app = create_app()
