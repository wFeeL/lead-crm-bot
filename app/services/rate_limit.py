from redis.asyncio import Redis

from app.core.exceptions import RateLimitExceededError
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisRateLimiter:
    def __init__(self, redis: Redis | None) -> None:
        self.redis = redis

    async def hit(self, *, key: str, limit: int, window_seconds: int) -> None:
        if self.redis is None:
            return
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, window_seconds)
            if count > limit:
                raise RateLimitExceededError(f"rate limit exceeded for {key}")
        except RateLimitExceededError:
            raise
        except Exception as exc:
            logger.warning("redis_rate_limit_unavailable key=%s error=%s", key, exc)
