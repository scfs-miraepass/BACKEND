from typing import TYPE_CHECKING
from sqlmodel import delete, col

from app.schemas import Karaokes, KaraokeStatus, KaraokeBids, PointHistoryType

from ...core import ServiceCore
from ..user import User
from .bid import KaraokeBid
from .party import KaraokeParty

if TYPE_CHECKING:
    _Type = Karaokes
else:
    _Type = object


class Karaoke(ServiceCore[Karaokes], _Type):
    """
    노래방 서비스 관련된 Redis Key는

    karaoke:{karaoke.id} - karaoke.id에 대한 노래방 예약 데이터
    karaoke_list:{karaoke.date} - karaoke.date 날에 소속된 노래방 예약 목록 데이터
    karaoke:{karaoke.id}:highest - karaoke.id 의 최고 입찰 기록
    karaoke_party:{karaoke_party.id} - karaoke_party.id의 파티 데이터

    - key에 들어가는 date요소의 포멧팅은 datetime의 기본 포멧팅인 YYYY-MM-DD으로 할 것.
    """

    @property
    def time_format(self) -> str:
        if self.time >= 8:
            return "점심"
        return f"{self.time}교시"

    async def delete(self):
        """
        노래방 예약을 삭제합니다.
        """
        async with self.session as session:
            exc = delete(Karaokes).where(col(Karaokes.id) == self.id)
            await session.execute(exc)

        await self.redis.delete(f"karaoke:{self.id}")
        await self.redis.delete_pattern(f"karaoke_list:{self.date}")

        self.logs.service_karaoke.info(f"노래방 예약 삭제 - ID {self.id}({self.date} / {self.time})")

    async def set_status(self, _status: KaraokeStatus):
        """
        노래방 예약의 상태를 변경합니다.

        Args:
            _status: 변경하려는 예약의 상태
        """

        async with self.session as session:
            karaoke = await session.merge(self._payload)
            karaoke.status = _status

        await self.redis.delete(f"karaoke:{self.id}")
        await self.redis.delete_pattern(f"karaoke_list:{self.date}")
        self._payload = karaoke

        self.logs.service_karaoke.info(
            f"노래방 예약 상태 변경 - {self.id}({self.date} / {self.time})의 상태가 '{_status}'으로 변경되었습니다."
        )

    async def get_highest(self) -> KaraokeBid | None:
        """
        현재 경매의 최고가를 가져옵니다.

        Returns:
            KaraokeBid | None
        """
        bid = await self.redis.get(f"karaoke:{self.id}:highest")
        if bid is None:
            return None
        return KaraokeBid.model_validate(bid)

    async def add_bid(self, bidder: User, amount: int, party: KaraokeParty | None = None) -> KaraokeBid:
        """
        노래방 경매에 입찰합니다.

        Args:
            bidder: 입찰하는 유저
            amount: 입찰 금액
            party: 입찰하는 유저의 파티 고유 ID (선택 사항)

        Raises:
            ValueError: 입찰 조건(상태, 금액 등)을 만족하지 않을 경우 발생합니다.

        Returns:
            KaraokeBid
        """
        if self.status != KaraokeStatus.IN_PROGRESS:
            raise ValueError("경매가 진행 중인 상태가 아닙니다.")

        highest = await self.get_highest()
        if amount < (self.min_point if highest is None else highest.amount):
            raise ValueError(f"입찰 금액은 최소 입찰가({self.min_point}) 이상이어야 합니다.")

        # TODO: 입찰자(들)에게 입찰가 만큼의 돈이 있는가 확인 로직 필요함

        async with self.session as session:
            obj = KaraokeBids(
                auction_id=self.id, bidder_id=bidder.id, party_id=party.id if party is not None else None, amount=amount
            )
            session.add(obj)
            await session.flush()

        if party is None:
            await bidder.point_deduct(
                amount,
                reason="노래방 예약",
                memo=f"{self.date} {self.time_format} 노래방 예약",
                type=PointHistoryType.karaoke_bid,
            )  # 포인트 차감
        else:
            # TODO: 파티 멤버에게서 각각 돈을 빼도록 해야함
            ...

        if highest is not None:
            ...

        # TODO: 입찰시 기존 최고가 입찰자 포인트 환불, 파티가 있을경우 분리해서 환불이랑 지출 할 수 있도록

        await self.redis.delete(f"karaoke:{self.id}")
        await self.redis.delete_pattern(f"karaoke_list:{self.date}")

        await self.redis.set(f"karaoke:{self.id}:highest", obj.model_dump())  # 최고 입찰가 갱신
        # TODO: 위에 이거 TTL 설정필요

        return KaraokeBid(payload=obj)
