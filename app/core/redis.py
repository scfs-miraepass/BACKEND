import json
from datetime import date, datetime, time
from inspect import isawaitable
from typing import Any, TYPE_CHECKING

from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from .config import settings
from .loggers import LoggerCore
from .redis_keys import BoundKey, KeyPattern, RedisKey

if TYPE_CHECKING:
    _Type = Redis
else:
    _Type = object

SCAN_COUNT = 500


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, time)):
            return obj.isoformat()
        return super().default(obj)


def _require_key(key: Any) -> BoundKey:
    if not isinstance(key, BoundKey):
        raise TypeError(f"Redis Key는 app.core.redis_keys.Keys에 정의된 Key를 사용해야 합니다: {key!r}")
    return key


# noinspection method-overriding
class RedisCore(_Type):
    """
    Redis 클라이언트 래퍼.

    Key를 받는 함수는 `app.core.redis_keys.Keys`로 만든 `BoundKey`만 허용합니다.
    여기에 정의되지 않은 함수(pipeline, publish, pubsub 등)는 Redis 원본 클라이언트로 전달됩니다.
    """

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
        LoggerCore.redis.error(f"Redis가 초기화 되지 않았습니다. '{name}'에 접근할 수 없습니다.")
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
            LoggerCore.redis.warning("Redis가 초기화 되지 않았습니다. 연결을 닫을 수 없습니다.")
            return
        LoggerCore.redis.info("Redis 연결 닫는 중...")
        await cls.redis_instance.close()
        LoggerCore.redis.info("Redis 연결이 닫혔습니다.")

    @classmethod
    async def get(cls, key: BoundKey) -> Any:
        _require_key(key)
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'에 대한 값을 가져올 수 없습니다.")
            return None

        try:
            value = await cls.redis_instance.get(key)
            if value:
                LoggerCore.redis.debug(f"'{key}' 가져옴")
                return json.loads(value)
            LoggerCore.redis.debug(f"'{key}' 존재하지 않음")
            return None
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'에 대한 값을 가져오는데 실패했습니다: {e}", exc_info=True)
            return None

    @classmethod
    async def mget(cls, keys: list[BoundKey]) -> list[Any]:
        """
        여러 Key의 값을 한 번에 가져옵니다. 값이 없거나 실패한 Key는 None으로 반환됩니다.
        """
        for key in keys:
            _require_key(key)
        if not keys:
            return []
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. {len(keys)}개의 값을 가져올 수 없습니다.")
            return [None] * len(keys)

        try:
            values = await cls.redis_instance.mget(keys)
            LoggerCore.redis.debug(f"{len(keys)}개 중 {sum(v is not None for v in values)}개 가져옴")
            return [json.loads(v) if v else None for v in values]
        except Exception as e:
            LoggerCore.redis.error(f"{len(keys)}개의 값을 가져오는데 실패했습니다: {e}", exc_info=True)
            return [None] * len(keys)

    @classmethod
    async def set(cls, key: BoundKey, value: Any, ttl: int | None = None):
        """
        값을 저장합니다.

        Args:
            key: 저장할 Key
            value: JSON으로 직렬화 가능한 값
            ttl: TTL(초). 생략시 Key에 정의된 TTL을 사용합니다.

        Raises:
            ValueError: ttl을 생략했는데 Key에 TTL이 정의되어 있지 않은 경우
        """
        _require_key(key)
        if ttl is None:
            ttl = key.ttl
        if ttl is None:
            raise ValueError(f"'{key}'는 기본 TTL이 없어 ttl을 직접 지정해야 합니다.")

        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'에 대한 값을 저장할 수 없습니다.")
            return

        try:
            json_value = json.dumps(value, cls=DateTimeEncoder)
            await cls.redis_instance.set(key, json_value, ex=ttl)
            LoggerCore.redis.debug(f"'{key}'를 설정했습니다. (TTL: {ttl}초, 크기: {len(json_value)} bytes)")
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'에 대한 값을 저장하는데 실패했습니다: {e}", exc_info=True)

    @classmethod
    async def incrby(cls, key: BoundKey, amount: int, *, expire_at: datetime) -> int:
        """
        정수 값을 원자적으로 증가(음수면 감소)시키고, 만료 시각을 설정합니다.

        포인트 한도처럼 캐시가 아닌 상태 값에 사용하므로, 다른 함수와 달리 실패를 무시하지 않고 예외를 발생시킵니다.

        Returns:
            int: 증가된 후의 값
        """
        _require_key(key)
        if cls.redis_instance is None:
            raise RuntimeError(f"Redis가 초기화 되지 않았습니다. '{key}'의 값을 변경할 수 없습니다.")

        async with cls.redis_instance.pipeline(transaction=True) as pipe:
            pipe.incrby(key, amount)
            pipe.expireat(key, expire_at)
            value, _ = await pipe.execute()
        LoggerCore.redis.debug(f"'{key}'를 {amount:+} 변경했습니다. (현재: {value}, 만료: {expire_at.isoformat()})")
        return value

    @classmethod
    async def sadd(cls, key: BoundKey, *members: str):
        """Set에 값을 추가하고, Set의 TTL을 Key에 정의된 TTL로 갱신합니다."""
        _require_key(key)
        if key.ttl is None:
            raise ValueError(f"'{key}'는 기본 TTL이 없어 Set으로 사용할 수 없습니다.")
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'에 값을 추가할 수 없습니다.")
            return

        try:
            async with cls.redis_instance.pipeline(transaction=True) as pipe:
                pipe.sadd(key, *members)
                pipe.expire(key, key.ttl)
                await pipe.execute()
            LoggerCore.redis.debug(f"'{key}'에 {len(members)}개의 값을 추가했습니다.")
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'에 값을 추가하는데 실패했습니다: {e}", exc_info=True)

    @classmethod
    async def srem(cls, key: BoundKey, *members: str):
        """Set에서 값을 제거합니다."""
        _require_key(key)
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'에서 값을 제거할 수 없습니다.")
            return

        try:
            await cls.redis_instance.srem(key, *members)
            LoggerCore.redis.debug(f"'{key}'에서 {len(members)}개의 값을 제거했습니다.")
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'에서 값을 제거하는데 실패했습니다: {e}", exc_info=True)

    @classmethod
    async def smembers(cls, key: BoundKey) -> set[str]:
        """Set의 모든 값을 가져옵니다. 실패한 경우 빈 Set을 반환합니다."""
        _require_key(key)
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'의 값을 가져올 수 없습니다.")
            return set()

        try:
            return set(await cls.redis_instance.smembers(key))
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'의 값을 가져오는데 실패했습니다: {e}", exc_info=True)
            return set()

    @classmethod
    async def get_version(cls, key: BoundKey) -> int:
        """버전 Key의 현재 값을 가져옵니다. 값이 없으면 0을 반환합니다."""
        value = await cls.get(key)
        return int(value) if value else 0

    @classmethod
    async def bump_version(cls, key: BoundKey):
        """
        버전 Key의 값을 1 올려, 이전 버전으로 저장된 목록 캐시를 무효화합니다.
        버전 Key의 TTL은 올릴 때마다 Key에 정의된 TTL로 갱신됩니다.
        """
        _require_key(key)
        if key.ttl is None:
            raise ValueError(f"'{key}'는 버전 Key로 사용하려면 TTL이 정의되어 있어야 합니다.")
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'의 버전을 올릴 수 없습니다.")
            return

        try:
            async with cls.redis_instance.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, key.ttl)
                version, _ = await pipe.execute()
            LoggerCore.redis.debug(f"'{key}'의 버전을 {version}(으)로 올렸습니다.")
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'의 버전을 올리는데 실패했습니다: {e}", exc_info=True)

    @classmethod
    async def delete(cls, *keys: BoundKey):
        for key in keys:
            _require_key(key)
        if not keys:
            return
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. {list(keys)}에 대한 값을 삭제할 수 없습니다.")
            return

        try:
            await cls.redis_instance.delete(*keys)
            LoggerCore.redis.debug(f"{list(keys)}를 삭제했습니다.")
        except Exception as e:
            LoggerCore.redis.error(f"{list(keys)}에 대한 값을 삭제하는데 실패했습니다: {e}", exc_info=True)

    @classmethod
    async def delete_pattern(cls, pattern: RedisKey | KeyPattern) -> int:
        """
        패턴과 일치하는 Key들을 삭제합니다.

        `KEYS` 대신 `SCAN`으로 조금씩 나눠 조회하므로 다른 요청을 막지 않으며,
        삭제는 `UNLINK`로 메모리 해제를 백그라운드에서 처리합니다.

        Args:
            pattern: `RedisKey`(해당 Key 전체) 또는 `RedisKey.pattern(...)`으로 만든 패턴

        Returns:
            int: 삭제된 Key 개수
        """
        if isinstance(pattern, RedisKey):
            pattern = pattern.pattern()
        if not isinstance(pattern, KeyPattern):
            raise TypeError(f"패턴은 RedisKey 또는 RedisKey.pattern()으로 만들어야 합니다: {pattern!r}")

        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{pattern}' 패턴의 값들을 삭제할 수 없습니다.")
            return 0

        deleted = 0
        try:
            batch: list[str] = []
            async for key in cls.redis_instance.scan_iter(match=pattern, count=SCAN_COUNT):
                batch.append(key)
                if len(batch) >= SCAN_COUNT:
                    deleted += await cls.redis_instance.unlink(*batch)
                    batch.clear()
            if batch:
                deleted += await cls.redis_instance.unlink(*batch)
            LoggerCore.redis.debug(f"'{pattern}' 패턴의 값들 {deleted}개를 삭제했습니다.")
        except Exception as e:
            LoggerCore.redis.error(f"'{pattern}' 패턴의 값들을 삭제하는데 실패했습니다: {e}", exc_info=True)
        return deleted

    @classmethod
    async def expire(cls, key: BoundKey, time: int | None = None, **kwargs) -> bool:
        """
        만료 시간을 설정합니다. time을 생략하면 Key에 정의된 TTL을 사용합니다.
        """
        _require_key(key)
        if time is None:
            time = key.ttl
        if time is None:
            raise ValueError(f"'{key}'는 기본 TTL이 없어 time을 직접 지정해야 합니다.")

        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'의 만료 시간을 설정할 수 없습니다.")
            return False

        try:
            result = await cls.redis_instance.expire(key, time, **kwargs)
            LoggerCore.redis.debug(f"'{key}'의 만료 시간을 '{time}초'로 설정했습니다.")
            return result
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'의 만료시간 설정에 실패했습니다: {e}", exc_info=True)
            return False

    @classmethod
    async def ttl(cls, key: BoundKey) -> int:
        _require_key(key)
        if cls.redis_instance is None:
            LoggerCore.redis.warning(f"Redis가 초기화 되지 않았습니다. '{key}'의 TTL 값을 가져올 수 없습니다.")
            return -2

        try:
            ttl = await cls.redis_instance.ttl(key)
            LoggerCore.redis.debug(f"'{key}'는 '{ttl}초' 후에 만료됩니다.")
            return ttl
        except Exception as e:
            LoggerCore.redis.error(f"'{key}'의 TTL 값을 가져오는데 실패했습니다: {e}", exc_info=True)
            return -2
