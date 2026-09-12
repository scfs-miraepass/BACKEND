from typing import TYPE_CHECKING
from app.schemas import KaraokeMembers

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

        if self.party:
            return KaraokeParty(self.party)
        party = await KaraokeParty.get_by_id(self.party_id)
        if party is None:
            raise RuntimeError()
        return KaraokeParty(party)

    async def accept(self):
        """
        초대를 수락합니다.
        """
        async with self.session as session:
            member = await session.merge(self._payload)
            member.pending = False

        self._payload = member
        await self.redis.delete(f"karaoke_members:{self.party_id}")
        self.logs.service_karaoke.info(
            f"노래방 파티 멤버 초대 수락 - 파티 ID {self.party_id}의 유저 {self.user_id}가 초대를 수락했습니다."
        )

    async def reject(self):
        """
        기본적으론 초대를 거절하는 목적으로 사용됩니다.
        단, 초대 상태 상관없이 DB에서 객체를 삭제하는 동작을 수행합니다.
        """
        async with self.session as session:
            member = await session.merge(self._payload)
            await session.delete(member)

        self._payload = None
        await self.redis.delete(f"karaoke_members:{self.party_id}")
        self.logs.service_karaoke.info(
            f"노래방 파티 멤버 초대 거절/삭제 - 파티 ID {self.party_id}의 유저 {self.user_id}가 초대를 거절/삭제했습니다."
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
