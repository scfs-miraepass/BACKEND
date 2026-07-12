# ruff: noqa: E402

import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

import asyncio
import json
import typer
from typing import Optional
from sqlalchemy import select, desc
from sqlmodel import col

from app.core import ServiceClient
from app.core.service import History
from app.core.config import settings
from app.schemas.users import Users, UserType
from app.schemas.point import PointHistory, PointHistoryType


# CLI를 실행할 때는 기본적으로 DB 쿼리 로그(echo)를 끕니다.
settings.debug = False

app = typer.Typer()
client = ServiceClient()


def get_visual_width(s: str) -> int:
    """Calculates the visual width of a string, accounting for wide characters like Hangul."""
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
    await client.initialize()
    try:
        await coroutine
    finally:
        await client.close()


async def clear_user_cache(user_id: int):
    """Clears the cache for a specific user."""
    await client.redis.delete(f"user:{user_id}")
    await client.redis.delete(f"point_history_count:{user_id}")
    await client.redis.delete_pattern(f"point_history:{user_id}:*")
    await client.redis.delete_pattern("search_users:*")
    print(f"Cache cleared for user ID: {user_id}")


@app.command()
def add_user(
    name: str = typer.Option(..., help="User's name"),
    user_type: UserType = typer.Option(..., help="User's type (student, teacher, or service)"),
    grade: Optional[int] = typer.Option(None, help="Grade (for students)"),
    number: Optional[int] = typer.Option(None, help="Class number (for students)"),
    student_no: Optional[int] = typer.Option(None, help="Student number (for students)"),
):
    """
    Add a new user.
    """

    async def _add_user():
        async with client.session as session:
            if user_type == UserType.student:
                if not all([grade, number, student_no]):
                    print("Error: For student, grade, number, and student_no are required.")
                    return

                user_id = int(f"{grade}{number}{student_no:02d}")
                existing_user = await session.get(Users, user_id)
                if existing_user:
                    print(f"Error: Student with ID {user_id} already exists.")
                    return

                new_user = Users(
                    id=user_id,
                    type=UserType.student,
                    name=name,
                    grade=grade,
                    number=number,
                )
                session.add(new_user)
                print(f"Student '{name}' with ID {user_id} added successfully.")

            elif user_type == UserType.teacher:
                # Find the next available ID for a teacher (starting from 4000)
                current_teacher_id = 4000
                while True:
                    id_check = await session.get(Users, current_teacher_id)
                    if not id_check:
                        break
                    current_teacher_id += 1

                new_user = Users(id=current_teacher_id, type=UserType.teacher, name=name)
                session.add(new_user)
                print(f"Teacher '{name}' with ID {current_teacher_id} added successfully.")

            elif user_type == UserType.service:
                # Find the next available ID for a service user (starting from 5000)
                current_service_id = 5000
                while True:
                    id_check = await session.get(Users, current_service_id)
                    if not id_check:
                        break
                    current_service_id += 1

                new_user = Users(id=current_service_id, type=UserType.service, name=name)
                session.add(new_user)
                print(f"Service user '{name}' with ID {current_service_id} added successfully.")

    asyncio.run(run_with_client(_add_user()))


@app.command()
def manage_point(
    user_id: int = typer.Option(..., help="User ID to manage points for"),
    amount: int = typer.Option(..., help="Amount of points to add (positive) or subtract (negative)"),
    reason: str = typer.Option(..., help="Reason for the point change"),
    history_type: PointHistoryType = typer.Option(PointHistoryType.etc, help="Type of point history"),
):
    """
    Manage a user's points.
    """

    async def _manage_point():
        async with client.session:
            user = await client.get_user(user_id, save_cache=False)
            if not user:
                print(f"Error: User with ID {user_id} not found.")
                return

            if amount >= 0:
                await user.point_grant(amount=amount, reason=reason, type=history_type)
            else:
                await user.point_deduct(amount=amount * -1, reason=reason, type=history_type)
        await client.redis.delete_pattern("search_users:*")
        print(f"Successfully changed points for user {user_id}. New balance: {user.point}")

    asyncio.run(run_with_client(_manage_point()))


