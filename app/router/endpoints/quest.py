from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlmodel import func, select
from sqlalchemy.orm import joinedload

from app.core import LoginDep, SessionDep
from app.core.loggers import service_logger
from app.core.redis import redis
from app.schemas import (
    PointHistory,
    Quest,
    QuestCompletion,
    Users,
    UserType,
    PointHistoryType,
)
from app.schemas.response import ErrorResponse, ResponseModel

router = APIRouter(prefix="/quest", tags=["quest"])
QUEST_MAX_POINT_LIMIT = 300
QUEST_ID_BACKFILLED = False


def serialize_quest(quest: Quest) -> dict[str, Any]:
    return {
        "id": quest.id,
        "title": quest.title,
        "description": quest.description,
        "reward": quest.reward,
        "end_date": quest.end_date,
        "max_repeat": 1,
        "created_at": quest.created_at,
        "author_id": quest.author_id,
    }


async def backfill_missing_quest_ids(session: SessionDep) -> None:
    global QUEST_ID_BACKFILLED

    if QUEST_ID_BACKFILLED:
        return

    missing_result = await session.execute(select(Quest).where(Quest.id.is_(None)).order_by(Quest.created_at))
    missing_quests = [item for item in missing_result.scalars().all() if item is not None]

    if not missing_quests:
        QUEST_ID_BACKFILLED = True
        return

    max_id_result = await session.execute(select(func.max(Quest.id)))
    next_id = (max_id_result.scalar() or 0) + 1

    for quest in missing_quests:
        quest.id = next_id
        next_id += 1

    await session.commit()
    QUEST_ID_BACKFILLED = True


class QuestOperation(BaseModel):
    title: str = Field(..., description="퀘스트 제목")
    description: str = Field(..., description="퀘스트 내용")
    reward: int = Field(..., gt=0, description="퀘스트 보상(포인트)")
    end_date: datetime = Field(..., description="퀘스트 종료 날짜")
    max_repeat: int = Field(1, ge=1, description="퀘스트 반복 가능 횟수")


class QuestUpdate(BaseModel):
    title: Optional[str] = Field(None, description="퀘스트 제목")
    description: Optional[str] = Field(None, description="퀘스트 내용")
    reward: Optional[int] = Field(None, gt=0, description="퀘스트 보상(포인트)")
    end_date: Optional[datetime] = Field(None, description="퀘스트 종료 날짜")
    max_repeat: Optional[int] = Field(None, ge=1, description="퀘스트 반복 가능 횟수")


