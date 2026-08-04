from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, Any
from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from pydantic import field_serializer

if TYPE_CHECKING:
    from .users import Users


class PointHistoryType(str, Enum):
    teacher = "teacher"  # 교사 지급
    cafe = "cafe"  # 음료 구매
    food = "food"  # 음식 구매
    etc = "etc"  # 기타
    grant = "grant"  # 학생 포인트 지급에 대한 교사 포인트 지급
    quest = "quest"  # 퀘스트 보상
    stamp = "stamp"  # 스탬프 발급
    stamp_bonus = "stamp_bonus"  # 스탬프 보너스


class PointHistory(SQLModel, table=True):
    id: Optional[int] = Field(None, primary_key=True, index=True)  # autoincrement

    user: "Users" = Relationship(back_populates="history")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)

    changed_amount: int = Field(description="변경된 포인트의 정도")

    # 기록 이유 (프론트에는 memo가 없는 경우 reason이 표기)
    # 기존 reason만 있다가 처리 이유를 따로 담을 필요성이 있어서 memo를 추가했지만
    # 기존에 있는 데이터 마이그레이션을 고려해 아래와 같이 분리함
    reason: str = Field(description="누구의 무엇의 의해서 포인트가 변경되었는지 이유")
    memo: Optional[str] = Field(
        None, description="포인트가 어떠한 사유로 변경되었는지 이유"
    )

    type: Optional[PointHistoryType] = Field(
        None, description="기록 종류", sa_column=Column(String(20))
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )

    @field_serializer("type")
    def serialize_type(self, type_value: Any, _info):
        if isinstance(type_value, PointHistoryType):
            return type_value.value
        return type_value

    @field_serializer("created_at")
    def serialize_created_at(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt
