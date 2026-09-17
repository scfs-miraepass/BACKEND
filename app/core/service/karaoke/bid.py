from typing import TYPE_CHECKING
from app.schemas import KaraokeBids, PointHistoryType

from ..user import User

from ...core import ServiceCore
from .party import KaraokeParty

if TYPE_CHECKING:
    _Type = KaraokeBids
else:
    _Type = object


class KaraokeBid(ServiceCore[KaraokeBids], _Type):
    async def get_bidder(self) -> User:
        """
        입찰한 유저를 가져옵니다

        Raises:
            RuntimeError: 입찰한 유저가 없는 경우 발생합니다. 이론상 발생할 수 없습니다.

        Returns:
            User
        """
        bidder = await User.get_by_id(self.bidder_id)
        if bidder is None:
            raise RuntimeError("It has to be there, but it’s not..!")
        return bidder

    async def get_party(self) -> KaraokeParty | None:
        """
        입찰한 파티를 가져옵니다.

        Returns:
            KaraokeParty | None
        """
        if self.party_id is None:
            return None

        return await KaraokeParty.get_by_id(self.party_id)

    async def cancel(self):
        """
        예약 경매 입찰을 취소합니다.
        유찰이 발생하는 경우 호출되며, 취소시 입찰한 금액은 다시 지급됩니다.

        Raises:
            RuntimeError: 경매 또는 파티를 찾을 수 없는 경우 발생합니다. 이론상 발생할 수 없습니다.
        """
        from .karaoke import Karaoke

        async with self.session:
            auction = await Karaoke.get_by_id(self.auction_id)
            if auction is None:
                raise RuntimeError("It has to be there, but it’s not..!")

            bidder = await self.get_bidder()  # 입찰자 가져오기

            party_members: list[User] = []
            if self.party_id is not None:
                # 파티 객체 가져오기
                party = await self.get_party()
                if party is None:
                    raise RuntimeError("It has to be there, but it’s not..!")

                # 파티에 참여한 사용자 가져오기 (입찰 이후 새로 합류한 멤버는 제외하고,
                # 입찰 당시 실제로 비용을 분담했던 인원만 복원합니다)
                party_members = await party.get_members_before(self.created_at)

            deductions = self.build_dutch_pay_deductions(bidder, self.amount, party_members)

            # 실제 포인트 처리
            for user, deduct_amount in deductions:
                await user.point_grant(
                    deduct_amount,
                    reason="노래방 예약 취소",
                    memo=f"{auction.date} {auction.time_format} 노래방 예약 취소로 인한 환불",
                    type=PointHistoryType.karaoke_cancel,
                )

            self.logs.service_karaoke.info(
                f"노래방 입찰 취소 (환불) - ID {self.auction_id}의 입찰({self.amount} 포인트)이 취소되었습니다."
            )
