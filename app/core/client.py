from sqlmodel import select

from app.schemas import Users, Posts

from .core import BaseCore
from .service import User, Post
from .config import settings


class ServiceClient(BaseCore):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def get_user(
        self, /, _id: int, *, cache: bool = False, save_cache: bool = True, lock: bool = False
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
        if cache and not lock:
            cached_user = await self.redis.get(f"user:{_id}")
            if cached_user:
                return User(payload=Users.model_validate(cached_user))

        async with self.session as session:
            if lock:
                query = select(Users).where(Users.id == _id).with_for_update()
                result = await session.execute(query)
                payload: Users | None = result.scalar_one_or_none()
            else:
                payload = await session.get(Users, _id)

        if save_cache and payload is not None:
            await self.redis.set(
                f"user:{payload.id}",
                payload.model_dump(),
                ttl=settings.service.session.expire_seconds,
            )
        return User(payload=payload)

    async def get_post(
        self, /, _id: int, *, cache: bool = False, save_cache: bool = True, lock: bool = False
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
        if cache and not lock:
            cached_user = await self.redis.get(f"post:{_id}")
            if cached_user:
                return Post(payload=Posts.model_validate(cached_user))

        async with self.session as session:
            if lock:
                query = select(Posts).where(Posts.id == _id).with_for_update()
                result = await session.execute(query)
                payload: Posts | None = result.scalar_one_or_none()
            else:
                payload = await session.get(Posts, _id)

        if save_cache and payload is not None:
            await self.redis.set(
                f"post:{payload.id}",
                payload.model_dump(),
                ttl=60 * 60 * 24,
            )
        return Post(payload=payload)
