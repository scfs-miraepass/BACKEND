from typing import TypeVar, Type
from functools import lru_cache
from hangulpy import split_hangul_string
from math import floor
from dataclasses import dataclass
from sqlmodel import SQLModel, select

from .database import DatabaseCore
from .loggers import LoggerCore
from .redis import RedisCore

T = TypeVar("T")

TModel = TypeVar("TModel", bound=SQLModel)
TWrapper = TypeVar("TWrapper")


@dataclass
class DutchPayReturn:
    member: int
    leader: int


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

    @classmethod
    def dutch_pay(cls, amount: int, party_members: int) -> DutchPayReturn:
        """
        대표자와 파티 멤버가 각자 얼마 씩 분배해야하는지 계산하는 함수
        100원 단위로 절사되며, 절사된 금액은 대표자에게 적용됩니다.

        Args:
            amount: 더치페이 해야하는 금액
            party_members: 대표자를 포함한, 모든 파티원의 인원 수

        Returns:
            DutchPayReturn
        """
        member_share = floor(amount / (party_members * 100)) * 100
        leader_share = amount - (member_share * (party_members - 1))

        return DutchPayReturn(member=member_share, leader=leader_share)

    async def _get_item(
        self,
        _id: int,
        wrapper_cls: Type[TWrapper],
        model_cls: Type[TModel],
        prefix: str,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
        ttl: int = 60,
    ) -> TWrapper | None:
        if cache and not lock:
            cached = await self.redis.get(f"{prefix}:{_id}")
            if cached:
                return wrapper_cls(payload=model_cls.model_validate(cached))

        async with self.session as session:
            if lock:
                query = select(model_cls).where(getattr(model_cls, "id") == _id).with_for_update()
                result = await session.execute(query)
                payload: TModel | None = result.scalar_one_or_none()
            else:
                payload = await session.get(model_cls, _id)

        if save_cache and payload is not None:
            await self.redis.set(f"{prefix}:{getattr(payload, 'id')}", payload.model_dump(), ttl=ttl)
        return wrapper_cls(payload=payload)


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