@app.command()
def list_users(
    user_type: Optional[UserType] = typer.Option(None, help="Filter by user type (student, teacher, service)"),
    limit: int = typer.Option(50, help="Max number of users to return"),
):
    """
    List users in the system.
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
                print("No users found.")
                return

            print(f"{'ID':<10} | {'Type':<10} | {'Name':<15} | {'Point':<10} | {'Admin'}")
            print("-" * 65)
            for u in users:
                admin_str = "O" if u.is_admin else "X"

                # Manually pad the name to handle wide characters
                visual_name_width = get_visual_width(u.name)
                padding_needed = 15 - visual_name_width
                name_padding = " " * padding_needed if padding_needed > 0 else ""
                padded_name = u.name + name_padding

                print(f"{u.id:<10} | {u.type.value:<10} | {padded_name} | {u.point:<10} | {admin_str}")

    asyncio.run(run_with_client(_list_users()))


@app.command()
def user_info(user_id: int = typer.Option(..., help="User ID to lookup")):
    """
    Get detailed information about a specific user.
    """

    async def _user_info():
        async with client.session as session:
            user = await session.get(Users, user_id)
            if not user:
                print(f"User with ID {user_id} not found.")
                return

            print(f"--- User Info (ID: {user.id}) ---")
            print(f"Name: {user.name}")
            print(f"Type: {user.type.value}")
            if user.type == UserType.student:
                print(f"Grade/Class: {user.grade}학년 {user.number}반")
            print(f"Current Point: {user.point}")
            print(f"Total Point (Accumulated): {user.total_point}")
            print(f"Is Admin: {user.is_admin}")

    asyncio.run(run_with_client(_user_info()))


@app.command()
def delete_user(
    user_id: int = typer.Option(..., help="User ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without prompt"),
):
    """
    Delete a user from the system.
    """

    async def _delete_user():
        async with client.session as session:
            user = await session.get(Users, user_id)
            if not user:
                print(f"User with ID {user_id} not found.")
                return

            if not force:
                confirm = input(f"Are you sure you want to delete user '{user.name}' (ID: {user.id})? [y/N]: ")
                if confirm.lower() != "y":
                    print("Deletion cancelled.")
                    return

            await session.delete(user)
            await session.commit()  # Commit before clearing cache

            await clear_user_cache(user_id)
            print(f"User '{user.name}' (ID: {user.id}) has been successfully deleted.")

    asyncio.run(run_with_client(_delete_user()))


@app.command()
def reset_password(
    user_id: int = typer.Option(..., help="User ID to reset password for"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reset without prompt"),
):
    """
    Reset a user's password to None.
    """

    async def _reset_password():
        async with client.session as session:
            user = await session.get(Users, user_id)
            if not user:
                print(f"User with ID {user_id} not found.")
                return

            if not force:
                confirm = input(
                    f"Are you sure you want to reset the password for user '{user.name}' (ID: {user.id})? [y/N]: "
                )
                if confirm.lower() != "y":
                    print("Password reset cancelled.")
                    return

            user.password = None
            await session.commit()  # Commit before clearing cache

            await clear_user_cache(user_id)
            print(f"Password for user '{user.name}' (ID: {user.id}) has been reset to None.")

    asyncio.run(run_with_client(_reset_password()))


@app.command()
def point_history(
    user_id: Optional[int] = typer.Option(None, help="Filter history by user ID"),
    limit: int = typer.Option(20, help="Number of records to show"),
):
    """
    View point history log.
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
                print("No point history found.")
                return

            print(f"{'ID':<8} | {'User ID':<10} | {'Amount':<10} | {'Type':<10} | {'Reason':<20} | {'Date'}")
            print("-" * 90)
            for h in histories:
                h_type = h.type.value if h.type else "N/A"
                date_str = h.created_at.strftime("%Y-%m-%d %H:%M:%S") if h.created_at else "N/A"
                print(
                    f"{h.id:<8} | {h.user_id:<10} | {h.changed_amount:<10} | {h_type:<10} | {h.reason:<20} | {date_str}"
                )

    asyncio.run(run_with_client(_point_history()))


@app.command()
def delete_point_history(
    history_id: int = typer.Option(..., help="Point history ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without prompt"),
):
    """
    Delete a point history record and recalculate user points.
    """

    async def _delete_point_history():
        async with client.session as session:
            history_payload = await session.get(PointHistory, history_id)

            if not history_payload:
                print(f"Point history with ID {history_id} not found.")
                return

            history = History(payload=history_payload)

            if not force:
                confirm = input(
                    f"Are you sure you want to delete history ID {history.id} (User: {history.user_id}, Amount: {history.changed_amount})? This will affect user's points. [y/N]: "
                )
                if confirm.lower() != "y":
                    print("Deletion cancelled.")
                    return

            await history.delete()
            print(f"Point history ID {history_id} deleted. User {history.user_id}'s points have been recalculated.")

    asyncio.run(run_with_client(_delete_point_history()))


# --- Redis Commands ---


@app.command()
def redis_get(key: str = typer.Argument(..., help="Redis key to get")):
    """
    Get a value from Redis.
    """

    async def _redis_get():
        value = await client.redis.get(key)
        if value is not None:
            print(f"Key: {key}")
            print(f"Value: {json.dumps(value, indent=2, ensure_ascii=False)}")
        else:
            print(f"Key '{key}' not found or is None.")

    asyncio.run(run_with_client(_redis_get()))


@app.command()
def redis_delete(key: str = typer.Argument(..., help="Redis key to delete")):
    """
    Delete a key from Redis.
    """

    async def _redis_delete():
        await client.redis.delete(key)
        print(f"Key '{key}' deleted (or didn't exist).")

    asyncio.run(run_with_client(_redis_delete()))


@app.command()
def redis_delete_pattern(pattern: str = typer.Argument(..., help="Redis key pattern to delete (e.g., 'cache:*')")):
    """
    Delete keys matching a pattern from Redis.
    """

    async def _redis_delete_pattern():
        # RedisCore doesn't have a direct way to count deleted keys easily without changing it,
        # but it will log it. We just call it.
        await client.redis.delete_pattern(pattern)
        print(f"Pattern '{pattern}' deletion triggered. Check logs for details.")

    asyncio.run(run_with_client(_redis_delete_pattern()))


if __name__ == "__main__":
    app()
