from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import field_serializer
from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field, Relationship, SQLModel

from .core import SchemaCore

if TYPE_CHECKING:
    from .users import Users


class StampType(StrEnum):
    """
    스탬프 종류 Enum
    - 부스 이름은 추후 수정될 수 있습니다.
    """

    BOOTH_1 = "보석 십자수"
    BOOTH_3 = "페이스 페인팅"
    BOOTH_5 = "수학 문제 풀이" # 추후 이름 수정
    BOOTH_6 = "일러스트"
    BOOTH_7 = "주짓수"
    BOOTH_8 = "환경 퀴즈 맞추기"
    BOOTH_9 = "인권 키링"
    BOOTH_11 = "인권 나무"
    BOOTH_12 = "문제 다트"
    BOOTH_13 = "암호표 해독"


class Stamps(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, description="고유 ID")
    stamp_type: StampType = Field(description="스탬프 종류", sa_column=Column(String(20)))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(SchemaCore.timezone),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="스탬프 발급 일시",
    )

    user: Users = Relationship(back_populates="stamps")
    user_id: int = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        index=True,
        description="스탬프를 받은 유저의 고유 ID",
    )

    @field_serializer("created_at")
    def serialize_created_at(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return SchemaCore.sync_timezone(dt).isoformat()
        return dt
