from datetime import date, datetime
from enum import StrEnum
from sqlmodel import SQLModel, Field, Index, Column, String


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
