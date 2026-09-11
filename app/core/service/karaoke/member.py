from typing import TYPE_CHECKING
from app.schemas import KaraokeMembers

from sqlmodel import select

from ...core import ServiceCore
from ...core import DatabaseCore
from ...core import RedisCore


if TYPE_CHECKING:
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

    async def accept(self) -> None:
        """
        초대를 수락합니다.
        """
        async with self.session as session:
            member = await session.merge(self._payload)
            member.pending = False

        self._payload = member
        await self.redis.delete(f"karaoke_members:{self.party_id}")

    async def reject(self) -> None:
        """
        초대를 거절합니다.
        해당 멤버 기록을 삭제합니다.
        """
        async with self.session as session:
            member = await session.merge(self._payload)
            await session.delete(member)

        self._payload = None
        await self.redis.delete(f"karaoke_members:{self.party_id}")
