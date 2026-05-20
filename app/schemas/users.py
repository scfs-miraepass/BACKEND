from sqlmodel import Field, SQLModel, Relationship, delete
from sqlalchemy import event, Connection, insert
from typing import Optional, TYPE_CHECKING, List, Any
from enum import Enum
from typing import cast
from hangulpy import split_hangul_string, get_chosung_string
from pydantic import field_serializer

from app.core.loggers import service_logger
from .point import PointHistoryType

if TYPE_CHECKING:
    from .point import PointHistory


class UserType(str, Enum):
    student = "student"
    teacher = "teacher"
    service = "service"


class User(SQLModel):
    id: Optional[int] = Field(
        primary_key=True,
        default=None,
        description="고유 ID. 교사, 서비스의 경우 자동생성. 학생의 경우 학번 사용",
        index=True,
    )  # autoincrement

    type: UserType = Field(description="유저 종류 (학생, 교사, 서비스)")
    name: str = Field(description="이름")
    grade: Optional[int] = Field(description="학년")
    number: Optional[int] = Field(description="반")
    point: int = Field(0, description="보유 포인트")
    total_point: int = Field(0, description="누적 포인트")
    is_admin: bool = Field(False, description="관리자 여부")

    history_type: Optional[PointHistoryType] = Field(
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
            if value is not None and current_point is not None:
                if value > current_point:
                    diff = value - current_point
                    self.total_point = getattr(self, "total_point", 0) + diff
        super().__setattr__(name, value)


class Users(User, table=True):
    password: Optional[str] = Field(description="비밀번호")

    search: List["UserSearch"] = Relationship(back_populates="user", cascade_delete=True)
    history: List["PointHistory"] = Relationship(back_populates="user", cascade_delete=True)


class UserSearch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)  # autoincrement

    user: Users = Relationship(back_populates="search")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    value: str = Field(index=True)


def _generate_search_entries(target: Users) -> List[UserSearch]:
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

    service_logger.info(f"Generating search entries for new user: {target.name} (ID: {target.id})")
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

    service_logger.info(f"Updating search entries for user ID: {target.id} due to name change")
    connection.execute(delete(UserSearch).where(cast(Any, UserSearch.user_id == target.id)))
    if target.name:
        search_entries = _generate_search_entries(target)
        connection.execute(
            insert(UserSearch),
            [entry.model_dump() for entry in search_entries],
        )
