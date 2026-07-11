from sqlmodel import select

from app.schemas import Users

from .core import BaseCore
from .service import User


class ServiceClient(BaseCore):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def get_user(self, /, _id: int, *, cache: bool = False, lock: bool = False) -> User | None:
        """
        ID를 이용해 사용자를 가져옵니다.

        Args:
            _id: 사용자 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            lock: 조회후 Row-level Lock를 설정할 것 인가 여부

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
        return User(payload=payload)
