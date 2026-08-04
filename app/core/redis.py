import json
from datetime import datetime
from inspect import isawaitable
from typing import Any

from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

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
        LoggerCore.redis.error(
            f"Redis가 초기화 되지 않았습니다. '{name}'에 접근할 수 없습니다."
        )
        raise RuntimeError(f"Redis is not initialized. Cannot access '{name}'")

    @classmethod
    async def connect(cls):
        if cls.redis_instance is not None:
            LoggerCore.redis.warning("Redis가 이미 초기화 되어있습니다.")
            return
        LoggerCore.redis.info("Redis 초기화 중...")
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
        LoggerCore.redis.info("Redis 초기화 완료")

    @classmethod
    async def close(cls):
        if cls.redis_instance is None:
            LoggerCore.redis.warning(
                "Redis가 초기화 되지 않았습니다. 연결을 닫을 수 없습니다."
            )
            return
        LoggerCore.redis.info("Redis 연결 닫는 중...")
        await cls.redis_instance.close()
        LoggerCore.redis.info("Redis 연결이 닫혔습니다.")

    @classmethod
    async def get(cls, key: str) -> Any:
        if cls.redis_instance is None:
            LoggerCore.redis.warning(
                f"Redis가 초기화 되지 않았습니다. '{key}'에 대한 값을 가져올 수 없습니다."
            )
            return None

        try:
            value = await cls.redis_instance.get(key)
            if value:
                LoggerCore.redis.debug(f"'{key}' 가져옴")
                return json.loads(value)
            LoggerCore.redis.debug(f"'{key}' 존재하지 않음")
            return None
        except Exception as e:
            LoggerCore.redis.error(
                f"'{key}'에 대한 값을 가져오는데 실패했습니다: {e}", exc_info=True
            )
            return None

    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = 60):
        if cls.redis_instance is None:
            LoggerCore.redis.warning(
                f"Redis가 초기화 되지 않았습니다. '{key}'에 대한 값을 저장할 수 없습니다."
            )
            return

        try:
            json_value = json.dumps(value, cls=DateTimeEncoder)
            await cls.redis_instance.set(key, json_value, ex=ttl)
            LoggerCore.redis.debug(
                f"'{key}'를 설정했습니다. (TTL: {ttl}초, 크기: {len(json_value)} bytes)"
            )
        except Exception as e:
            LoggerCore.redis.error(
                f"'{key}'에 대한 값을 저정하는데 실패했습니다: {e}", exc_info=True
            )

    @classmethod
    async def delete(cls, key: str):
        if cls.redis_instance is None:
            LoggerCore.redis.warning(
                f"Redis가 초기화 되지 않았습니다. '{key}'에 대한 값을 삭제할 수 없습니다."
            )
            return

        try:
            await cls.redis_instance.delete(key)
            LoggerCore.redis.debug(f"'{key}'를 삭제했습니다.")
        except Exception as e:
            LoggerCore.redis.error(
                f"'{key}'에 대한 값을 삭제하는데 실패했습니다: {e}", exc_info=True
            )

    @classmethod
    async def delete_pattern(cls, pattern: str):
        if cls.redis_instance is None:
            LoggerCore.redis.warning(
                f"Redis가 초기화 되지 않았습니다. '{pattern}' 패턴의 값들을 삭제할 수 없습니다."
            )
            return

        try:
            keys = await cls.redis_instance.keys(pattern)
            if keys:
                await cls.redis_instance.delete(*keys)
                LoggerCore.redis.debug(
                    f"'{pattern}' 패턴의 값들 {len(keys)}개를 삭제했습니다."
                )
            else:
                LoggerCore.redis.debug(f"'{pattern}' 패턴의 값들 0개를 삭제했습니다.")
        except Exception as e:
            LoggerCore.redis.error(
                f"'{pattern}' 패턴의 값들을 삭제하는데 실패했습니다: {e}", exc_info=True
            )

    @classmethod
    async def expire(cls, key: str, time: int, **kwargs) -> bool:
        if cls.redis_instance is None:
            LoggerCore.redis.warning(
                f"Redis가 초기화 되지 않았습니다. '{key}'의 만료 시간을 설정할 수 없습니다."
            )
            return False

        try:
            result = await cls.redis_instance.expire(key, time, **kwargs)
            LoggerCore.redis.debug(f"'{key}'의 만료 시간을 '{time}초'로 설정했습니다.")
            return result
        except Exception as e:
            LoggerCore.redis.error(
                f"'{key}'의 만료시간 설정에 실패했습니다: {e}", exc_info=True
            )
            return False

    @classmethod
    async def ttl(cls, key: str) -> int:
        if cls.redis_instance is None:
            LoggerCore.redis.warning(
                f"Redis가 초기화 되지 않았습니다. '{key}'의 TTL 값을 가져올 수 없습니다."
            )
            return -2

        try:
            ttl = await cls.redis_instance.ttl(key)
            LoggerCore.redis.debug(f"'{key}'는 '{ttl}초' 후에 만료됩니다.")
            return ttl
        except Exception as e:
            LoggerCore.redis.error(
                f"'{key}'의 TTL 값을 가져오는데 실패했습니다: {e}", exc_info=True
            )
            return -2
