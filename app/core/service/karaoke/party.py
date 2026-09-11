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
            wrapper_cls=cls,
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
        async with self.session:
            members = await self.get_member_models()

            return_obj: list[User] = []
            for i in members:
                user = await User.get_by_id(i.user_id)
                if user is None:
                    raise NotFound("Party Member User not found!")

                return_obj.append(user)

        return return_obj

    async def get_member_models(self) -> list[KaraokeMember]:
        """
        현재 파티에 소속된 유저들을 KaraokeMember 객체로 가져옵니다.

        Returns:
            list[KaraokeMember]
        """
        async with self.session as session:
            query = select(KaraokeMembers).where(KaraokeMembers.party_id == self.id, KaraokeMembers.pending == False)  # noqa: E712
            exc = await session.execute(query)
            payload = exc.scalars().all()

        await self.redis.set(f"karaoke_members:{self.id}", [item.model_dump() for item in payload], ttl=60 * 60 * 24)

        return payload

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

    async def get_pending_members(self) -> list[User]:
        """
        현재 파티에 초대되어 수락 대기중인 유저들을 가져옵니다.

        Returns:
            list[User]
        """
        async with self.session as session:
            query = select(KaraokeMembers).where(KaraokeMembers.party_id == self.id, KaraokeMembers.pending == True)  # noqa: E712
            exc = await session.execute(query)
            payload = exc.scalars().all()

            return_obj: list[User] = []
            for i in payload:
                user = await User.get_by_id(i.user_id)
                if user is not None:
                    return_obj.append(user)

        return return_obj

    async def invite_user(self, user: User) -> KaraokeMember:
        """
        특정 유저를 파티에 초대합니다.

        Args:
            user: 초대할 유저

        Returns:
            KaraokeMember: 생성된 멤버 객체
        """
        async with self.session as session:
            member = KaraokeMembers(party_id=self.id, user_id=user.id, pending=True)
            session.add(member)

        await self.redis.delete(f"karaoke_members:{self.id}")
        return KaraokeMember(member)

    async def kick_members(self, users: User | list[User]) -> "KaraokeParty":
        """
        파티 멤버를 퇴장처리 합니다.
        기존 파티의 멤버(KaraokeMember) 데이터를 삭제하지 않고,
        강퇴될 멤버를 제외한 나머지 인원들로 새로운 파티를 생성합니다.

        Args:
            users: 강퇴할 유저 또는 유저 목록

        Returns:
            KaraokeParty: 새로운 인원으로 구성된 새 파티 객체
        """

        async with self.session as session:
            current_members = await self.get_member_models()
            user_ids = [users.id] if isinstance(users, User) else [user.id for user in users]

            # 새로운 파티 객체 생성
            new_party_model = KaraokePartis(auction_id=self.auction_id, leader_id=self.leader_id, dispersed=False)
            session.add(new_party_model)

            await session.flush()

            # 제외될 멤버가 아닌 멤버들만 새 파티에 추가
            for member in current_members:
                if member.user_id not in user_ids:
                    new_member = KaraokeMembers(
                        party_id=new_party_model.id, user_id=member.user_id, pending=member.pending
                    )
                    session.add(new_member)

            # 기존 파티는 해산(dispersed) 처리하여 유효하지 않도록 만듦
            old_party = await session.merge(self._payload)
            old_party.dispersed = True

        # 기존 파티의 캐시 삭제
        await self.redis.delete(f"karaoke_party:{self.id}")
        await self.redis.delete(f"karaoke_members:{self.id}")
        self._payload = old_party

        return KaraokeParty(new_party_model)