@router.post(
    "/create",
    response_model=ResponseModel[Quest],
    responses={
        201: {"description": "퀘스트 생성 성공"},
        401: {"model": ErrorResponse, "description": "세션이 만료되었거나 유효하지 않음"},
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        429: {"model": ErrorResponse, "description": "퀘스트 보상 한도 초과"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="퀘스트 생성",
    description="퀘스트를 생성합니다. (교사 또는 관리자 전용)",
)
async def create_quest(
    operation: QuestOperation,
    auth_data: LoginDep,
    session: SessionDep,
):
    user, _ = auth_data

    if user.type != UserType.teacher and not user.is_admin:
        service_logger.warning(
            f"Unauthorized quest creation attempt. UserID: {user.id}, Role: {user.type}, Admin: {user.is_admin}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Only teachers or administrators can create quests.",
        )

    if not user.is_admin and operation.reward > QUEST_MAX_POINT_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"The maximum point reward for a quest is {QUEST_MAX_POINT_LIMIT}.",
        )

    next_quest_id = await session.scalar(select(func.coalesce(func.max(Quest.id), 0))) or 0
    quest = Quest(
        id=next_quest_id + 1,
        title=operation.title,
        description=operation.description,
        reward=operation.reward,
        end_date=operation.end_date,
        max_repeat=1,
        author_id=user.id,
    )

    session.add(quest)
    await session.flush()
    await session.commit()

    await redis.delete("quests_count")
    await redis.delete_pattern("quests:*")

    return ResponseModel(success=True, data=serialize_quest(quest))


@router.get(
    "",
    response_model=ResponseModel[List[Quest]],
    responses={
        200: {"description": "퀘스트 목록 조회 성공"},
        401: {"model": ErrorResponse, "description": "세션이 만료되었거나 유효하지 않음"},
    },
    status_code=status.HTTP_200_OK,
    summary="퀘스트 목록 조회",
    description="모든 퀘스트 목록을 조회합니다.",
)
async def list_quests(
    response: Response,
    session: SessionDep,
    auth_data: LoginDep,
    limit: int = 20,
    offset: int = 0,
):
    _user, _ = auth_data
    await backfill_missing_quest_ids(session)

    count_query = select(func.count()).select_from(Quest)
    count_result = await session.execute(count_query)
    count = count_result.scalar() or 0

    response.headers["X-CACHED"] = "false"
    query = select(Quest).order_by(Quest.end_date).limit(limit).offset(offset)
    result = await session.execute(query)
    quests = [item for item in result.scalars().all() if item is not None]

    max_page = str(ceil(count / limit)) if limit > 0 else "1"
    response.headers["X-MAX-PAGE"] = max_page
    service_logger.info(f"Quest list fetched. count={count}, returned={len(quests)}, limit={limit}, offset={offset}")

    return ResponseModel(success=True, data=[serialize_quest(item) for item in quests])


@router.get(
    "/{quest_id}",
    response_model=ResponseModel[Quest],
    responses={
        200: {"description": "퀘스트 조회 성공"},
        401: {"model": ErrorResponse, "description": "세션이 만료되었거나 유효하지 않음"},
        404: {"model": ErrorResponse, "description": "퀘스트를 찾을 수 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="퀘스트 조회",
    description="퀘스트 상세 정보를 조회합니다.",
)
async def get_quest(quest_id: int, response: Response, session: SessionDep, auth_data: LoginDep):
    _user, _ = auth_data

    response.headers["X-CACHED"] = "false"
    quest = await session.get(Quest, quest_id)
    if not quest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.")

    return ResponseModel(success=True, data=serialize_quest(quest))


@router.put(
    "/{quest_id}",
    response_model=ResponseModel[Quest],
    responses={
        200: {"description": "퀘스트 수정 성공"},
        401: {"model": ErrorResponse, "description": "세션이 만료되었거나 유효하지 않음"},
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        404: {"model": ErrorResponse, "description": "퀘스트를 찾을 수 없음"},
        429: {"model": ErrorResponse, "description": "퀘스트 보상 한도 초과"},
    },
    status_code=status.HTTP_200_OK,
    summary="퀘스트 수정",
    description="퀘스트 정보를 수정합니다. (생성한 교사 또는 관리자 전용)",
)
async def update_quest(
    quest_id: int,
    operation: QuestUpdate,
    auth_data: LoginDep,
    session: SessionDep,
):
    user, _ = auth_data
    quest = await session.get(Quest, quest_id)

    if not quest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.")

    if user.type != UserType.teacher and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if not user.is_admin and quest.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the quest creator can update this quest."
        )

    if operation.reward is not None and not user.is_admin and operation.reward > QUEST_MAX_POINT_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"The maximum point reward for a quest is {QUEST_MAX_POINT_LIMIT}.",
        )

    update_data = operation.model_dump(exclude_unset=True)
    update_data.pop("max_repeat", None)
    for key, value in update_data.items():
        setattr(quest, key, value)

    quest.max_repeat = 1

    session.add(quest)
    await session.commit()

    await redis.delete(f"quest:{quest_id}")
    await redis.delete("quests_count")
    await redis.delete_pattern("quests:*")

    return ResponseModel(success=True, data=serialize_quest(quest))


@router.delete(
    "/{quest_id}",
    responses={
        204: {"description": "퀘스트 삭제 성공"},
        401: {"model": ErrorResponse, "description": "세션이 만료되었거나 유효하지 않음"},
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        404: {"model": ErrorResponse, "description": "퀘스트를 찾을 수 없음"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="퀘스트 삭제",
    description="퀘스트를 삭제합니다. (생성한 교사 또는 관리자 전용)",
)
async def delete_quest(quest_id: int, auth_data: LoginDep, session: SessionDep):
    user, _ = auth_data
    quest = await session.get(Quest, quest_id)

    if not quest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.")

    if user.type != UserType.teacher and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if not user.is_admin and quest.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the quest creator can delete this quest."
        )

    await session.delete(quest)
    await session.commit()

    await redis.delete(f"quest:{quest_id}")
    await redis.delete("quests_count")
    await redis.delete_pattern("quests:*")


@router.post(
    "/{quest_id}/complete",
    response_model=ResponseModel[int],
    responses={
        200: {"description": "퀘스트 완료 처리 성공"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        404: {"model": ErrorResponse, "description": "퀘스트를 찾을 수 없음"},
        400: {"model": ErrorResponse, "description": "퀘스트 완료 불가"},
        429: {"model": ErrorResponse, "description": "퀘스트 반복 한도 초과"},
    },
    status_code=status.HTTP_200_OK,
    summary="퀘스트 완료",
    description="학생이 퀘스트를 완료합니다. 완료 시 보상이 지급됩니다.",
)
async def complete_quest(quest_id: int, auth_data: LoginDep, session: SessionDep):
    user, _ = auth_data

    if user.type != UserType.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can complete quests.",
        )

    query = select(Quest).where(Quest.id == quest_id).options(joinedload(Quest.author))
    result = await session.execute(query)
    quest: Quest | None = result.scalar_one_or_none()
    if not quest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.")

    now = datetime.now(timezone.utc)
    if quest.end_date < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quest is expired.")

    count_query = (
        select(func.count())
        .select_from(QuestCompletion)
        .where(
            QuestCompletion.quest_id == quest_id,
            QuestCompletion.user_id == user.id,
        )
    )
    result = await session.execute(count_query)
    completed_count = result.scalar_one()

    if completed_count >= 1:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="This quest can only be completed once.",
        )

    result = await session.execute(select(Users).where(Users.id == user.id).with_for_update())
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    student.point += quest.reward
    session.add(
        PointHistory(
            user_id=student.id,
            changed_amount=quest.reward,
            reason="퀘스트 완료 보상",
            memo=f"{quest.author.name} 선생님의 '{quest.title}' 퀘스트 완료 보상",
            type=PointHistoryType.quest,
        )
    )
    session.add(QuestCompletion(quest_id=quest_id, user_id=student.id))

    await session.commit()
    await session.refresh(student)

    await redis.delete(f"user:{student.id}")
    await redis.delete(f"point_history_count:{student.id}")
    await redis.delete_pattern(f"point_history:{student.id}:*")
    await redis.delete_pattern("ranking:student:*")

    return ResponseModel(success=True, data=student.point)
