import asyncio

import redis.asyncio as redis
from loguru import logger

from app.config import get_settings

redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """
    Dependency for FastAPI to get a Redis client.

    Returns the singleton Redis client.
    """
    if not redis_client:
        raise RuntimeError("Redis not initialized")
    return redis_client


async def init_redis(retries: int = 5, backoff: float = 0.5) -> None:
    global redis_client
    settings = get_settings()
    redis_client = redis.Redis(
        host=settings.redis.host,
        port=settings.redis.connect_port,
        db=settings.redis.redis_db,
        password=settings.redis.password,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.redis.pool_size,
    )

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            await redis_client.ping()
            logger.info("Redis connected successfully")
            return
        except Exception as e:
            last_exc = e
            logger.warning(f"Redis connect attempt {attempt}/{retries} failed: {e}")
            await asyncio.sleep(backoff * (2 ** (attempt - 1)))

    logger.error(f"Failed to connect to Redis after {retries} attempts: {last_exc}")
    raise last_exc


async def close_redis() -> None:
    """
    Close the Redis client.
    """
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")
