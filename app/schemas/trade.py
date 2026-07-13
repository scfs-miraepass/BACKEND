from sqlmodel import Field, SQLModel, Relationship
from typing import TYPE_CHECKING, Any
from sqlalchemy import Column, DateTime, func
from datetime import datetime, timezone
from pydantic import field_serializer

if TYPE_CHECKING:
    from .users import Users


class Trades(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, description="고유 ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="스탬프 발급 일시",
    )

    seller: "Users" = Relationship(back_populates="sells")
    seller_id: int = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        description="판매자 유저의 ID",
    )

    buyer: "Users" = Relationship(back_populates="buys")
    buyer_id: int = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        description="구매자 유저의 ID",
    )

    amount: int = Field(description="거래 금액")
    reason: str = Field(description="거래 이유")

    @field_serializer("created_at")
    def serialize_created_at(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt
