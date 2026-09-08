from typing import TYPE_CHECKING
from app.schemas import KaraokePartis, KaraokeMembers, Users

from sqlmodel import select

from ...error import NotFound
from ...core import ServiceCore
from ..user import User


if TYPE_CHECKING:
    _Type = KaraokePartis
else:
    _Type = object


class KaraokeParty(ServiceCore[KaraokePartis], _Type):
    async def get_members(self) -> list[User]:
        """
        현재 파티에 소속된 유저들을 가져옵니다.
        파티 대표자 유저는 포함하지 않습니다.

        Raises:
            ServiceError.NotFound: 유저 정보를 가져오지 못하거나, 찾지 못할 경우 발생합니다.

        Returns:
            list[User]
        """
        async with self.session as session:
            query = select(KaraokeMembers).where(KaraokeMembers.party_id == self.id)
            exc = await session.execute(query)
            payload = exc.scalars().all()

            return_obj: list[User] = []
            for i in payload:
                cached = await self.redis.get(f"user:{i.user_id}")
                user_payload = cached
                if cached is None:
                    user_payload = await session.get(Users, i.user_id)
                    if user_payload is None:
                        raise NotFound("Party Member User not found!")

                return_obj.append(User(payload=user_payload))

        return return_obj

    async def set_dispersed(self, dispersed: bool):
        """
        파티의 해산 여부를 변경합니다.

        Args:
            dispersed: 변경하려는 해산 여부
        """

        async with self.session as session:
            party = await session.merge(self._payload)
            party.dispersed = dispersed

        await self.redis.delete(f"karaoke_party:{self.id}")
        self._payload = party
