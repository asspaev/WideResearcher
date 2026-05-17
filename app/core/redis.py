import asyncio

import redis.asyncio as redis
from loguru import logger

from app.config import get_settings

_clients: dict[int, redis.Redis] = {}


def _loop_key() -> int:
    """Возвращает ключ реестра — id текущего event loop."""
    return id(asyncio.get_running_loop())


async def get_redis() -> redis.Redis:
    """Dependency для FastAPI и общий аксессор Redis-клиента.

    Возвращает клиент, привязанный к текущему event loop. Соединения redis-py
    привязаны к loop, в котором были созданы, поэтому в Celery-воркере, где
    каждая таска запускает свой `asyncio.run()`, делить клиент между петлями
    нельзя — каждая петля держит своего.
    """
    client = _clients.get(_loop_key())
    if client is None:
        raise RuntimeError("Redis not initialized")
    return client


async def init_redis(retries: int = 5, backoff: float = 0.5) -> None:
    """Создаёт Redis-клиент и регистрирует его за текущим event loop.

    Args:
        retries: Сколько раз пинговать Redis перед фейлом.
        backoff: Начальная задержка между попытками (экспоненциально растёт).

    Raises:
        Exception: Если после `retries` попыток Redis не отвечает.
    """
    settings = get_settings()
    client = redis.Redis(
        host=settings.redis.host,
        port=settings.redis.connect_port,
        db=settings.redis.redis_db,
        password=settings.redis.password,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.redis.pool_size,
    )

    last_exc: Exception | None = None
    connected = False
    for attempt in range(1, retries + 1):
        try:
            await client.ping()
            connected = True
            break
        except Exception as e:
            last_exc = e
            logger.warning(f"Redis connect attempt {attempt}/{retries} failed: {e}")
            await asyncio.sleep(backoff * (2 ** (attempt - 1)))

    if not connected:
        logger.error(f"Failed to connect to Redis after {retries} attempts: {last_exc}")
        assert last_exc is not None
        raise last_exc

    key = _loop_key()
    previous = _clients.get(key)
    if previous is not None:
        try:
            await previous.aclose()
        except Exception as e:
            logger.warning(f"Redis: failed to close previous client on loop {key}: {e}")
    _clients[key] = client
    logger.info("Redis connected successfully")


async def close_redis() -> None:
    """Закрывает Redis-клиент, относящийся к текущему event loop.

    Если соединение не удалось закрыть штатно (например, из-за гонок при
    шатдауне), ошибка логируется и подавляется — реестр всё равно очищается,
    чтобы не валить вызывающий код (Celery-таску).
    """
    key = _loop_key()
    client = _clients.pop(key, None)
    if client is None:
        return
    try:
        await client.aclose()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.warning(f"Redis: error while closing client: {e}")
