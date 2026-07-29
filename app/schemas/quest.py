from pydantic import field_serializer

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, func, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .users import Users


class Quests(SQLModel, table=True):
    id: Optional[int] = Field(
        primary_key=True,
        default=None,
        description="퀘스트 고유 ID",
        index=True,
    )

    title: str = Field(..., description="퀘스트 제목")
    description: str = Field(..., description="퀘스트 내용")

    reward: int = Field(..., description="퀘스트 보상 포인트")
    end_date: datetime = Field(..., description="퀘스트 종료 날짜", index=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="퀘스트를 작성한 시간",
    )

    author: "Users" = Relationship(back_populates="created_quest")
    author_id: int = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        index=True,
        description="퀘스트 생성 유저의 고유 ID",
    )

    completions: List["QuestCompletion"] = Relationship(back_populates="quest", passive_deletes=True)
    acceptances: List["QuestAccept"] = Relationship(back_populates="quest", passive_deletes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt


class QuestCompletion(SQLModel, table=True):
    __table_args__ = (Index("ix_questcompletion_user_id_quest_id", "user_id", "quest_id"),)

    id: Optional[int] = Field(
        primary_key=True,
        default=None,
        description="퀘스트 완료기록 고유 ID",
        index=True,
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="퀘스트 완료한 일자",
    )

    quest: Quests = Relationship(back_populates="completions")
    quest_id: int = Field(foreign_key="quests.id", ondelete="CASCADE", description="완료한 퀘스트 ID", index=True)

    user: "Users" = Relationship(back_populates="completion_quest")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", description="퀘스트를 완료한 유저 ID", index=True)

    @field_serializer("completed_at")
    def serialize_completed_at(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt


class QuestAccept(SQLModel, table=True):
    __table_args__ = (Index("ix_questaccept_user_id_quest_id", "user_id", "quest_id"),)

    id: Optional[int] = Field(
        primary_key=True,
        default=None,
        description="퀘스트 수락 기록 고유 ID",
        index=True,
    )

    accepted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="퀘스트 수락한 일자",
    )

    quest: Quest = Relationship(back_populates="acceptances")
    quest_id: int = Field(foreign_key="quest.id", ondelete="CASCADE", description="수락한 퀘스트 ID", index=True)

    user: "Users" = Relationship(back_populates="accepted_quests")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", description="퀘스트를 수락한 유저 ID", index=True)

    @field_serializer("accepted_at")
    def serialize_accepted_at(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt
