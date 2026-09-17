from inspect import isroutine
from functools import wraps
from typing import TYPE_CHECKING
from app.schemas import KaraokeMembers
from app.schemas.core import SchemaCore

from sqlmodel import select

from ...core import ServiceCore
from ...core import DatabaseCore
from ...core import RedisCore
from ..user import User


if TYPE_CHECKING:
    from .party import KaraokeParty

    _Type = KaraokeMembers
else:
    _Type = object


class KaraokeMember(ServiceCore[KaraokeMembers], _Type):
    def __getattribute__(self, name):
        # reject()는 DB에서 멤버를 삭제하며 `_payload`를 None으로 비운다.
        # 삭제된 이후 이 객체의 메서드가 다시 호출되는 것을 막기 위해, KaraokeMember에
        # 한해서만 메서드 호출 시점에 `_payload`가 살아있는지 확인한다.
        attr = super().__getattribute__(name)
        if callable(attr) and isroutine(attr) and not name.startswith("__"):

            @wraps(attr)
            def wrapper(*args, **kwargs):
                if super(KaraokeMember, self).__getattribute__("_payload") is None:
                    raise RuntimeError("This object has been deleted.")
                return attr(*args, **kwargs)

            return wrapper
        return attr

    @classmethod
    async def get_member(cls, party_id: int, user_id: int) -> "KaraokeMember | None":
        """
        파티 ID와 유저 ID를 통해 노래방 파티 멤버 객체를 가져옵니다.

        Args:
            party_id: 파티 고유 ID
            user_id: 파티에 소속된 멤버의 유저 ID
        """
        redis_key = f"karaoke_party_member:{party_id}:{user_id}"
        cached = await RedisCore.get(redis_key)

        if cached:
            return cls(payload=KaraokeMembers.model_validate(cached))

        async with DatabaseCore.session() as session:
            query = select(KaraokeMembers).where(KaraokeMembers.party_id == party_id, KaraokeMembers.user_id == user_id)
            exc = await session.execute(query)
            payload = exc.scalar_one_or_none()

            if payload is None:
                return None

            await RedisCore.set(redis_key, payload.model_dump(), ttl=60 * 60)

            return cls(payload=payload)

    async def get_party(self) -> "KaraokeParty":
        """
        이 멤버 객체가 소속된 파티를 가져옵니다.

        Raises:
            RuntimeError: 파티가 없는 경우 발생합니다. 논리상 발생할 수 없습니다.
        """
        from .party import KaraokeParty

        # `self.party`(ORM relationship)는 lazy-load라 원본 세션이 닫힌 뒤 접근하면
        # DetachedInstanceError가 발생한다. 항상 로드되어 있는 `party_id`로 다시 조회한다.
        party = await KaraokeParty.get_by_id(self.party_id)
        if party is None:
            raise RuntimeError()
        return KaraokeParty(party)

    async def accept(self):
        """
        초대를 수락합니다.
        """
        async with self.session as session:
            party_obj = await self.get_party()
            member = await session.merge(self._payload)
            member.pending = False
            member.accepted_at = SchemaCore.now()

        self._payload = member
        await self.redis.delete(f"karaoke_members:{self.party_id}")
        await self.redis.delete(f"karaoke_party_member:{self.party_id}:{self.user_id}")
        await self.redis.delete(f"karaoke:{party_obj.auction_id}:member:{self.user_id}")
        self.logs.service_karaoke.info(
            f"노래방 파티 멤버 초대 수락 - 파티 ID {self.party_id}의 유저 {self.user_id}가 초대를 수락했습니다."
        )

    async def reject(self):
        """
        기본적으론 초대를 거절하는 목적으로 사용됩니다.
        단, 초대 상태 상관없이 DB에서 객체를 삭제하는 동작을 수행합니다.
        """
        # `_payload`를 비우고 나면 위임(`__getattribute__`)으로 필드에 접근할 수 없으므로 미리 보관합니다.
        party_id, user_id = self.party_id, self.user_id

        async with self.session as session:
            party_obj = await self.get_party()
            member = await session.merge(self._payload)
            await session.delete(member)

        self._payload = None
        await self.redis.delete(f"karaoke_members:{party_id}")
        await self.redis.delete(f"karaoke_party_member:{party_id}:{user_id}")
        await self.redis.delete(f"karaoke:{party_obj.auction_id}:member:{user_id}")
        self.logs.service_karaoke.info(
            f"노래방 파티 멤버 초대 거절/삭제 - 파티 ID {party_id}의 유저 {user_id}가 초대를 거절/삭제했습니다."
        )

    async def leave(self):
        """
        이 멤버가 파티에서 나감니다.

        Raises:
            RuntimeError: 유저가 없는 경우 발생합니다. 논리상 발생할 수 없습니다.
        """
        karaoke = await self.get_party()
        user = await User.get_by_id(self.user_id)
        if user is None:
            raise RuntimeError()
        await karaoke.kick_members(user)
