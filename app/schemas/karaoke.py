from datetime import datetime, date as dt_date
from enum import StrEnum
from sqlalchemy import Column, DateTime, func, String, Date
from sqlmodel import Field, Relationship, SQLModel

from .core import SchemaCore


class PeriodType(StrEnum):
    P1 = "1"
    P2 = "2"
    P3 = "3"
    P4 = "4"
    P5 = "5"
    P6 = "6"
    P7 = "7"
    LUNCH = "LUNCH"


class AuctionStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class KaraokeAuction(SQLModel, table=True):
    id: int | None = Field(None, primary_key=True, index=True)

    target_date: dt_date = Field(description="예약 대상 날짜", sa_column=Column(Date, nullable=False, index=True))
    period: PeriodType = Field(description="교시 (1~7, LUNCH)", sa_column=Column(String(10), nullable=False))

    start_time: datetime = Field(description="경매 시작 시간")
    end_time: datetime = Field(description="경매 종료 시간")

    min_bid: int = Field(default=0, description="최소 입찰가")

    status: AuctionStatus = Field(default=AuctionStatus.SCHEDULED, sa_column=Column(String(20), nullable=False))

    # 캐싱용으로 현재 최고 입찰 상태를 저장해두면 쿼리가 빠름
    current_highest_bid_id: int | None = Field(None, description="현재 최고 입찰 ID")
    current_highest_bid_amount: int = Field(default=0, description="현재 최고 입찰가")

    bids: list["KaraokeBid"] = Relationship(back_populates="auction", passive_deletes=True)


class KaraokeBidStatus(StrEnum):
    ACTIVE = "ACTIVE"
    OUTBID = "OUTBID"
    CANCELED = "CANCELED"


class KaraokeBid(SQLModel, table=True):
    id: int | None = Field(None, primary_key=True, index=True)

    auction: KaraokeAuction = Relationship(back_populates="bids")
    auction_id: int = Field(foreign_key="karaokeauction.id", nullable=False, index=True, ondelete="CASCADE")

    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)

    amount: int = Field(nullable=False, description="입찰 금액")

    status: KaraokeBidStatus = Field(default=KaraokeBidStatus.ACTIVE, sa_column=Column(String(20), nullable=False))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(SchemaCore.timezone),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
        ),
    )
