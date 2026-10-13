"""v1.13.0 #1 (Users default permission update)

Revision ID: da0b850e71f1
Revises: 1fb6fa59d8c8
Create Date: 2026-10-13 00:00:00.000000
"""

from collections.abc import Sequence
from enum import IntFlag, StrEnum
from logging import getLogger

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "da0b850e71f1"
down_revision: str | Sequence[str] | None = "1fb6fa59d8c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = getLogger("alembic.runtime.migration")


class UserPermission(IntFlag):
    NONE = 0

    SEARCH_USER = 2**17
    GRANT_POINT = 2**1 | SEARCH_USER
    CREATE_QUEST = 2**3
    VIEW_RANK = 2**6
    VIEW_POINT = 2**7
    VIEW_POINT_HISTORY = 2**8
    VIEW_USER_POINT = 2**11 | SEARCH_USER
    JOIN_QUEST = 2**12
    VIEW_POST = 2**14
    VIEW_STAMP = 2**15
    VIEW_QUEST = 2**16
    JOIN_KARAOKE = 2**18
    VIEW_KARAOKE = 2**20

    # v1.8.0 #4 에서 부여한 학생 기본 권한에, v1.11.0 에서 노래방 권한만 추가된 상태
    OLD_STUDENT_MIGRATED = (
        VIEW_RANK
        | VIEW_POINT
        | VIEW_POINT_HISTORY
        | JOIN_QUEST
        | VIEW_POST
        | VIEW_STAMP
        | VIEW_QUEST
        | VIEW_KARAOKE
        | JOIN_KARAOKE
    )
    # v1.11.0 이후 생성된 학생 계정의 기본 권한 (SEARCH_USER 포함)
    OLD_STUDENT = OLD_STUDENT_MIGRATED | SEARCH_USER
    OLD_TEACHER = (
        GRANT_POINT
        | CREATE_QUEST
        | VIEW_RANK
        | VIEW_POINT
        | VIEW_POINT_HISTORY
        | VIEW_USER_POINT
        | VIEW_POST
        | VIEW_STAMP
    )

    NEW_STUDENT = VIEW_RANK | VIEW_POINT | VIEW_POINT_HISTORY | VIEW_POST | VIEW_KARAOKE | JOIN_KARAOKE | SEARCH_USER
    NEW_TEACHER = (
        GRANT_POINT
        | VIEW_RANK
        | VIEW_POINT
        | VIEW_POINT_HISTORY
        | VIEW_USER_POINT
        | VIEW_POST
        | VIEW_STAMP
        | VIEW_KARAOKE
        | JOIN_KARAOKE
        | SEARCH_USER
    )


class UserType(StrEnum):
    student = "student"
    teacher = "teacher"
    service = "service"


# 유저 종류별 (기존 기본 권한 목록, 새 기본 권한)
# 기존 기본 권한과 정확히 일치하는 유저만 갱신하고, 개별로 권한이 수정된 유저는 건드리지 않는다.
# 서비스 계정은 기본 권한이 변경되지 않았으므로 대상에서 제외한다.
UPGRADE_MAP: dict[UserType, tuple[list[UserPermission], UserPermission]] = {
    UserType.student: (
        [UserPermission.OLD_STUDENT_MIGRATED, UserPermission.OLD_STUDENT],
        UserPermission.NEW_STUDENT,
    ),
    UserType.teacher: ([UserPermission.OLD_TEACHER], UserPermission.NEW_TEACHER),
}

# 업그레이드 이후에는 두 학생 기본 권한을 구분할 수 없으므로, 최신 기본 권한(OLD_STUDENT)으로 되돌린다.
DOWNGRADE_MAP: dict[UserType, tuple[list[UserPermission], UserPermission]] = {
    UserType.student: ([UserPermission.NEW_STUDENT], UserPermission.OLD_STUDENT),
    UserType.teacher: ([UserPermission.NEW_TEACHER], UserPermission.OLD_TEACHER),
}


def _migrate_permissions(mapping: dict[UserType, tuple[list[UserPermission], UserPermission]]) -> None:
    log.info("Proceeding with the Users default permission migration")
    conn = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("permissions", sa.Integer),
        sa.column("type", sa.String(length=20)),
    )

    for user_type, (before, after) in mapping.items():
        result = conn.execute(
            users.update()
            .where(
                users.c.type == user_type.value,
                users.c.permissions.in_([perm.value for perm in before]),
            )
            .values(permissions=after.value)
        )
        log.info(f"Users default permission migration - {user_type.value}: {result.rowcount} rows updated")

    log.info("Users default permission migration completed")


def upgrade() -> None:
    """Upgrade schema."""
    _migrate_permissions(UPGRADE_MAP)


def downgrade() -> None:
    """Downgrade schema."""
    _migrate_permissions(DOWNGRADE_MAP)
