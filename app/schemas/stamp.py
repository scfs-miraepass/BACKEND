from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from typing import TYPE_CHECKING, Any
from sqlalchemy import Column, DateTime, func, String
from datetime import datetime, timezone
from pydantic import field_serializer


if TYPE_CHECKING:
    from .users import Users


class StampType(str, Enum):
    """
    스탬프 종류 Enum
    - 부스 이름은 추후 수정될 수 있습니다.
    """

    BOOTH_1 = "쓰레기 투호"
    BOOTH_3 = "철권 한판"
    BOOTH_5 = "큐피트의 다트"
    BOOTH_6 = "제기찰겨? 날찰겨?"
    BOOTH_7 = "팔씨름 최강자전"
    BOOTH_8 = "부적꾸미기"
    BOOTH_9 = "누르기 챌린지"
    BOOTH_11 = "공놀이 괴물"
    BOOTH_12 = "철면피 노래방"
    BOOTH_13 = "절대음감"
    BOOTH_15 = "런닝맨"
    BOOTH_16 = "의자뺏기"
    BOOTH_17 = "단체줄넘기"
    BOOTH_18 = "수학 키캡"


class Stamps(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, description="고유 ID")
    stamp_type: StampType = Field(description="스탬프 종류", sa_column=Column(String(20)))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="스탬프 발급 일시",
    )

    user: "Users" = Relationship(back_populates="stamps")
    user_id: int = Field(
        foreign_key="users.id", ondelete="CASCADE", index=True, description="스탬프를 받은 유저의 고유 ID"
    )

    @field_serializer("created_at")
    def serialize_created_at(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt
