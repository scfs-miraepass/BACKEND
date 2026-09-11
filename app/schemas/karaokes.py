from datetime import date as dt_date, datetime
from enum import StrEnum
from pydantic import field_serializer
from sqlmodel import SQLModel, Field, Index, Column, String, DateTime, Relationship, func

from .core import SchemaCore


class KaraokeStatus(StrEnum):
    PENDING = "Pending"  # 경매 시작 전 대기/예정 상태
    IN_PROGRESS = "In_Progress"  # 경매 진행 중 (Progress보다 명확함)
    CONFIRMED = "Confirmed"  # 경매 종료 후 예약 확정됨


class Karaokes(SQLModel, table=True):
    __tablename__ = "karaoke"
    __table_args__ = (Index("ix_karaoke_date_time", "date", "time"),)

    id: int | None = Field(default=None, primary_key=True, index=True)

    date: dt_date = Field(..., nullable=False, index=True, description="예약 일자")
    time: int = Field(..., nullable=False, description="예약 시간 (1~7교시, 점심시간 8)")

    status: KaraokeStatus = Field(
        default=KaraokeStatus.PENDING,
        sa_column=Column(String(20), nullable=False),
        description="현재 예약 상태",
    )

    start_time: datetime = Field(description="경매 시작 시간")
    end_time: datetime = Field(description="경매 종료 시간")

    min_point: int = Field(default=0, description="최소 입찰가")

    bids: list["KaraokeBids"] = Relationship(back_populates="auction", passive_deletes=True)
    parties: list["KaraokePartis"] = Relationship(back_populates="auction", passive_deletes=True)

    @field_serializer("start_time", "end_time")
    def serialize_datetime(self, dt, _info):
        if isinstance(dt, datetime):
            return SchemaCore.sync_timezone(dt).isoformat()
        return dt


class KaraokeBids(SQLModel, table=True):
    __tablename__ = "karaoke_bid"
    __table_args__ = (Index("ix_karaoke_auction_id_bidder_id", "auction_id", "bidder_id"),)

    id: int | None = Field(None, primary_key=True, index=True)

    auction: Karaokes = Relationship(back_populates="bids")
    auction_id: int = Field(
        foreign_key="karaoke.id", nullable=False, index=True, ondelete="CASCADE", description="연결된 경매의 고유 ID"
    )

    bidder_id: int = Field(foreign_key="users.id", nullable=False, description="입찰한 유저의 고유ID")
    party_id: int | None = Field(
        foreign_key="karaoke_party.id", nullable=True, description="입찰한 유저의 파티 고유 ID"
    )

    amount: int = Field(nullable=False, description="입찰 금액")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(SchemaCore.timezone),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
        ),
        description="입찰된 시간",
    )

    @field_serializer("created_at")
    def serialize_created_at(self, dt, _info):
        if isinstance(dt, datetime):
            return SchemaCore.sync_timezone(dt).isoformat()
        return dt


class KaraokePartis(SQLModel, table=True):
    __tablename__ = "karaoke_party"
    __table_args__ = (Index("ix_karaoke_auction_id_leader_id", "auction_id", "leader_id"),)

    id: int | None = Field(None, primary_key=True, index=True)

    auction: Karaokes = Relationship(back_populates="parties")
    auction_id: int = Field(
        foreign_key="karaoke.id", nullable=False, index=True, ondelete="CASCADE", description="연결된 경매의 고유 ID"
    )

    leader_id: int = Field(
        foreign_key="users.id", nullable=False, index=True, ondelete="CASCADE", description="파티 대표 유저의 고유ID"
    )

    dispersed: bool = Field(default=False, description="파티 해산 여부")
    members: list["KaraokeMembers"] = Relationship(back_populates="party", passive_deletes=True)


class KaraokeMembers(SQLModel, table=True):
    __tablename__ = "karaoke_member"

    party: KaraokePartis = Relationship(back_populates="members")
    party_id: int = Field(
        foreign_key="karaoke_party.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        primary_key=True,
        description="소속된 파티의 고유 ID",
    )

    user_id: int = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        primary_key=True,
        description="파티 멤버의 고유 ID",
    )

    pending: bool = Field(default=True, description="멤버 참여가 수락 대기중인지 여부")
