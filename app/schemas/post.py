from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel, Relationship, ForeignKey, Integer, JSON
from typing import Optional, Any
from pydantic import field_serializer

from .users import Users


class Post(SQLModel):
    id: Optional[int] = Field(
        primary_key=True,
        default=None,
        description="게시글 고유 ID",
        index=True,
    )  # autoincrement

    title: str = Field(..., description="게시글 제목")
    views: int = Field(default=0, description="게시글 조회수")

    # 시간 관련 데이터
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="게시글이 작성된 시간",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
        description="게시글이 수정된 마지막 시간",
    )

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: Any, _info):
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt


class Posts(Post, table=True):
    content: Optional["PostContent"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"uselist": False},
        passive_deletes=True,
    )

    author: "Users" = Relationship(back_populates="posts")
    author_id: int = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        index=True,
        description="게시글 작성자의 고유 ID",
    )


class PostContent(SQLModel, table=True):
    # 관계
    post: "Posts" = Relationship(back_populates="content")
    post_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
        ),
        description="연결된 게시글 고유 ID",
    )

    # JSON 내용
    data: dict = Field(
        ..., description="게시글의 내용 JSON 데이터", sa_column=Column(JSON)
    )
