from enum import IntFlag, StrEnum
from typing import Any, cast

from hangulpy import get_chosung_string, split_hangul_string
from pydantic import GetJsonSchemaHandler, field_serializer
from pydantic_core import core_schema
from sqlalchemy import Connection, event, insert
from sqlmodel import Field, Integer, Relationship, SQLModel, delete

from app.core import LoggerCore

from .point import PointHistory, PointHistoryType
from .post import Posts
from .quest import QuestCompletion, Quests
from .stamp import Stamps


class UserType(StrEnum):
    student = "student"
    teacher = "teacher"
    service = "service"


class UserPermission(IntFlag):
    """
    유저 권한 IntFlag.
    작명시 `동사_목적`으로 작성하며, 대문자로만 작성한다.
    예) 포인트 관리 -> MANAGE_POINT
    """

    NONE = 0

    SEARCH_USER = 2**17
    """사용자를 검색할 수 있는 권한"""

    DEDUCT_POINT = 2**0 | SEARCH_USER
    """포인트를 차감할 수 있는 권한"""

    GRANT_POINT = 2**1 | SEARCH_USER
    """포인트를 지급할 수 있는 권한"""

    NO_LIMIT_POINT = 2**2
    """
    제한 없이 포인트를 지급할 수 있는 권한
    **해당 권한을 가진 사용자는 포인트 랭킹에 표기되지 않습니다**
    """

    CREATE_QUEST = 2**3
    """퀘스트 신청 권한"""

    MANAGE_QUEST = 2**4
    """
    퀘스트 관리 권한
    - 다른 유저의 퀘스트 삭제
    """

    GIVE_STAMP = 2**5 | SEARCH_USER
    """스탬프를 다른 유저에게 지급할 권한"""

    VIEW_RANK = 2**6
    """포인트 랭크를 확인 할 수 있는 권한"""

    VIEW_POINT = 2**7
    """보유중인 포인트를 확인 할 수 있는 권한"""

    VIEW_POINT_HISTORY = 2**8
    """자기 자신의 포인트 기록을 확인 할 수 있는 권한"""

    MANAGE_POST = 2**9
    """
    게시글 관리 권한
    - 다른 유저의 게시글 삭제
    """

    CREATE_POST = 2**10
    """게시글 생성 권한"""

    VIEW_USER_POINT = 2**11 | SEARCH_USER
    """다른 사용자의 보유중인 포인트를 확인 할 수 있는 권한"""

    JOIN_QUEST = 2**12
    """퀘스트에 참가해 수락하고 완료할 수 있는 권한"""

    MANAGE_USER = 2**13 | SEARCH_USER
    """
    유저 관리 권한
    - 유저 생성, 수정, 삭제
    - 일괄 포인트 지급
    - 유저 목록 조회
    """

    VIEW_POST = 2**14
    """게시글을 볼 수 있는 권한"""

    VIEW_STAMP = 2**15
    """스템프를 볼 수 있는 권한"""

    VIEW_QUEST = 2**16
    """퀘스트를 볼 수 있는 권한"""

    STUDENT = (
        VIEW_RANK
        | VIEW_POINT
        | VIEW_POINT_HISTORY
        | JOIN_QUEST
        | VIEW_POST
        | VIEW_STAMP
        | VIEW_QUEST
    )
    TEACHER = (
        GRANT_POINT
        | CREATE_QUEST
        | VIEW_RANK
        | VIEW_POINT
        | VIEW_POINT_HISTORY
        | VIEW_USER_POINT
        | VIEW_POST
        | VIEW_STAMP
    )
    ADMIN = MANAGE_USER | MANAGE_POST | MANAGE_QUEST | CREATE_POST

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema_: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        json_schema = handler(core_schema_)
        json_schema = handler.resolve_ref_schema(json_schema)

        if "enum" in json_schema:
            varnames = []
            for val in json_schema["enum"]:
                try:
                    member = cls(val)
                    if member.name:
                        varnames.append(member.name)
                    else:
                        varnames.append(f"FLAG_{val}")
                except ValueError:
                    varnames.append(f"FLAG_{val}")
            
            json_schema["x-enum-varnames"] = varnames
            json_schema["x-enumNames"] = varnames

        return json_schema


