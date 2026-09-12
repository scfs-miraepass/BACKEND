from typing import TYPE_CHECKING
from app.schemas import KaraokePartis, KaraokeMembers

from sqlmodel import col, select

from ...error import Conflict, NotFound
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
        self.logs.service_karaoke.info(
            f"노래방 파티 해산 상태 변경 - 파티 ID {self.id}의 해산 상태가 {dispersed}로 변경되었습니다."
        )

    async def _invalidate_member_caches(self):
        """
        이 파티의 리더 및 멤버(대기중인 초대 포함)가 들고 있는
        `User.get_party()` 캐시(`karaoke:{auction_id}:member:{user_id}`)를 무효화합니다.

        파티가 해산되거나 강퇴로 인해 새 파티로 대체될 때 호출되며,
        캐시 TTL(5분)이 만료될 때까지 기다리지 않고 관련 유저들이 즉시 최신 상태를
        조회할 수 있도록 합니다.
        """
        async with self.session as session:
            query = select(KaraokeMembers.user_id).where(KaraokeMembers.party_id == self.id)
            result = await session.execute(query)
            user_ids = {row[0] for row in result.all()}

        user_ids.add(self.leader_id)
        for user_id in user_ids:
            await self.redis.delete(f"karaoke:{self.auction_id}:member:{user_id}")
            await self.redis.delete(f"karaoke_party_member:{self.id}:{user_id}")

    async def disperse(self):
        """
        파티를 해산합니다.
        파티장이 자발적으로 파티를 해산할 때 사용되며,
        기존 파티/멤버(KaraokeMember) 데이터는 삭제하지 않고 해산 상태로만 변경합니다.
        """
        await self.set_dispersed(True)
        await self.redis.delete(f"karaoke_members:{self.id}")
        await self._invalidate_member_caches()

        self.logs.service_karaoke.info(f"노래방 파티 자진 해산 - 파티 ID {self.id}가 해산되었습니다.")

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

        한 유저는 하나의 경매에서 단 하나의 파티에만 소속될 수 있으므로,
        초대 대상이 같은 경매의 다른 파티(자기 자신 포함)에 이미 소속되어 있거나
        초대 대기중인 경우 초대를 거부합니다.

        Args:
            user: 초대할 유저

        Raises:
            ValueError: 해산된 파티에 초대하거나, 파티장 자신을 초대할 경우 발생합니다.
            ServiceError.Conflict: 초대 대상이 이 경매의 파티에 이미 소속/초대되어 있을 경우 발생합니다.

        Returns:
            KaraokeMember: 생성된 멤버 객체
        """
        if self.dispersed:
            raise ValueError("Cannot invite a user to a dispersed party.")

        if user.id == self.leader_id:
            raise ValueError("The party leader is already in the party.")

        async with self.session as session:
            # 같은 경매의 해산되지 않은 파티 중, 초대 대상이 리더이거나 멤버(대기중 포함)인 파티를 찾습니다.
            query = (
                select(KaraokePartis.id)
                .outerjoin(KaraokeMembers, col(KaraokeMembers.party_id) == col(KaraokePartis.id))
                .where(
                    KaraokePartis.auction_id == self.auction_id,
                    KaraokePartis.dispersed == False,  # noqa: E712
                    (KaraokePartis.leader_id == user.id) | (KaraokeMembers.user_id == user.id),
                )
            )
            exists = (await session.execute(query)).scalars().first()
            if exists is not None:
                if exists == self.id:
                    raise Conflict("The user is already invited to or a member of this party.")
                raise Conflict("The user already belongs to another party in this auction.")

            member = KaraokeMembers(party_id=self.id, user_id=user.id, pending=True)
            session.add(member)

        await self.redis.delete(f"karaoke_members:{self.id}")
        self.logs.service_karaoke.info(f"노래방 파티 유저 초대 - 파티 ID {self.id}에 유저 {user.id}를 초대했습니다.")
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
            await self.set_dispersed(True)

        # 기존 파티의 캐시 삭제
        await self.redis.delete(f"karaoke_party:{self.id}")
        await self.redis.delete(f"karaoke_members:{self.id}")
        await self._invalidate_member_caches()
        self.logs.service_karaoke.info(
            f"노래방 파티 멤버 강퇴 - 파티 ID {self.id}에서 유저 {user_ids}를 강퇴하고 새 파티 ID {new_party_model.id}를 생성했습니다."
        )

        return KaraokeParty(new_party_model)
