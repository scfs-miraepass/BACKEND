from typing import TYPE_CHECKING

from sqlmodel import col, delete

from app.schemas import PointHistory, Users, UserType

from ..core import ServiceCore
from ..error import NotFound

if TYPE_CHECKING:
    _Type = PointHistory
else:
    _Type = object


class History(ServiceCore[PointHistory], _Type):
    async def delete(self, *, revert: bool = True, total_revert: bool = True):
        """
        포인트 기록을 삭제합니다

        Args:
            revert: 유저가 현재 보유중인 포인트에서 기록만큼 포인트를 차감해 되돌립니다.
            total_revert: 유저의 받은 포인트에서 포인트를 제외합니다. 단, 차감의 경우 적용되지 않습니다.

        Raises:
            ServiceError.NotFound: PointHistory를 소유하고 있는 User 객체를 찾지 못할 경우 발생합니다. revert또는 total_revert 인수가 True일 경우에만 발생합니다.
        """

        async with self.session as session:
            # history 삭제
            exc = delete(Users).where(col(Users.id) == self.id)
            await session.execute(exc)

            # User Point 관련 데이터 Revert 처리
            if revert or (total_revert and self.changed_amount > 0):
                # User Session 로드
                if self.user:
                    user = await session.merge(self.user)
                else:
                    user = await session.get(Users, self.user_id)

                if user is None:
                    raise NotFound("PointHistory.User Not Found")

                if revert:
                    user.point = max(0, user.point - self.changed_amount)
                if total_revert and self.changed_amount > 0:
                    user.total_point -= max(0, user.total_point - self.changed_amount)

                # 유저 데이터(포인트, 총합 포인트) 값 변경에 따른 캐시 삭제
                await self.redis.delete(f"user:{user.id}")
                if user.type == UserType.teacher or user.type == UserType.student:
                    await self.redis.delete_pattern(f"ranking:{user.type}:*")

        # 포인트 기록 변경에 따른 캐시 삭제
        await self.redis.delete(f"point_history_count:{self.user_id}")
        await self.redis.delete_pattern(f"point_history:{self.user_id}:*")

        self.logs.service_post.debug(f"포인트 기록 삭제 - ID {self.id}")
