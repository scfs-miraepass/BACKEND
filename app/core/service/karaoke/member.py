from typing import TYPE_CHECKING
from app.schemas import KaraokeMembers

from ...core import ServiceCore


if TYPE_CHECKING:
    _Type = KaraokeMembers
else:
    _Type = object


class KaraokeMember(ServiceCore[KaraokeMembers], _Type):
    async def accept(self) -> None:
        """
        초대를 수락합니다.
        pending 상태를 True로 변경합니다.
        """
        async with self.session as session:
            member = await session.merge(self._payload)
            member.pending = False

        self._payload = member

    async def reject(self) -> None:
        """
        초대를 거절합니다.
        해당 멤버 기록을 삭제합니다.
        """
        async with self.session as session:
            member = await session.merge(self._payload)
            await session.delete(member)

        self._payload = None
