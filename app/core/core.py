from typing import TYPE_CHECKING, TypeVar, Type
from functools import lru_cache
from hangulpy import split_hangul_string
from math import floor
from dataclasses import dataclass
from sqlmodel import SQLModel, select

from .database import DatabaseCore
from .loggers import LoggerCore
from .redis import RedisCore
from .redis_keys import BoundKey

if TYPE_CHECKING:
    from .service.user import User

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

    @classmethod
    def build_dutch_pay_deductions(cls, leader: "User", amount: int, members: list["User"]) -> list[tuple["User", int]]:
        """
        더치페이 대상 인원(대표자 + 파티원)에게 각자 부담할 금액을 배분합니다.
        `members`가 비어있으면(개인 입찰) 대표자가 전액을 부담합니다.

        Args:
            leader: 대표자(입찰자)
            amount: 분배할 전체 금액
            members: 대표자를 제외한 파티원 목록

        Returns:
            list[tuple[User, int]]: (유저, 배분된 금액) 목록. 대표자가 첫 번째 원소입니다.
        """
        if not members:
            return [(leader, amount)]

        point = cls.dutch_pay(amount, len(members) + 1)
        return [(leader, point.leader)] + [(member, point.member) for member in members]

    @classmethod
    async def _get_item(
        cls,
        _id: int,
        wrapper_cls: Type[TWrapper],
        model_cls: Type[TModel],
        key: BoundKey,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
        cache_exclude: frozenset[str] = frozenset(),
    ) -> TWrapper | None:
        """
        ID로 데이터를 조회해 `wrapper_cls`로 감싸 반환합니다.

        Args:
            _id: 조회할 데이터의 ID
            wrapper_cls: 반환할 서비스 클래스
            model_cls: 조회할 모델 클래스
            key: 캐시 Key (예: `Keys.User.ITEM(user_id=_id)`)
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 조회 후 캐시 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부
            cache_exclude: 캐시에 저장하지 않을 필드 (비밀번호 해시 등 민감한 값)
        """
        if cache and not lock:
            cached = await RedisCore.get(key)
            if cached:
                payload = model_cls.model_validate({**dict.fromkeys(cache_exclude), **cached})
                # 캐시에 없는 필드는 객체에서 제거해 '불러오지 않은 값'으로 둡니다.
                # None으로 남겨두면 이 객체를 session.merge()할 때 DB의 실제 값이 None으로 덮어써집니다.
                for name in cache_exclude:
                    payload.__dict__.pop(name, None)
                return wrapper_cls(payload=payload)

        async with DatabaseCore.session() as session:
            if lock:
                query = select(model_cls).where(getattr(model_cls, "id") == _id).with_for_update()
                result = await session.execute(query)
                payload: TModel | None = result.scalar_one_or_none()
            else:
                payload = await session.get(model_cls, _id)

        if save_cache and payload is not None:
            await RedisCore.set(key, payload.model_dump(exclude=set(cache_exclude)))
        return wrapper_cls(payload=payload)


class ServiceCore[T](BaseCore):
    def __new__(cls, payload: T | None):
        if payload is None:
            return None
        return super().__new__(cls)

    def __init__(self, payload: T | None):
        self._payload: T | None = payload
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
