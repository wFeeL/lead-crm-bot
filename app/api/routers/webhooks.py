from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

router = APIRouter(tags=["webhooks"])
logger = get_logger(__name__)


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.bot_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid webhook secret")

    bot: Bot = request.app.state.bot
    dispatcher: Dispatcher = request.app.state.dispatcher
    update_payload = await request.json()
    update_id = update_payload.get("update_id")
    if update_id is not None:
        try:
            is_new = await request.app.state.redis.set(
                f"telegram_update:{update_id}",
                "1",
                ex=24 * 60 * 60,
                nx=True,
            )
        except Exception as exc:
            logger.warning(
                "telegram_update_dedupe_unavailable update_id=%s error=%s",
                update_id,
                exc,
            )
        else:
            if not is_new:
                return {"status": "duplicate"}
    update = Update.model_validate(update_payload, context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"status": "ok"}
