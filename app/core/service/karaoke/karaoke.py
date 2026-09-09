from typing import TYPE_CHECKING
from sqlmodel import delete, col
from datetime import datetime

from app.schemas import Karaokes, KaraokeStatus, KaraokeBids, PointHistoryType

from ...core import ServiceCore
from ...error import PointInsufficient
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
            ServiceError.PointInsufficient: 입찰자, 입찰하는 파티의 멤버가 포인트가 부족할 경우 발생합니다.

        Returns:
            KaraokeBid
        """
        if self.status != KaraokeStatus.IN_PROGRESS:
            raise ValueError("경매가 진행 중인 상태가 아닙니다.")

        highest = await self.get_highest()
        min_point = self.min_point if highest is None else highest.amount
        if amount < min_point:
            raise ValueError(f"입찰 금액은 최소 입찰가({min_point}) 이상이어야 합니다.")

        async with self.session as session:
            # 차감 대상 유저와 금액 목록 구성
            deductions: list[tuple[User, int]] = []
            if party is None:
                deductions.append((bidder, amount))
            else:
                party_members = await party.get_members()
                point = self.dutch_pay(amount, len(party_members) + 1)

                deductions.append((bidder, point.leader))
                for member in party_members:
                    deductions.append((member, point.member))

            # 차감할 포인트가 있는지 확인
            for user, deduct_amount in deductions:
                if user.point < deduct_amount:
                    raise PointInsufficient(user=user)

            # 실제 결제 처리
            reason = "노래방 예약"
            memo = f"{self.date} {self.time_format} 노래방 예약"

            for user, deduct_amount in deductions:
                await user.point_deduct(
                    deduct_amount,
                    reason=reason,
                    memo=memo,
                    type=PointHistoryType.karaoke_bid,
                )

            if highest is not None:
                # 기존에 최고가가 있는경우, 해당 입찰 취소처리
                await highest.cancel()

            # 입찰 기록 생성
            obj = KaraokeBids(
                auction_id=self.id, bidder_id=bidder.id, party_id=party.id if party is not None else None, amount=amount
            )
            session.add(obj)
            await session.flush()

        await self.redis.delete(f"karaoke:{self.id}")
        await self.redis.delete_pattern(f"karaoke_list:{self.date}")

        # 최고가 TTL은 종료 시간까지로 하며, 최소 60초
        now = datetime.now().astimezone() if self.end_time.tzinfo else datetime.now()
        ttl_seconds = int((self.end_time - now).total_seconds()) + 60
        ttl = max(60, ttl_seconds)

        await self.redis.set(f"karaoke:{self.id}:highest", obj.model_dump(), ttl=ttl)  # 최고 입찰 갱신

        return KaraokeBid(payload=obj)
