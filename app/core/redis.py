import json
from datetime import datetime
from typing import Any, Optional
from redis.asyncio import Redis

from .config import settings
from .loggers import redis_logger


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RedisCore:
    def __init__(self):
        self.redis: Optional[Redis] = None

    async def init(self):
        try:
            self.redis = Redis.from_url(str(settings.redis.url), decode_responses=True)
            await self.redis.ping()
            redis_logger.info("Redis initialized and connected successfully.")
        except Exception as e:
            redis_logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            self.redis = None

    async def close(self):
        if self.redis:
            await self.redis.close()
            redis_logger.info("Redis connection closed.")

    async def get(self, key: str) -> Any:
        if not self.redis:
            return None
        try:
            value = await self.redis.get(key)
            if value:
                redis_logger.debug(f"HIT: {key}")
                return json.loads(value)
            redis_logger.debug(f"MISS: {key}")
            return None
        except Exception as e:
            redis_logger.error(f"Error getting key '{key}': {e}", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int = 60):
        if not self.redis:
            return
        try:
            json_value = json.dumps(value, cls=DateTimeEncoder)
            await self.redis.set(key, json_value, ex=ttl)
            redis_logger.debug(f"SET: {key} (TTL: {ttl}s, Size: {len(json_value)} bytes)")
        except Exception as e:
            redis_logger.error(f"Error setting key '{key}': {e}", exc_info=True)

    async def delete(self, key: str):
        if not self.redis:
            return
        try:
            await self.redis.delete(key)
            redis_logger.debug(f"DELETE: {key}")
        except Exception as e:
            redis_logger.error(f"Error deleting key '{key}': {e}", exc_info=True)

    async def delete_pattern(self, pattern: str):
        if not self.redis:
            return
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
                redis_logger.debug(f"DELETE PATTERN: {pattern} ({len(keys)} keys)")
            else:
                redis_logger.debug(f"`DELETE PATTERN: {pattern} (0 keys)")
        except Exception as e:
            redis_logger.error(f"Error deleting pattern '{pattern}': {e}", exc_info=True)


redis = RedisCore()
