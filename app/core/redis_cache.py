import json
from dataclasses import asdict, is_dataclass
from functools import lru_cache
from typing import Any

from app.core.redis import get_redis


class RedisCache:
    def __init__(
        self,
        default_ttl: int = 3600,
    ):
        """Инициализация RedisCache"""
        self.default_ttl = default_ttl

    @staticmethod
    def dumps(
        value: Any,
    ) -> str:
        """Преобразует объект в строку"""
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def loads(
        value: str,
    ) -> Any:
        """Преобразует строку в объект"""
        return json.loads(value)

    async def get(
        self,
        key: str,
    ) -> Any | None:
        """Читает объект из Redis"""
        redis = await get_redis()
        value = await redis.get(key)
        if value is None:
            return None
        return self.loads(value)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Сохраняет объект в Redis"""
        redis = await get_redis()
        await redis.set(
            key,
            self.dumps(value),
            ex=ttl or self.default_ttl,
        )

    async def delete(
        self,
        key: str,
    ) -> None:
        """Удаляет объект из Redis"""
        redis = await get_redis()
        await redis.delete(key)

    async def set_dataclass(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        Сохраняет dataclass в Redis
        """
        if not is_dataclass(value):
            raise ValueError("value must be a dataclass")
        dict_value = asdict(value)
        await self.set(key, dict_value, ttl)

    async def get_dataclass(
        self,
        key: str,
        cls: type,
    ) -> Any | None:
        """
        Читает dataclass из Redis
        """
        data = await self.get(key)
        if data is None:
            return None
        return cls(**data)


@lru_cache()
def get_redis_cache() -> RedisCache:
    return RedisCache()
