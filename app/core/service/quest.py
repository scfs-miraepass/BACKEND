from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypedDict, Unpack
from sqlmodel import delete, select, col, func

from app.schemas import Users, Quests, QuestCompletion, PointHistoryType, QuestAccept

from ..core import ServiceCore
from ..error import LimitExceeded, ExpiredError


if TYPE_CHECKING:
    from .user import User

    _Type = Quests
else:
    _Type = object


class QuestEditParams(TypedDict):
    title: str | None
    description: str | None
    reward: int | None
    end_date: datetime | None
    max_repeat: int | None


class Quest(ServiceCore[Quests], _Type):
    async def _cache_clear(self):
        await self.redis.delete(f"quest:{self.id}")
        await self.redis.delete("quests_count")
        await self.redis.delete_pattern("quests:*")

    async def delete(self):
        """
        퀘스트를 삭제합니다.
        """
        async with self.session as session:
            exc = delete(Quests).where(col(Quests.id) == self.id)
            await session.execute(exc)

        await self._cache_clear()

        self.logs.service_quest.info(
            f"퀘스트 삭제 - ID {self.id}({self.title[:10] + '...' if len(self.title) > 10 else self.title})"
        )

    async def edit(self, **kwargs: Unpack[QuestEditParams]):
        async with self.session as session:
            quest = await session.merge(self._payload)

            for key, value in kwargs.items():
                setattr(quest, key, value)
        self._payload = quest
        await self._cache_clear()

        self.logs.service_quest.info(f"퀘스트 수정 - ID {self.id}")

    async def complete(self, user: "User"):
        """
        퀘스트 완료 처리하고, 유저에게 보상을 지급합니다.

        Args:
            user: 유저

        Raises:
            ServiceError.ExpiredError: 퀘스트가 만료되었을 경우 발생합니다.
            ServiceError.LimitExceeded: 퀘스트 중복 참가 횟수를 모두 소진했을 경우 발생합니다.
        """
        now = datetime.now(timezone.utc)
        if self.end_date < now:
            raise ExpiredError("Quest duration ended.")

        async with self.session as session:
            count = await self.complete_count(user)
            if count >= self.max_repeat:
                raise LimitExceeded("Maximum participation limit reached.")

            author = self.author
            if not author:
                author = await session.get(Users, self.author_id)

            await user.point_grant(
                amount=self.reward,
                reason="퀘스트 완료 보상",
                memo=f"{author.name} 선생님의 '{self.title}' 퀘스트 완료 보상",
                type=PointHistoryType.quest,
            )
            session.add(QuestCompletion(quest_id=self.id, user_id=user.id))

        self.logs.service_quest.info(f"퀘스트 완료 - {user.id}({user.name})가 {self.id} 완료")

    async def complete_count(self, user: "User") -> int:
        """
        유저가 퀘스트를 몇 번 완료 했는지를 가져옵니다.

        Args:
            user: 유저

        Returns:
            Int
        """
        async with self.session as session:
            query = (
                select(func.count())
                .select_from(QuestCompletion)
                .where(
                    QuestCompletion.quest_id == self.id,
                    QuestCompletion.user_id == user.id,
                )
            )
            result = await session.execute(query)
            count = result.scalar_one()
        return count

    async def accept(self, user: "User"):
        """
        학생이 퀘스트를 수락하도록 기록합니다. 중복 수락은 허용하지 않습니다.
        """
        async with self.session as session:
            query = (
                select(func.count())
                .select_from(QuestAccept)
                .where(
                    QuestAccept.quest_id == self.id,
                    QuestAccept.user_id == user.id,
                )
            )
            result = await session.execute(query)
            count = result.scalar_one()
            if count > 0:
                return

            session.add(QuestAccept(quest_id=self.id, user_id=user.id))
            await session.flush()

        try:
            await self._cache_clear()
        except Exception:
            pass

        self.logs.service_quest.info(f"퀘스트 수락 - {user.id}({user.name}) 가 {self.id} 수락")

    async def list_acceptances(self):
        """
        수락한 유저 목록을 반환합니다.
        """
        async with self.session as session:
            query = (
                select(Users).join(QuestAccept, QuestAccept.user_id == Users.id).where(QuestAccept.quest_id == self.id)
            )
            result = await session.execute(query)
            users = list(result.scalars().all())
        return users

    async def has_accepted(self, user: "User") -> bool:
        async with self.session as session:
            query = (
                select(func.count())
                .select_from(QuestAccept)
                .where(
                    QuestAccept.quest_id == self.id,
                    QuestAccept.user_id == user.id,
                )
            )
            result = await session.execute(query)
            count = result.scalar_one()
        return count > 0

    async def remove_accept(self, user: "User"):
        async with self.session as session:
            exc = delete(QuestAccept).where(
                QuestAccept.quest_id == self.id,
                QuestAccept.user_id == user.id,
            )
            await session.execute(exc)
            await session.flush()

        # invalidate cache after removal
        try:
            await self._cache_clear()
        except Exception:
            pass

        self.logs.service_quest.info(f"퀘스트 수락 취소 - {user.id}({user.name}) 가 {self.id} 취소")
