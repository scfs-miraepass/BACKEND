from .core import BaseCore
from .service import User

from app.schemas import Users


class ServiceClient(BaseCore):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def get_user(self, _id: int, *, cache: bool = False) -> User | None:
        """
        ID를 이용해 사용자를 가져옵니다.

        Returns:
            User | None
        """
        if cache:
            cached_user = await self.redis.get(f"user:{_id}")
            if cached_user:
                return User(payload=Users.model_validate(cached_user))

        async with self.session as session:
            payload = await session.get(Users, _id)
        return User(payload=payload)
