from typing import TypeVar
from functools import lru_cache
from hangulpy import split_hangul_string

from .database import DatabaseCore
from .loggers import LoggerCore
from .redis import RedisCore

T = TypeVar("T")


class BaseCore:
    def __init__(self):
        self.logs: LoggerCore = LoggerCore()
        self.redis: RedisCore = RedisCore()
        self.database: DatabaseCore = DatabaseCore()

    @property
    def session(self):
        return self.database.session()

    async def initialize(self):
        await self.redis.connect()
        await self.database.initialize()

    async def close(self):
        await self.redis.close()
        await self.database.dispose()

    @staticmethod
    @lru_cache(maxsize=128)
    def normalize_and_decompose(query: str) -> str:
        """
        검색어의 공백을 제거하고 한글 자모를 분리합니다.
        동일한 검색어에 대한 중복 연산을 방지하기 위해 캐싱을 사용합니다.
        """
        return "".join(split_hangul_string(query.replace(" ", "")))


class ServiceCore[T](BaseCore):
    def __new__(cls, payload: T | None):
        if payload is None:
            return None
        return super().__new__(cls)

    def __init__(self, payload: T | None):
        self._payload: T = payload
        super().__init__()

    def __str__(self):
        return str(self._payload)

    def __repr__(self):
        return repr(self._payload)

    def __getattribute__(self, name):
        if name == "_payload":
            return super().__getattribute__(name)

        payload = super().__getattribute__("_payload")
        if hasattr(payload, name):
            return getattr(payload, name)
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if name == "_payload":
            super().__setattr__(name, value)
            return

        payload = super().__getattribute__("_payload")
        if hasattr(payload, name):
            setattr(payload, name, value)
        else:
            super().__setattr__(name, value)
