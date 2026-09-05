from datetime import date, datetime
from enum import StrEnum
from pydantic import field_serializer
from sqlmodel import SQLModel, Field, Index, Column, String, DateTime, Relationship, func

from .core import SchemaCore


class KaraokeStatus(StrEnum):
    scheduled = "Scheduled"  # 경매가 시작 되기전, 예정됨 시간
    progress = "Progress"  # 경매가 진행중
    appointment = "Appointment"  # 경매가 끝나 예약이 확정됨


class Karaoke(SQLModel, table=True):
    __tablename__ = "karaoke"
    __table_args__ = Index("ix_karaoke_date_time", "date", "time")

    date: date = Field(..., nullable=False, index=True, primary_key=True, description="예약 일자")
    time: int = Field(..., nullable=False, index=True, primary_key=True, description="예약 시간 (1~7교시, 점심시간 8)")

    status: KaraokeStatus = Field(
        default=KaraokeStatus.scheduled.value,
        sa_column=Column(String(20), nullable=False),
        description="현재 예약 상태",
    )

    start_time: datetime = Field(description="경매 시작 시간")
    end_time: datetime = Field(description="경매 종료 시간")

    min_point: int = Field(default=0, description="최소 입찰가")

    bids: list["KaraokeBid"] = Relationship(back_populates="auction", passive_deletes=True)


class KaraokeBid(SQLModel, table=True):
    __tablename__ = "karaoke_bid"

    id: int | None = Field(None, primary_key=True, index=True)

    auction: Karaoke = Relationship(back_populates="bids")
    auction_id: int = Field(foreign_key="karaoke.id", nullable=False, index=True, ondelete="CASCADE")

    amount: int = Field(nullable=False, description="입찰 금액")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(SchemaCore.timezone),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
        ),
    )

    # TODO: 누가 입찰했는지 추가해야함, 이때 입찰자는 여러명일 수 있음으로 파티로 따로 묶어서 하자
    # TODO: 경매의 최고 입찰가는 Redis에 저장하자

    @field_serializer("created_at")
    def serialize_created_at(self, dt, _info):
        if isinstance(dt, datetime):
            return SchemaCore.sync_timezone(dt).isoformat()
        return dt
