import asyncio

from redis.asyncio import Redis

from app.bot.create import create_bot, create_dispatcher
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings, redis)
    try:
        await bot.delete_webhook(drop_pending_updates=settings.drop_pending_updates)
        logger.info("bot_polling_started")
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
