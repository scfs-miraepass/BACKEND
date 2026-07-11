from .core import BaseCore
from .service import User

from app.schemas import Users


class ServiceClient(BaseCore):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def get_user(self, _id: int) -> User | None:
        """
        ID를 이용해 사용자를 가져옵니다.

        Returns:
            User | None
        """
        async with self.session as session:
            payload = await session.get(Users, _id)
        return User(payload=payload)