class User(SQLModel):
    id: int | None = Field(
        primary_key=True,
        default=None,
        description="고유 ID. 교사, 서비스의 경우 자동생성. 학생의 경우 학번 사용",
        index=True,
    )  # autoincrement

    type: UserType = Field(description="유저 종류 (학생, 교사, 서비스)", index=True)
    name: str = Field(description="이름")
    grade: int | None = Field(description="학년")
    number: int | None = Field(description="반")
    point: int = Field(0, description="보유 포인트")
    total_point: int = Field(0, description="누적 포인트")

    permissions: UserPermission = Field(
        UserPermission.NONE.value, description="관리자 여부", sa_type=Integer
    )

    history_type: PointHistoryType | None = Field(
        None, description="해당 유저가 포인트 지급/차감시 포인트 기록 타입"
    )

    @field_serializer("type")
    def serialize_type(self, type_value: Any, _info):
        if isinstance(type_value, UserType):
            return type_value.value
        return type_value

    @field_serializer("history_type")
    def serialize_history_type(self, type_value: Any, _info):
        if isinstance(type_value, PointHistoryType):
            return type_value.value
        return type_value

    def __setattr__(self, name, value):
        if name == "point":
            current_point = getattr(self, "point", 0)
            if (
                value is not None
                and current_point is not None
                and value > current_point
            ):
                diff = value - current_point
                self.total_point = getattr(self, "total_point", 0) + diff
        super().__setattr__(name, value)


class Users(User, table=True):
    password: str | None = Field(description="비밀번호")

    search: list[UserSearch] = Relationship(back_populates="user", passive_deletes=True)
    history: list[PointHistory] = Relationship(
        back_populates="user", passive_deletes=True
    )
    created_quest: list[Quests] = Relationship(
        back_populates="author", passive_deletes=True
    )
    completion_quest: list[QuestCompletion] = Relationship(
        back_populates="user", passive_deletes=True
    )
    stamps: list[Stamps] = Relationship(back_populates="user", passive_deletes=True)

    posts: list[Posts] = Relationship(back_populates="author")


class UserSearch(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)  # autoincrement

    user: Users = Relationship(back_populates="search")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    value: str = Field(index=True)


def _generate_search_entries(target: Users) -> list[UserSearch]:
    decomposed = "".join(split_hangul_string(target.name.replace(" ", "")))
    chosung = get_chosung_string(target.name)
    return [
        UserSearch(user_id=target.id, value=decomposed),
        UserSearch(user_id=target.id, value=chosung),
    ]


@event.listens_for(Users, "after_insert")
def user_search_insert(mapper, connection: Connection, target: Users):
    if not target.name or not target.id:
        return

    LoggerCore.service_quest.info(
        f"Generating search entries for new user: {target.name} (ID: {target.id})"
    )
    search_entries = _generate_search_entries(target)
    # 성능을 위해 대량 삽입을 사용하거나 세션에 추가
    connection.execute(
        insert(UserSearch),
        [entry.model_dump() for entry in search_entries],
    )


@event.listens_for(Users, "after_update")
def user_search_update(mapper, connection: Connection, target: Users):
    # 이름이 변경된 경우에만 실행하도록 검사
    state = getattr(target, "_sa_instance_state", None)
    if state:
        history = state.get_history("name", True)
        if not history.has_changes():
            return

    LoggerCore.service.info(
        f"Updating search entries for user ID: {target.id} due to name change"
    )
    connection.execute(
        delete(UserSearch).where(cast(Any, UserSearch.user_id == target.id))
    )
    if target.name:
        search_entries = _generate_search_entries(target)
        connection.execute(
            insert(UserSearch),
            [entry.model_dump() for entry in search_entries],
        )
