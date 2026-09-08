from typing import TYPE_CHECKING
from sqlmodel import delete, col

from app.schemas import Karaokes

from ..core import ServiceCore

if TYPE_CHECKING:
    _Type = Karaokes
else:
    _Type = object


class Karaoke(ServiceCore[Karaokes], _Type):
    """
    노래방 서비스 관련된 Redis Key는

    karaoke:{karaoke.id}: karaoke.id에 대한 노래방 예약 데이터
    karaoke_list:{karaoke.date}: karaoke.date 날에 소속된 노래방 예약 목록 데이터

    - key에 들어가는 date요소의 포멧팅은 datetime의 기본 포멧팅인 YYYY-MM-DD으로 할 것.
    """

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
