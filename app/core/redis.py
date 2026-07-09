import json
from datetime import datetime
from typing import Any
from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from inspect import isawaitable

from .config import settings
from .loggers import redis_logger


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RedisCore:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        self.redis_instance: Redis | None = None

    def __getattr__(self, name):
        if self.redis_instance:
            return getattr(self.redis_instance, name)
        redis_logger.error(f"Redis is not initialized. Cannot access '{name}'")
        raise AttributeError(f"Redis is not initialized. Cannot access '{name}'")

    async def connect(self):
        if self.redis_instance:
            redis_logger.warning("Redis is already initialized.")
            return
        redis_logger.info("Connecting to Redis...")
        try:
            retry = Retry(ExponentialBackoff(), 3)
            self.redis_instance = Redis.from_url(
                str(settings.redis.url),
                retry=retry,
                retry_on_timeout=True,
                health_check_interval=30,
                decode_responses=True,
            )

            # noinspection PyUnresolvedReferences
            ping_result = self.redis_instance.ping()

            # 비동기(awaitable) 환경을 지원하기 위한 처리
            if isawaitable(ping_result):
                ping_result = await ping_result

            if not ping_result:
                raise ConnectionError("Redis ping failed: no response")
            redis_logger.info("Redis initialized and connected successfully.")
        except Exception as e:
            redis_logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            self.redis_instance = None

    async def close(self):
        if self.redis_instance:
            redis_logger.info("Closing Redis connection...")
            await self.redis_instance.close()
            redis_logger.info("Redis connection closed.")
        else:
            redis_logger.warning("Redis is not initialized. Cannot close connection.")

    async def get(self, key: str) -> Any:
        if not self.redis_instance:
            redis_logger.warning(f"Redis is not initialized. Cannot get key '{key}'")
            return None

        try:
            value = await self.redis_instance.get(key)
            if value:
                redis_logger.debug(f"HIT: {key}")
                return json.loads(value)
            redis_logger.debug(f"MISS: {key}")
            return None
        except Exception as e:
            redis_logger.error(f"Error getting key '{key}': {e}", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int = 60):
        if not self.redis_instance:
            redis_logger.warning(f"Redis is not initialized. Cannot set key '{key}'")
            return

        try:
            json_value = json.dumps(value, cls=DateTimeEncoder)
            await self.redis_instance.set(key, json_value, ex=ttl)
            redis_logger.debug(f"SET: {key} (TTL: {ttl}s, Size: {len(json_value)} bytes)")
        except Exception as e:
            redis_logger.error(f"Error setting key '{key}': {e}", exc_info=True)

    async def delete(self, key: str):
        if not self.redis_instance:
            redis_logger.warning(f"Redis is not initialized. Cannot delete key '{key}'")
            return

        try:
            await self.redis_instance.delete(key)
            redis_logger.debug(f"DELETE: {key}")
        except Exception as e:
            redis_logger.error(f"Error deleting key '{key}': {e}", exc_info=True)

    async def delete_pattern(self, pattern: str):
        if not self.redis_instance:
            redis_logger.warning(f"Redis is not initialized. Cannot delete pattern '{pattern}'")
            return

        try:
            keys = await self.redis_instance.keys(pattern)
            if keys:
                await self.redis_instance.delete(*keys)
                redis_logger.debug(f"DELETE PATTERN: {pattern} ({len(keys)} keys)")
            else:
                redis_logger.debug(f"`DELETE PATTERN: {pattern} (0 keys)")
        except Exception as e:
            redis_logger.error(f"Error deleting pattern '{pattern}': {e}", exc_info=True)

    async def expire(self, key: str, time: int, **kwargs) -> bool:
        if not self.redis_instance:
            redis_logger.warning(f"Redis is not initialized. Cannot set expire for key '{key}'")
            return False

        try:
            result = await self.redis_instance.expire(key, time, **kwargs)
            redis_logger.debug(f"EXPIRE: {key} set to {time}s")
            return result
        except Exception as e:
            redis_logger.error(f"Error setting expire for key '{key}': {e}", exc_info=True)
            return False

    async def ttl(self, key: str) -> int:
        if not self.redis_instance:
            redis_logger.warning(f"Redis is not initialized. Cannot get TTL for key '{key}'")
            return -2

        try:
            ttl = await self.redis_instance.ttl(key)
            redis_logger.debug(f"TTL: {key} is {ttl}s")
            return ttl
        except Exception as e:
            redis_logger.error(f"Error getting TTL for key '{key}': {e}", exc_info=True)
            return -2
