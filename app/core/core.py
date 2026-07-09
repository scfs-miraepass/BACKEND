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
