import json
from datetime import datetime
from typing import Any
from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from inspect import isawaitable

from .config import settings
from .loggers import LoggerCore


class DateTimeEncoder(json.JSONEncoder):
    def default(cls, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RedisCore:
    instance = None
    redis_instance: Redis | None = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    @classmethod
    def __getattr__(cls, name):
        if cls.redis_instance is not None:
            return getattr(cls.redis_instance, name)
        LoggerCore.redis.error(f"Redis is not initialized. Cannot access '{name}'")
        raise AttributeError(f"Redis is not initialized. Cannot access '{name}'")

    @classmethod
    async def connect(cls):
        if cls.redis_instance is not None:
            LoggerCore.redis.warning("Redis is already initialized.")
            return
        LoggerCore.redis.info("Redis Initializing...")
        try:
            retry = Retry(ExponentialBackoff(), 3)
            cls.redis_instance = Redis.from_url(
                str(settings.redis.url),
                retry=retry,
                retry_on_timeout=True,
                health_check_interval=30,
                decode_responses=True,
            )

            # noinspection PyUnresolvedReferences
            ping_result = cls.redis_instance.ping()

            # 비동기(awaitable) 환경을 지원하기 위한 처리
            if isawaitable(ping_result):
                ping_result = await ping_result

            if not ping_result:
                raise ConnectionError("Redis ping failed: no response")
            LoggerCore.redis.info("Redis initialized.")
        except Exception as e:
            LoggerCore.redis.error(f"Failed to connect to Redis: {e}", exc_info=True)
            cls.redis_instance = None

    @classmethod
    async def close(cls):
        if cls.redis_instance is None:
            LoggerCore.redis.warning("Redis is not initialized. Cannot close connection.")
            return
        LoggerCore.redis.info("Closing Redis connection...")
        await cls.redis_instance.close()
        LoggerCore.redis.info("Redis connection closed.")

    @classmethod
    async def get(cls, key: str) -> Any:
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis is not initialized. Cannot get key '{key}'")
            return None

        try:
            value = await cls.redis_instance.get(key)
            if value:
                LoggerCore.redis.debug(f"HIT: {key}")
                return json.loads(value)
            LoggerCore.redis.debug(f"MISS: {key}")
            return None
        except Exception as e:
            LoggerCore.redis.error(f"Error getting key '{key}': {e}", exc_info=True)
            return None

    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = 60):
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis is not initialized. Cannot set key '{key}'")
            return

        try:
            json_value = json.dumps(value, cls=DateTimeEncoder)
            await cls.redis_instance.set(key, json_value, ex=ttl)
            LoggerCore.redis.debug(f"SET: {key} (TTL: {ttl}s, Size: {len(json_value)} bytes)")
        except Exception as e:
            LoggerCore.redis.error(f"Error setting key '{key}': {e}", exc_info=True)

    @classmethod
    async def delete(cls, key: str):
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis is not initialized. Cannot delete key '{key}'")
            return

        try:
            await cls.redis_instance.delete(key)
            LoggerCore.redis.debug(f"DELETE: {key}")
        except Exception as e:
            LoggerCore.redis.error(f"Error deleting key '{key}': {e}", exc_info=True)

    @classmethod
    async def delete_pattern(cls, pattern: str):
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis is not initialized. Cannot delete pattern '{pattern}'")
            return

        try:
            keys = await cls.redis_instance.keys(pattern)
            if keys:
                await cls.redis_instance.delete(*keys)
                LoggerCore.redis.debug(f"DELETE PATTERN: {pattern} ({len(keys)} keys)")
            else:
                LoggerCore.redis.debug(f"`DELETE PATTERN: {pattern} (0 keys)")
        except Exception as e:
            LoggerCore.redis.error(f"Error deleting pattern '{pattern}': {e}", exc_info=True)

    @classmethod
    async def expire(cls, key: str, time: int, **kwargs) -> bool:
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis is not initialized. Cannot set expire for key '{key}'")
            return False

        try:
            result = await cls.redis_instance.expire(key, time, **kwargs)
            LoggerCore.redis.debug(f"EXPIRE: {key} set to {time}s")
            return result
        except Exception as e:
            LoggerCore.redis.error(f"Error setting expire for key '{key}': {e}", exc_info=True)
            return False

    @classmethod
    async def ttl(cls, key: str) -> int:
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis is not initialized. Cannot get TTL for key '{key}'")
            return -2

        try:
            ttl = await cls.redis_instance.ttl(key)
            LoggerCore.redis.debug(f"TTL: {key} is {ttl}s")
            return ttl
        except Exception as e:
            LoggerCore.redis.error(f"Error getting TTL for key '{key}': {e}", exc_info=True)
            return -2
