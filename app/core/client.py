from typing import Type, TypeVar

from sqlmodel import SQLModel, select

from app.schemas import Karaokes, PointHistory, Posts, Quests, Users

from .config import settings
from .core import BaseCore
from .service import History, Karaoke, Post, Quest, User

TModel = TypeVar("TModel", bound=SQLModel)
TWrapper = TypeVar("TWrapper")


class ServiceClient(BaseCore):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def _get_item(
        self,
        _id: int,
        wrapper_cls: Type[TWrapper],
        model_cls: Type[TModel],
        prefix: str,
        cache: bool,
        save_cache: bool,
        lock: bool,
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

    async def get_user(
        self,
        /,
        _id: int,
        *,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
    ) -> User | None:
        """
        ID를 이용해 사용자를 가져옵니다.

        Args:
            _id: 사용자 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 유저를 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            User | None
        """
        return await self._get_item(
            _id=_id,
            wrapper_cls=User,
            model_cls=Users,
            prefix="user",
            ttl=settings.service.session.expire_seconds,
            cache=cache,
            save_cache=save_cache,
            lock=lock,
        )

    async def get_post(
        self,
        /,
        _id: int,
        *,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
    ) -> Post | None:
        """
        ID를 이용해 게시글을 가져옵니다.

        Args:
            _id: 게시글 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            Post | None
        """
        return await self._get_item(
            _id=_id,
            wrapper_cls=Post,
            model_cls=Posts,
            prefix="post",
            ttl=60 * 60 * 24,
            cache=cache,
            save_cache=save_cache,
            lock=lock,
        )

    async def get_quest(
        self,
        /,
        _id: int,
        *,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
    ) -> Quest | None:
        """
        ID를 이용해 퀘스트를 가져옵니다.

        Args:
            _id: 퀘스트 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            Quest | None
        """
        return await self._get_item(
            _id=_id,
            wrapper_cls=Quest,
            model_cls=Quests,
            prefix="quest",
            ttl=60 * 5,
            cache=cache,
            save_cache=save_cache,
            lock=lock,
        )

    async def get_history(
        self, /, _id: int, *, cache: bool = False, save_cache: bool = True, lock: bool = False
    ) -> History | None:
        """
        ID를 이용해 포인트 기록을 가져옵니다.

        Args:
            _id: 포인트 기록 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            History | None
        """
        return await self._get_item(
            _id=_id,
            wrapper_cls=History,
            model_cls=PointHistory,
            prefix="point_history",
            ttl=60 * 5,
            cache=cache,
            save_cache=save_cache,
            lock=lock,
        )

    async def get_karaoke(
        self, /, _id: int, *, cache: bool = False, save_cache: bool = True, lock: bool = False
    ) -> Karaoke | None:
        """
        ID를 이용해 노래방 예약을 가져옵니다.

        Args:
            _id: 노래방 예약 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            Karaoke | None
        """
        return await self._get_item(
            _id=_id,
            wrapper_cls=Karaoke,
            model_cls=Karaokes,
            prefix="karaoke",
            ttl=60 * 5,
            cache=cache,
            save_cache=save_cache,
            lock=lock,
        )
