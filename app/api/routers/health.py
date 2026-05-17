from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_redis
from app.db.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await session.execute(text("select 1"))
    return {"status": "ok"}


@router.get("/health/redis")
async def health_redis(redis: Redis = Depends(get_redis)) -> dict[str, str]:
    await redis.ping()
    return {"status": "ok"}

