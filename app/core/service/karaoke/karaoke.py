from typing import TYPE_CHECKING
from sqlmodel import delete, select, col
from datetime import datetime

from app.schemas import Karaokes, KaraokeStatus, KaraokeBids, PointHistoryType, KaraokePartis

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
    karaoke_members:{karaoke_party.id} - karaoke_party.id의 파티 멤버 데이터
    karaoke:{karaoke.id}:member:{user.id} - karaoke.id의 파티 중에 user.id가 소속된 파티 ID

    - key에 들어가는 date요소의 포멧팅은 datetime의 기본 포멧팅인 YYYY-MM-DD으로 할 것.
    """

    @classmethod
    async def get_by_id(cls, karaoke_id: int, **kwargs) -> Karaoke | None:
        """
        ID를 기반으로 노래방 예약을 가져옵니다.

        Args:
            karaoke_id: ID

        Returns:
            Karaoke | None
        """
        return await cls._get_item(
            _id=karaoke_id, wrapper_cls=cls, model_cls=Karaokes, prefix="karaoke", ttl=60 * 5, **kwargs
        )

    @property
    def time_format(self) -> str:
        if self.time >= 8:
            return "점심"
        return f"{self.time}교시"

    async def delete(self):
        """
        노래방 예약을 삭제합니다.
        현재 최고 입찰이 있는 경우, 삭제 전에 해당 입찰을 취소(환불) 처리합니다.
        """
        highest = await self.get_highest()
        if highest is not None:
            await highest.cancel()

        async with self.session as session:
            exc = delete(Karaokes).where(col(Karaokes.id) == self.id)
            await session.execute(exc)

        await self.redis.delete(f"karaoke:{self.id}")
        await self.redis.delete(f"karaoke:{self.id}:*")
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
        return KaraokeBid(payload=KaraokeBids.model_validate(bid))

    async def get_final_bid(self) -> KaraokeBid | None:
        """
        최종(마지막) 입찰 기록을 DB에서 직접 조회합니다.

        `get_highest`가 사용하는 Redis 캐시는 경매 종료 시각 기준으로 TTL이 걸려 있어
        시간이 지나면 만료되므로, 경매가 끝난 뒤 최종 낙찰 내역(낙찰자)을 확인할 때는
        이 함수를 사용해야 합니다.

        Returns:
            KaraokeBid | None
        """
        async with self.session as session:
            query = select(KaraokeBids).where(KaraokeBids.auction_id == self.id).order_by(col(KaraokeBids.id).desc())
            row = (await session.execute(query)).scalars().first()

        return KaraokeBid(payload=row) if row is not None else None

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
        async with self.session as session:
            # 동시 입찰로 인한 레이스 컨디션(중복 최고가 인정 등)을 막기 위해
            # 경매 Row에 락을 걸어 같은 경매에 대한 입찰 처리를 직렬화합니다.
            lock_query = select(Karaokes).where(col(Karaokes.id) == self.id).with_for_update()
            locked_karaoke = (await session.execute(lock_query)).scalar_one_or_none()
            if locked_karaoke is None or locked_karaoke.status != KaraokeStatus.IN_PROGRESS:
                raise ValueError("The auction is not in progress.")

            # 락을 잡은 상태에서 DB 기준 최신(최고) 입찰을 다시 조회합니다.
            # (Redis 캐시는 동시 요청 사이에서 갱신 타이밍이 어긋날 수 있어 신뢰할 수 없습니다)
            highest = await self.get_final_bid()

            if highest is None:
                # 첫 입찰은 최소 입찰가 이상이기만 하면 됩니다.
                if amount < self.min_point:
                    raise ValueError(
                        f"The bid amount must be greater than or equal to the minimum bid ({self.min_point})."
                    )
            elif amount <= highest.amount:
                # 이후 입찰은 직전 최고가를 반드시 넘어야 합니다. (동일 금액으로 최고가를 가져갈 수 없음)
                raise ValueError(f"The bid amount must be greater than the current highest bid ({highest.amount}).")

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

            for user, deduct_amount in deductions:
                await user.point_deduct(
                    deduct_amount,
                    reason="노래방 예약",
                    memo=f"{self.date} {self.time_format} 노래방 예약",
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
        await self.redis.delete(f"karaoke:{self.id}:bids_history")  # 기록 캐시 무효화
        await self.redis.delete_pattern(f"karaoke_list:{self.date}")

        # 최고가 TTL은 종료 시간까지로 하며, 최소 60초
        now = datetime.now().astimezone() if self.end_time.tzinfo else datetime.now()
        ttl_seconds = int((self.end_time - now).total_seconds()) + 60
        ttl = max(60, ttl_seconds)

        dump_str = obj.model_dump_json()
        await self.redis.set(f"karaoke:{self.id}:highest", obj.model_dump(), ttl=ttl)  # 최고 입찰 갱신
        await self.redis.publish(f"ws_karaoke_{self.id}", dump_str)  # 구독 공지

        self.logs.service_karaoke.info(
            f"노래방 입찰 성공 - {self.id}({self.date} / {self.time})에 {bidder.name}({bidder.id})님이 {amount} 포인트로 입찰했습니다."
        )

        return KaraokeBid(payload=obj)

    async def create_party(self, leader: User) -> KaraokeParty:
        """
        현재 노래방 경매에 대한 새로운 파티를 생성합니다.

        Args:
            leader: 파티장이 될 유저

        Raises:
            ValueError: 이미 해당 경매에 자신이 파티장인 파티가 있거나 속해있는 파티가 있는 경우

        Returns:
            KaraokeParty
        """
        async with self.session as session:
            user_party = await leader.get_party(self)
            if user_party is not None:
                raise ValueError("User is already a leader or member of a party in this auction.")

            party = KaraokePartis(auction_id=self.id, leader_id=leader.id)
            session.add(party)
            await session.flush()

        self.logs.service_karaoke.info(
            f"파티 생성 성공 - 경매 {self.id}에 {leader.name}({leader.id})님이 파티(ID {party.id})를 생성했습니다."
        )
        return KaraokeParty(party)
