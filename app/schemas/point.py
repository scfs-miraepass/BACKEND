from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel, Relationship
from enum import Enum

if TYPE_CHECKING:
    from .users import Users


class PointHistoryType(str, Enum):
    teacher = "teacher"  # 교사 지급
    cafe = "cafe"  # 음료 구매
    food = "food"  # 음식 구매
    etc = "etc"  # 기타
    grant = "grant"  # 학생 포인트 지급에 대한 교사 포인트 지급


class PointHistory(SQLModel, table=True):
    id: Optional[int] = Field(None, primary_key=True)  # autoincrement

    user: "Users" = Relationship(back_populates="history")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")

    changed_amount: int = Field(description="변경된 포인트의 정도")
    reason: str = Field(description="이유")

    type: Optional[PointHistoryType] = Field(None, description="기록 종류")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
