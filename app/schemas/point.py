from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, Any
from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel, Relationship
from enum import Enum
from pydantic import field_validator

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

    @field_validator("type", mode="before")
    @classmethod
    def type_to_enum(cls, v: Any) -> Optional["PointHistoryType"]:
        if v is None:
            return v
        if isinstance(v, str):
            return PointHistoryType(v)
        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def created_at_validate(cls, v: Any) -> datetime:
        if isinstance(v, str):
            # The format from the log is like '2026-05-18T15:11:29'
            # which from iso format can handle.
            # If there's a 'Z' or timezone info, it's also handled.
            if v.endswith("Z"):
                v = v[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                # Handle cases without seconds or other formats if necessary
                return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        return v
