from datetime import datetime
from typing import TYPE_CHECKING

from app.schemas import (
    PointHistory,
    PointHistoryType,
    PostContent,
    Posts,
    Quests,
    UserPermission,
    Users,
    UserType,
)

from ..core import ServiceCore
from ..error import Forbidden
from ..security import get_password_hash
from .history import History
from .post import Post
from .quest import Quest

if TYPE_CHECKING:
    _Type = Users
else:
    _Type = object


class User(ServiceCore[Users], _Type):
    @property
    def permission(self) -> UserPermission:
        return UserPermission(self.permissions)

    async def update_password(self, _new: str):
        """
        사용자의 비밀번호를 업데이트 합니다

        Args:
            _new: 새로운 비밀번호
        """
        async with self.session as session:
            user = await session.merge(self._payload)
            user.password = get_password_hash(_new)
        self._payload = user
        await self.redis.delete(f"user:{self.id}")

    async def create_history(
        self,
        changed: int,
        reason: str,
        *,
        memo: str | None = None,
        type: PointHistoryType = PointHistoryType.etc,
    ) -> History:
        """
        포인트 기록을 생성합니다.

        Args:
            changed: 변경된 포인트를 뜻합니다. 양수와 음수를 통해 입금및 출금이 처리 됩니다.
            reason: 포인트가 변경된 주 된 이유
            memo: 포인트를 처리한 유저가 입력하거나, 시스템의 의해서 추가적으로 확인 할 수 있는 이유
            type: 포인트가 변경된 종류 입니다.

        Returns:
            History
        """
        async with self.session as session:
            obj = PointHistory(
                user_id=self.id,
                changed_amount=changed,
                reason=reason,
                memo=memo,
                type=type,
            )
            session.add(obj)
            await session.flush()

        # 포인트 기록 변경에 따른 캐시 삭제
        await self.redis.delete(f"point_history_count:{self.id}")
        await self.redis.delete_pattern(f"point_history:{self.id}:*")

        self.logs.service_point.debug(
            f"포인트 기록 생성 - ID {obj.id} ({reason[:10] + '...' if len(reason) > 10 else reason})"
        )
        return History(payload=obj)

    async def point_grant(
        self,
        amount: int,
        *,
        reason: str,
        memo: str | None = None,
        type: PointHistoryType | None = None,
    ):
        """
        포인트를 지급합니다.

        Args:
            amount: 지급하려는 포인트
            reason: 포인트를 지급하는 이유
            memo: 포인트를 지급하는 추가적인 이유
            type: 포인트를 지급하는 이유의 카테고리(종류)
        """
        if type is None:
            type = PointHistoryType.etc

        async with self.session as session:
            user = await session.merge(self._payload)
            user.point += amount

            history = await self.create_history(
                changed=amount, reason=reason, memo=memo, type=type
            )

        await self.redis.delete(f"user:{self.id}")
        if user.type == UserType.teacher or user.type == UserType.student:
            await self.redis.delete_pattern(f"ranking:{str(user.type)}:*")

        self.logs.service_point.info(
            f"포인트 지급 - {self.name}({self.id}) +{amount} (기록 ID {history.id})"
        )
        self._payload = user

    async def point_deduct(
        self,
        amount: int,
        *,
        reason: str,
        memo: str | None = None,
        type: PointHistoryType | None = None,
    ):
        """
        포인트를 차감합니다.

        Args:
            amount: 차감하려는 포인트
            reason: 포인트를 차감하는 이유
            memo: 포인트를 차감하는 추가적인 이유
            type: 포인트를 차감하는 이유의 카테고리(종류)

        Raises:
            ValueError: 보유중인 포인트가 부족할 경우 발생합니다.
        """
        if self.point < amount:
            raise ValueError("Insufficient points. Points cannot be less than 0.")

        if type is None:
            type = PointHistoryType.etc

        async with self.session as session:
            user = await session.merge(self._payload)
            user.point -= amount

            history = await self.create_history(
                changed=(amount * -1), reason=reason, memo=memo, type=type
            )

        await self.redis.delete(f"user:{self.id}")
        if user.type == UserType.teacher or user.type == UserType.student:
            await self.redis.delete_pattern(f"ranking:{str(user.type)}:*")

        self.logs.service_point.info(
            f"포인트 차감 - {self.name}({self.id}) +{amount} (기록 ID {history.id})"
        )
        self._payload = user

    async def create_post(self, *, title: str, content: dict) -> Post:
        """
        게시글을 생성합니다.

        Args:
            title: 게시글의 제목
            content: 게시글의 본문 데이터

        Returns:
            Post
        """
        async with self.session as session:
            obj = Posts(title=title, author_id=self.id)
            obj.content = PostContent(data=content)

            session.add(obj)
            await session.flush()

        await self.redis.delete("posts_count")
        await self.edis.delete_pattern("posts:list:*")

        self.logs.service_post.info(
            f"게시글 생성 - ID {obj.id} ({obj.title[:10] + '...' if len(obj.title) > 10 else obj.title}) By. {self.name}({self.id})"
        )
        return Post(payload=obj)

    async def create_quest(
        self,
        *,
        title: str,
        description: str,
        reward: int,
        end_date: datetime,
        max_repeat: int = 1,
    ) -> Quest:
        """
        **[교사 전용]**
        퀘스트를 생성합니다.

        Args:
            title: 퀘스트의 제목
            description: 퀘스트의 내용
            reward: 퀘스트 완료시 지급할 포인트
            end_date: 퀘스트 모집 마감일자
            max_repeat: 퀘스트 중복 참가 횟수

        Raises:
           ServiceError.Forbidden: 사용자가 교사 또는 관리자가 아닐경우 발생합니다.

        Returns:
            Quest
        """
        if not self.is_admin and self.type != UserType.teacher:
            raise Forbidden("Quest create is for teachers only")

        async with self.session as session:
            obj = Quests(
                title=title,
                description=description,
                reward=reward,
                end_date=end_date,
                max_repeat=max_repeat,
                created_by_teacher_id=self.id,
            )

            session.add(obj)
            await session.flush()
        await self.redis.delete("quests_count")
        await self.redis.delete_pattern("quests:*")

        self.logs.service_quest.info(
            f"퀘스트 생성 - {self.id}({self.name}) 생성. ID {obj.id}({title[:10] if len(title) > 10 else title})"
        )
        return Quest(payload=obj)

    def has_permission(self, perm: UserPermission | int) -> bool:
        """
        권한을 소유중인지 확인합니다.

        Args:
            perm: 추가하려는 권한

        Returns:
            Bool
        """
        if isinstance(perm, int):
            perm = UserPermission(perm)
        return perm in self.permission

    async def add_permission(self, perm: UserPermission | int):
        """
        권한을 추가합니다.

        Args:
            perm: 추가하려는 권한

        Raises:
            ValueError: 추가하려는 권한이 이미 사용자에게 있는 경우 발생합니다.
        """
        if isinstance(perm, int):
            perm = UserPermission(perm)
        if self.has_permission(perm):
            raise ValueError("already have permission")

        async with self.session as session:
            user = await session.merge(self._payload)
            user.permissions = (self.permission | perm).value

        await self.redis.delete(f"user:{self.id}")
        self._payload = user

        self.logs.service.info(
            f"{self.id}({self.name})의 권한을 추가했습니다. (+{perm.name})"
        )

    async def remove_permission(self, perm: UserPermission | int):
        """
        권한을 제거합니다.

        Args:
            perm: 제거하려는 권한

        Raises:
            ValueError: 제거하려는 권한이 사용자에게 없는 경우 발생합니다.
        """
        if isinstance(perm, int):
            perm = UserPermission(perm)
        if not self.has_permission(perm):
            raise ValueError("not have permission")

        async with self.session as session:
            user = await session.merge(self._payload)
            user.permissions = (self.permission & ~perm).value

        await self.redis.delete(f"user:{self.id}")
        self._payload = user

        self.logs.service.info(
            f"{self.id}({self.name})의 권한을 제거했습니다. (-{perm.name})"
        )
