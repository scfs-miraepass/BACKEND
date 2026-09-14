"""
개발/테스트를 위한 테스트 유저를 생성하는 스크립트입니다.
실제 유저를 추가하는 방식(cli.py의 add_user, admin.py의 create_user)과 동일하게
학생은 학년/반/번호로 학번을 계산하고, 교사/서비스는 빈 ID를 찾아 순차 할당합니다.

사용법:
    python tools/create_test_users.py
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

from app.core.config import settings

settings.debug = False

from app.core import ServiceClient
from app.schemas.users import UserPermission, Users, UserType

client = ServiceClient()

# 생성할 테스트 유저 목록
TEST_STUDENTS = [
    {"name": "테스트학생1", "grade": 1, "number": 1, "student_no": 1},
    {"name": "테스트학생2", "grade": 1, "number": 1, "student_no": 2},
    {"name": "테스트학생3", "grade": 1, "number": 1, "student_no": 3},
    {"name": "테스트학생4", "grade": 1, "number": 1, "student_no": 4},
    {"name": "테스트학생5", "grade": 1, "number": 1, "student_no": 5},
]
TEST_TEACHERS = ["교사"]
TEST_SERVICES = ["테스트서비스"]


async def create_students(session):
    for spec in TEST_STUDENTS:
        user_id = int(f"{spec['grade']}{spec['number']}{spec['student_no']:02d}")

        existing_user = await session.get(Users, user_id)
        if existing_user:
            client.logs.service.info(f"ID {user_id}인 학생이 이미 존재하여 건너뜁니다.")
            continue

        new_user = Users(
            id=user_id,
            type=UserType.student,
            name=spec["name"],
            grade=spec["grade"],
            number=spec["number"],
            permissions=UserPermission.STUDENT.value,
        )
        session.add(new_user)
        client.logs.service.info(f"ID {user_id}의 학생 '{spec['name']}'을(를) 추가했습니다.")


async def create_teachers(session):
    current_teacher_id = 4000
    for name in TEST_TEACHERS:
        while True:
            id_check = await session.get(Users, current_teacher_id)
            if not id_check:
                break
            current_teacher_id += 1

        new_user = Users(
            id=current_teacher_id,
            type=UserType.teacher,
            name=name,
            permissions=UserPermission.TEACHER.value,
        )
        session.add(new_user)
        client.logs.service.info(f"ID {current_teacher_id}의 교사 '{name}'을(를) 추가했습니다.")
        current_teacher_id += 1


async def create_services(session):
    current_service_id = 5000
    for name in TEST_SERVICES:
        while True:
            id_check = await session.get(Users, current_service_id)
            if not id_check:
                break
            current_service_id += 1

        new_user = Users(id=current_service_id, type=UserType.service, name=name)
        session.add(new_user)
        client.logs.service.info(f"ID {current_service_id}의 서비스 계정 '{name}'을(를) 추가했습니다.")
        current_service_id += 1


async def main():
    await client.initialize()

    try:
        async with client.session as session:
            await create_students(session)
            await create_teachers(session)
            await create_services(session)
            await session.commit()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
