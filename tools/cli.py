import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

import asyncio
import json
from typing import Optional

import typer
from sqlalchemy import desc, select
from sqlmodel import col

from app.core import ServiceClient
from app.core.config import settings
from app.core.service import History
from app.schemas.point import PointHistory, PointHistoryType
from app.schemas.users import Users, UserType

# CLI를 실행할 때는 기본적으로 DB 쿼리 로그(echo)를 끕니다.
settings.debug = False

app = typer.Typer()
client = ServiceClient()


def get_visual_width(s: str) -> int:
    """문자열의 시각적 너비를 계산합니다. 한글과 같은 넓은 문자를 고려합니다."""
    width = 0
    for char in s:
        # East Asian characters (Hangul, CJK, etc.) are typically 2 cells wide
        if (
            "\uac00" <= char <= "\ud7a3"
            or "\u4e00" <= char <= "\u9fff"
            or "\u3040" <= char <= "\u309f"
            or "\u30a0" <= char <= "\u30ff"
            or "\uff00" <= char <= "\uffef"
        ):
            width += 2
        else:
            width += 1
    return width


async def run_with_client(coroutine):
    """서비스 클라이언트를 초기화하고 코루틴을 실행합니다."""
    await client.initialize()
    try:
        await coroutine
    finally:
        await client.close()


async def clear_user_cache(user_id: int):
    """특정 사용자의 캐시를 지웁니다."""
    await client.redis.delete(f"user:{user_id}")
    await client.redis.delete(f"point_history_count:{user_id}")
    await client.redis.delete_pattern(f"point_history:{user_id}:*")
    await client.redis.delete_pattern("search_users:*")
    print(f"사용자 ID {user_id}의 캐시가 삭제되었습니다.")


@app.command()
def add_user(
    name: str = typer.Option(..., help="사용자 이름"),
    user_type: UserType = typer.Option(
        ..., help="사용자 유형 (student, teacher, or service)"
    ),
    grade: Optional[int] = typer.Option(None, help="학년 (학생용)"),
    number: Optional[int] = typer.Option(None, help="반 (학생용)"),
    student_no: Optional[int] = typer.Option(None, help="학번 (학생용)"),
):
    """
    새로운 사용자를 추가합니다.
    """

    async def _add_user():
        async with client.session as session:
            if user_type == UserType.student:
                if not all([grade, number, student_no]):
                    print("오류: 학생 유형은 학년, 반, 번호가 모두 필요합니다.")
                    return

                user_id = int(f"{grade}{number}{student_no:02d}")
                existing_user = await session.get(Users, user_id)
                if existing_user:
                    print(f"오류: ID가 {user_id}인 학생이 이미 존재합니다.")
                    return

                new_user = Users(
                    id=user_id,
                    type=UserType.student,
                    name=name,
                    grade=grade,
                    number=number,
                )
                session.add(new_user)
                print(f"ID {user_id}의 학생 '{name}'이(가) 성공적으로 추가되었습니다.")

            elif user_type == UserType.teacher:
                # Find the next available ID for a teacher (starting from 4000)
                current_teacher_id = 4000
                while True:
                    id_check = await session.get(Users, current_teacher_id)
                    if not id_check:
                        break
                    current_teacher_id += 1

                new_user = Users(
                    id=current_teacher_id, type=UserType.teacher, name=name
                )
                session.add(new_user)
                print(
                    f"ID {current_teacher_id}의 교사 '{name}'이(가) 성공적으로 추가되었습니다."
                )

            elif user_type == UserType.service:
                # Find the next available ID for a service user (starting from 5000)
                current_service_id = 5000
                while True:
                    id_check = await session.get(Users, current_service_id)
                    if not id_check:
                        break
                    current_service_id += 1

                new_user = Users(
                    id=current_service_id, type=UserType.service, name=name
                )
                session.add(new_user)
                print(
                    f"ID {current_service_id}의 서비스 사용자 '{name}'이(가) 성공적으로 추가되었습니다."
                )

    asyncio.run(run_with_client(_add_user()))


