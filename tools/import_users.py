import asyncio
import os
import sys
import pandas as pd
from sqlalchemy import select

# 프로젝트 루트 디렉토리를 sys.path에 추가하여 app 모듈을 임포트할 수 있도록 합니다.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import database_init, database_close, get_async_session
from app.schemas.users import Users, UserType


async def import_students(session):
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "student.xlsx")
    if not os.path.exists(file_path):
        print(f"학생 엑셀 파일을 찾을 수 없습니다: {file_path}")
        return

    print("학생 데이터 가져오는 중...")
    df = pd.read_excel(file_path)

    added_count = 0
    for index, row in df.iterrows():
        # 컬럼명이 한글 '학년', '반', '번호', '이름'으로 구성되어 있음
        grade = row.get("학년")
        number = row.get("반")
        student_no = row.get("번호")
        name = row.get("이름")

        if pd.isna(grade) or pd.isna(number) or pd.isna(student_no) or pd.isna(name):
            continue

        grade = int(grade)
        number = int(number)
        student_no = int(student_no)
        name = str(name).strip()

        # 학번 생성 (학년 + 반 두자리 + 번호 두자리) 예: 1학년 2반 3번 -> 1203
        student_id = int(f"{grade}{number}{student_no:02d}")

        # 이미 존재하는 학생인지 확인
        result = await session.execute(select(Users).where(Users.id == student_id))
        existing_user = result.scalars().first()

        if not existing_user:
            new_student = Users(id=student_id, type=UserType.student, name=name, grade=grade, number=number)
            session.add(new_student)
            added_count += 1

    await session.commit()
    print(f"학생 등록 완료! (새로 등록된 학생 수: {added_count}명)")


async def import_teachers(session):
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teacher.xlsx")
    if not os.path.exists(file_path):
        print(f"교사 엑셀 파일을 찾을 수 없습니다: {file_path}")
        return

    print("교사 데이터 가져오는 중...")
    df = pd.read_excel(file_path)

    # 교사 ID를 4000번대부터 시작
    current_teacher_id = 4000
    added_count = 0

    for index, row in df.iterrows():
        # 컬럼명이 한글 '이름'으로 구성되어 있음
        name = row.get("이름")

        if pd.isna(name):
            continue

        name = str(name).strip()

        # 이름으로 중복 확인
        result = await session.execute(select(Users).where(Users.name == name, Users.type == UserType.teacher))
        existing_user = result.scalars().first()

        if not existing_user:
            # 빈 ID 찾기 (4000번대)
            while True:
                id_check = await session.execute(select(Users).where(Users.id == current_teacher_id))
                if not id_check.scalars().first():
                    break
                current_teacher_id += 1

            new_teacher = Users(id=current_teacher_id, type=UserType.teacher, name=name)
            session.add(new_teacher)
            added_count += 1
            current_teacher_id += 1  # 다음 교사를 위해 ID 증가

    await session.commit()
    print(f"교사 등록 완료! (새로 등록된 교사 수: {added_count}명)")


async def main():
    # 데이터베이스 초기화
    print("데이터베이스 초기화")
    await database_init()
    _ = get_async_session()

    async for session in _:
        await import_students(session)
        await import_teachers(session)

    # 데이터베이스 연결 종료
    await database_close()


if __name__ == "__main__":
    asyncio.run(main())
