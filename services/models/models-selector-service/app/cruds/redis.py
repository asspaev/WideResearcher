from typing import Any, Optional

from loguru import logger

from app.core.redis import get_redis


async def create_record(key: str, value: bytes | int | float | str, expire: Optional[int] = None) -> bool:
    """
    Создает или перезаписывает запись в Redis.
    :param key: ключ записи
    :param value: значение (строка, словарь, число — всё сериализуется в строку)
    :param expire: время жизни в секундах (опционально)
    :return: True, если операция успешна
    """
    redis = await get_redis()
    result = await redis.set(key, value, ex=expire)
    logger.debug(f"CREATE key={key}, value={value}, expire={expire}, result={result}")
    return result


async def read_record(key: str) -> Optional[str]:
    """
    Возвращает значение по ключу или None, если ключ отсутствует.
    """
    redis = await get_redis()
    value = await redis.get(key)
    logger.debug(f"READ key={key}, result={value}")
    return value


async def update_record(key: str, value: Any, expire: Optional[int] = None) -> bool:
    """
    Обновляет значение по ключу, если оно существует.
    Возвращает False, если ключ не найден.
    """
    redis = await get_redis()
    exists = await redis.exists(key)
    if not exists:
        logger.debug(f"UPDATE failed, key={key} not found")
        return False

    result = await redis.set(key, value, ex=expire)
    logger.debug(f"UPDATE key={key}, value={value}, expire={expire}, result={result}")
    return result


async def delete_record(key: str) -> bool:
    """
    Удаляет запись по ключу.
    :return: True, если запись была удалена, False — если ключа не было
    """
    redis = await get_redis()
    result = await redis.delete(key)
    logger.debug(f"DELETE key={key}, deleted={bool(result)}")
    return bool(result)