@app.command()
def manage_point(
    user_id: int = typer.Option(..., help="포인트를 관리할 사용자 ID"),
    amount: int = typer.Option(..., help="추가(양수) 또는 차감(음수)할 포인트 양"),
    reason: str = typer.Option(..., help="포인트 변경 사유"),
    history_type: PointHistoryType = typer.Option(
        PointHistoryType.etc, help="포인트 내역 유형"
    ),
):
    """
    사용자의 포인트를 관리합니다.
    """

    async def _manage_point():
        async with client.session:
            user = await client.get_user(user_id, save_cache=False)
            if not user:
                print(f"오류: ID가 {user_id}인 사용자를 찾을 수 없습니다.")
                return

            if amount >= 0:
                await user.point_grant(amount=amount, reason=reason, type=history_type)
            else:
                await user.point_deduct(
                    amount=amount * -1, reason=reason, type=history_type
                )
        await client.redis.delete_pattern("search_users:*")
        print(
            f"사용자 {user_id}의 포인트를 성공적으로 변경했습니다. 현재 포인트: {user.point}"
        )

    asyncio.run(run_with_client(_manage_point()))


@app.command()
def list_users(
    user_type: Optional[UserType] = typer.Option(
        None, help="사용자 유형(student, teacher, service)으로 필터링"
    ),
    limit: int = typer.Option(50, help="반환할 최대 사용자 수"),
):
    """
    시스템의 사용자 목록을 보여줍니다.
    """

    async def _list_users():
        async with client.session as session:
            query = select(Users)
            if user_type:
                query = query.where(col(Users.type) == user_type)
            query = query.limit(limit)

            result = await session.execute(query)
            users = result.scalars().all()

            if not users:
                print("사용자를 찾을 수 없습니다.")
                return

            print(
                f"{'ID':<10} | {'유형':<10} | {'이름':<15} | {'포인트':<10} | {'관리자'}"
            )
            print("-" * 65)
            for u in users:
                admin_str = "O" if u.is_admin else "X"

                # Manually pad the name to handle wide characters
                visual_name_width = get_visual_width(u.name)
                padding_needed = 15 - visual_name_width
                name_padding = " " * padding_needed if padding_needed > 0 else ""
                padded_name = u.name + name_padding

                print(
                    f"{u.id:<10} | {u.type.value:<10} | {padded_name} | {u.point:<10} | {admin_str}"
                )

    asyncio.run(run_with_client(_list_users()))


@app.command()
def user_info(user_id: int = typer.Option(..., help="조회할 사용자 ID")):
    """
    특정 사용자의 상세 정보를 가져옵니다.
    """

    async def _user_info():
        async with client.session as session:
            user = await session.get(Users, user_id)
            if not user:
                print(f"ID가 {user_id}인 사용자를 찾을 수 없습니다.")
                return

            print(f"--- 사용자 정보 (ID: {user.id}) ---")
            print(f"이름: {user.name}")
            print(f"유형: {user.type.value}")
            if user.type == UserType.student:
                print(f"학년/반: {user.grade}학년 {user.number}반")
            print(f"현재 포인트: {user.point}")
            print(f"총 포인트 (누적): {user.total_point}")
            print(f"관리자 여부: {user.is_admin}")

    asyncio.run(run_with_client(_user_info()))


@app.command()
def delete_user(
    user_id: int = typer.Option(..., help="삭제할 사용자 ID"),
    force: bool = typer.Option(
        False, "--force", "-f", help="확인 프롬프트 없이 강제 삭제"
    ),
):
    """
    시스템에서 사용자를 삭제합니다.
    """

    async def _delete_user():
        async with client.session as session:
            user = await session.get(Users, user_id)
            if not user:
                print(f"ID가 {user_id}인 사용자를 찾을 수 없습니다.")
                return

            if not force:
                confirm = input(
                    f"정말로 '{user.name}' 사용자(ID: {user.id})를 삭제하시겠습니까? [y/N]: "
                )
                if confirm.lower() != "y":
                    print("삭제가 취소되었습니다.")
                    return

            await session.delete(user)
            await session.commit()  # Commit before clearing cache

            await clear_user_cache(user_id)
            print(f"'{user.name}' 사용자(ID: {user.id})가 성공적으로 삭제되었습니다.")

    asyncio.run(run_with_client(_delete_user()))


@app.command()
def reset_password(
    user_id: int = typer.Option(..., help="비밀번호를 초기화할 사용자 ID"),
    force: bool = typer.Option(
        False, "--force", "-f", help="확인 프롬프트 없이 강제 초기화"
    ),
):
    """
    사용자의 비밀번호를 None으로 초기화합니다.
    """

    async def _reset_password():
        async with client.session as session:
            user = await session.get(Users, user_id)
            if not user:
                print(f"ID가 {user_id}인 사용자를 찾을 수 없습니다.")
                return

            if not force:
                confirm = input(
                    f"정말로 '{user.name}' 사용자(ID: {user.id})의 비밀번호를 초기화하시겠습니까? [y/N]: "
                )
                if confirm.lower() != "y":
                    print("비밀번호 초기화가 취소되었습니다.")
                    return

            user.password = None
            await session.commit()  # Commit before clearing cache

            await clear_user_cache(user_id)
            print(
                f"'{user.name}' 사용자(ID: {user.id})의 비밀번호가 None으로 초기화되었습니다."
            )

    asyncio.run(run_with_client(_reset_password()))


