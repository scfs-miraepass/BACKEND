from typing import TYPE_CHECKING
from app.schemas import KaraokeBids

from ...core import ServiceCore

if TYPE_CHECKING:
    _Type = KaraokeBids
else:
    _Type = object


class KaraokeBid(ServiceCore[KaraokeBids], _Type):
    async def cancel(self):
        """
        예약 경매 입찰을 취소합니다.
        유찰이 발생하는 경우 호출되며, 취소시 입찰한 금액은 다시 지급됩니다.
        """

        # TODO: 한명 단독 입찰과 파티로 단체 입찰로 나뉘어서, 각각 포인트를 받은 만큼 다시 지급해야함
