from sqlmodel import Field, SQLModel
from typing import Optional
from enum import Enum


class UserType(str, Enum):
    student = "student"
    teacher = "teacher"
    service = "service"


class User(SQLModel):
    id: Optional[int] = Field(
        primary_key=True,
        default=None,
        description="고유 ID. 교사, 서비스의 경우 자동생성. 학생의 경우 학번 사용",
    )  # autoincrement

    type: UserType = Field(description="유저 종류 (학생, 교사, 서비스)")
    name: str = Field(description="이름")
    grade: Optional[int] = Field(description="학년")
    number: Optional[int] = Field(description="반")
    point: int = Field(0, description="보유 포인트")


class Users(User, table=True):
    password: Optional[str] = Field(description="비밀번호")
