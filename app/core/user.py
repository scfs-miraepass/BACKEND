from app.schemas import Users

from .core import ServiceCore
from .security import get_password_hash
from .config import settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    _Type = Users
else:
    _Type = object


class User(ServiceCore, _Type):
    def __new__(cls, payload) -> User | None:
        if payload is None:
            return None
        return super().__new__(cls)

    def __init__(self, payload: Users | None):
        super().__init__()
        self._payload = payload

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

    async def update_password(self, _new: str):
        """
        사용자의 비밀번호를 업데이트 합니다

        Args:
            _new: 새로운 비밀번호
        """
        async with self.session as session:
            self._payload.password = get_password_hash(_new)
            session.add(self)
            await session.commit()

    async def cache_clear(self):
        """
        사용자의 캐시를 삭제합니다.
        """
        await self.redis.delete(f"user:{self.id}")

    async def cache_update(self):
        """
        사용자의 데이터 캐시를 업데이트 합니다.
        """
        await self.redis.set(f"user:{self.id}", self.model_dump(), ttl=settings.service.session.expire_seconds)