@app.command()
def point_history(
    user_id: Optional[int] = typer.Option(None, help="사용자 ID로 내역 필터링"),
    limit: int = typer.Option(20, help="표시할 레코드 수"),
):
    """
    포인트 변경 내역을 봅니다.
    """

    async def _point_history():
        async with client.session as session:
            query = select(PointHistory).order_by(desc(col(PointHistory.created_at)))
            if user_id:
                query = query.where(col(PointHistory.user_id) == user_id)
            query = query.limit(limit)

            result = await session.execute(query)
            histories = result.scalars().all()

            if not histories:
                print("포인트 내역을 찾을 수 없습니다.")
                return

            print(
                f"{'ID':<8} | {'사용자 ID':<10} | {'변동량':<10} | {'유형':<10} | {'사유':<20} | {'날짜'}"
            )
            print("-" * 90)
            for h in histories:
                h_type = h.type.value if h.type else "N/A"
                date_str = (
                    h.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if h.created_at
                    else "N/A"
                )
                print(
                    f"{h.id:<8} | {h.user_id:<10} | {h.changed_amount:<10} | {h_type:<10} | {h.reason:<20} | {date_str}"
                )

    asyncio.run(run_with_client(_point_history()))


@app.command()
def delete_point_history(
    history_id: int = typer.Option(..., help="삭제할 포인트 내역 ID"),
    force: bool = typer.Option(
        False, "--force", "-f", help="확인 프롬프트 없이 강제 삭제"
    ),
):
    """
    포인트 내역을 삭제하고 사용자의 포인트를 재계산합니다.
    """

    async def _delete_point_history():
        async with client.session as session:
            history_payload = await session.get(PointHistory, history_id)

            if not history_payload:
                print(f"ID가 {history_id}인 포인트 내역을 찾을 수 없습니다.")
                return

            history = History(payload=history_payload)

            if not force:
                confirm = input(
                    f"정말로 내역 ID {history.id}(사용자: {history.user_id}, 변동량: {history.changed_amount})을(를) 삭제하시겠습니까? 이 작업은 사용자 포인트에 영향을 줍니다. [y/N]: "
                )
                if confirm.lower() != "y":
                    print("삭제가 취소되었습니다.")
                    return

            await history.delete()
            print(
                f"포인트 내역 ID {history_id}이(가) 삭제되었습니다. 사용자 {history.user_id}의 포인트가 재계산되었습니다."
            )

    asyncio.run(run_with_client(_delete_point_history()))


# --- Redis Commands ---


@app.command()
def redis_get(key: str = typer.Argument(..., help="가져올 Redis 키")):
    """
    Redis에서 값을 가져옵니다.
    """

    async def _redis_get():
        value = await client.redis.get(key)
        if value is not None:
            print(f"키: {key}")
            print(f"값: {json.dumps(value, indent=2, ensure_ascii=False)}")
        else:
            print(f"키 '{key}'를 찾을 수 없거나 값이 없습니다.")

    asyncio.run(run_with_client(_redis_get()))


@app.command()
def redis_delete(key: str = typer.Argument(..., help="삭제할 Redis 키")):
    """
    Redis에서 키를 삭제합니다.
    """

    async def _redis_delete():
        await client.redis.delete(key)
        print(f"키 '{key}'가 삭제되었거나 존재하지 않았습니다.")

    asyncio.run(run_with_client(_redis_delete()))


@app.command()
def redis_delete_pattern(
    pattern: str = typer.Argument(..., help="삭제할 Redis 키 패턴 (예: 'cache:*')"),
):
    """
    Redis에서 패턴과 일치하는 키를 삭제합니다.
    """

    async def _redis_delete_pattern():
        # RedisCore doesn't have a direct way to count deleted keys easily without changing it,
        # but it will log it. We just call it.
        await client.redis.delete_pattern(pattern)
        print(
            f"패턴 '{pattern}' 삭제가 시작되었습니다. 자세한 내용은 로그를 확인하세요."
        )

    asyncio.run(run_with_client(_redis_delete_pattern()))


if __name__ == "__main__":
    app()
