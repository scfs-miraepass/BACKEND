from typing import TYPE_CHECKING
from app.schemas import KaraokePartis, KaraokeMembers

from sqlmodel import select

from ...error import NotFound
from ...core import ServiceCore
from ..user import User
from .member import KaraokeMember


if TYPE_CHECKING:
    _Type = KaraokePartis
else:
    _Type = object


class KaraokeParty(ServiceCore[KaraokePartis], _Type):
    @classmethod
    async def get_by_id(cls, party_id: int, **kwargs) -> KaraokeParty | None:
        """
        ID를 기반으로 경매 파티를 가져옵니다.

        Args:
            party_id: ID

        Returns:
            KaraokeParty | None
        """
        return await cls._get_item(
            _id=party_id,
            wrapper_cls=KaraokeParty,
            model_cls=KaraokePartis,
            prefix="karaoke_party",
            ttl=60 * 60 * 24,
            **kwargs,
        )

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
            query = select(KaraokeMembers).where(KaraokeMembers.party_id == self.id, KaraokeMembers.pending == False)  # noqa: E712
            exc = await session.execute(query)
            payload = exc.scalars().all()

            return_obj: list[User] = []
            for i in payload:
                user = await User.get_by_id(i.user_id)
                if user is None:
                    raise NotFound("Party Member User not found!")

                return_obj.append(user)

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

    async def invite_user(self, user_id: int) -> KaraokeMember:
        """
        특정 유저를 파티에 초대합니다.

        Args:
            user_id: 초대할 유저의 ID

        Returns:
            KaraokeMember: 생성된 멤버 객체
        """
        async with self.session as session:
            member = KaraokeMembers(party_id=self.id, user_id=user_id, pending=True)
            session.add(member)

        return KaraokeMember(member)
