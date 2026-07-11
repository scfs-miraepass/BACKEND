from app.schemas import Users, PointHistory, PointHistoryType

from core.core import ServiceCore
from core.security import get_password_hash
from core.config import settings
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    _Type = Users
else:
    _Type = object


class User(ServiceCore[Users], _Type):
    async def update_password(self, _new: str):
        """
        사용자의 비밀번호를 업데이트 합니다

        Args:
            _new: 새로운 비밀번호
        """
        async with self.session as session:
            user = await session.merge(self._payload)
            user.password = get_password_hash(_new)
            await session.commit()
        self._payload = user

    async def cache_clear(self):
        """
        사용자의 캐시를 삭제합니다.
        """
        await self.redis.delete(f"user:{self.id}")

    async def cache_update(self):
        """
        사용자의 데이터 캐시를 업데이트 합니다.
        """
        await self.redis.set(
            f"user:{self.id}",
            self.model_dump(),
            ttl=settings.service.session.expire_seconds,
        )

    async def create_history(
        self,
        changed: int,
        reason: str,
        *,
        memo: str | None = None,
        type: PointHistoryType = PointHistoryType.etc,
    ):
        """
        포인트 기록을 생성합니다.

        Args:
            changed: 변경된 포인트를 뜻합니다. 양수와 음수를 통해 입금및 출금이 처리 됩니다.
            reason: 포인트가 변경된 주 된 이유
            memo: 포인트를 처리한 유저가 입력하거나, 시스템의 의해서 추가적으로 확인 할 수 있는 이유
            type: 포인트가 변경된 종류 입니다.
        """
        async with self.session as session:
            session.add(
                PointHistory(
                    user_id=self.id,
                    changed_amount=changed,
                    reason=reason,
                    memo=memo,
                    type=type,
                )
            )

        # 포인트 기록 변경에 따른 캐시 삭제
        await self.redis.delete(f"point_history_count:{self.id}")
        await self.redis.delete_pattern(f"point_history:{self.id}:*")
