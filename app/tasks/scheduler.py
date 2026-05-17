import asyncio
import signal

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis

from app.bot.create import create_bot
from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import session_scope
from app.services.leads import LeadService

logger = get_logger(__name__)


async def send_daily_report(bot: Bot, settings: Settings) -> None:
    async with session_scope() as session:
        stats = await LeadService(session, settings).daily_stats()
    text = (
        "Отчет за день\n\n"
        f"Новых заявок: {stats.new}\n"
        f"В работе: {stats.in_progress}\n"
        f"Ждем клиента: {stats.waiting}\n"
        f"Завершено: {stats.done}\n"
        f"Отклонено: {stats.rejected}\n"
        f"Отменено: {stats.cancelled}\n"
        f"Популярная категория: {stats.top_category or '-'}"
    )
    targets = list(settings.admin_ids)
    if settings.manager_group_id is not None:
        targets.append(settings.manager_group_id)
    for target in targets:
        try:
            await bot.send_message(target, text)
        except Exception as exc:
            logger.warning("daily_report_failed target=%s error=%s", target, exc)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    bot = create_bot(settings)
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(send_daily_report, "cron", hour=20, minute=0, args=[bot, settings])
    scheduler.start()
    logger.info("scheduler_started")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(stop_signal, stop_event.set)
    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
