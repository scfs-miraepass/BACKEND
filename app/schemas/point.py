from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .users import Users


class PointHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)  # autoincrement

    user: "Users" = Relationship(back_populates="history")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")

    changed_amount: int = Field(description="변경된 포인트의 정도")
    reason: str = Field(description="이유")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
