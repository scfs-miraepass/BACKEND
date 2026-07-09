from app.schemas import Users
from typing import cast

from .loggers import LoggerCore
from .redis import RedisCore
from .database import DatabaseCore


class ServiceCore:
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


class ServiceClient(ServiceCore):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def get_user(self, _id: int) -> Users | None:
        """
        ID를 이용해 사용자를 가져옵니다.

        Returns:
            schemas.Users | None
        """
        async with self.session as session:
            user = await session.get(Users, _id)
        return cast(Users | None, user)
