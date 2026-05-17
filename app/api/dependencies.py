from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.dependencies import get_db
from app.db.models.user import User
from app.db.repositories.users import UserRepository


async def get_redis(request: Request) -> Redis:
    return request.app.state.redis


async def get_api_admin_user(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not settings.admin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ADMIN_IDS must contain at least one admin for API mutations",
        )
    repository = UserRepository(session)
    user = await repository.upsert_telegram_user(
        telegram_id=settings.admin_ids[0],
        username="api_admin",
        first_name="API",
        last_name="Admin",
        is_admin=True,
    )
    await session.commit()
    return user
