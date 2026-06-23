from datetime import datetime
from math import ceil
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlmodel import func, select, col

from app.core import LoginDep, ServiceClient
from app.core.error import ExpiredError, LimitExceeded
from app.schemas import Quests, UserPermission
from app.schemas.response import ErrorResponse, ResponseModel

router = APIRouter(prefix="/quest", tags=["quest"])
client = ServiceClient()
QUEST_MAX_POINT_LIMIT = 300


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
    response_model=ResponseModel[Quests],
    responses={
        201: {"description": "퀘스트 생성 성공"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
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
):
    user, _ = auth_data

    if not user.has_permission(UserPermission.CREATE_QUEST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if operation.reward > QUEST_MAX_POINT_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"The maximum point reward for a quest is {QUEST_MAX_POINT_LIMIT}.",
        )

    quest = await user.create_quest(
        title=operation.title,
        description=operation.description,
        reward=operation.reward,
        end_date=operation.end_date,
        max_repeat=operation.max_repeat,
    )

    return ResponseModel(success=True, data=quest)


@router.get(
    "",
    response_model=ResponseModel[List[Quests]],
    responses={
        200: {"description": "퀘스트 목록 조회 성공"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {"model": ErrorResponse, "description": "권한이 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="퀘스트 목록 조회",
    description="모든 퀘스트 목록을 조회합니다.",
)
async def list_quests(
    response: Response,
    auth_data: LoginDep,
    limit: int = 20,
    offset: int = 0,
):
    _user, _ = auth_data

    if not _user.has_permission(UserPermission.VIEW_QUEST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    count_cache_key = "quests_count"
    cached_count = await client.redis.get(count_cache_key)

    async with client.session as session:
        if cached_count is not None:
            count = int(cached_count)
        else:
            count_query = select(func.count()).select_from(Quests)
            count_result = await session.execute(count_query)
            count = count_result.scalar() or 0
            await client.redis.set(count_cache_key, count, ttl=60 * 5)

        quests_cache_key = f"quests:{limit}:{offset}"
        cached_quests = await client.redis.get(quests_cache_key)

        if cached_quests is not None:
            quests = [Quests(**item) for item in cached_quests]
            response.headers["X-CACHED"] = "true"
        else:
            response.headers["X-CACHED"] = "false"
            query = (
                select(Quests)
                .order_by(col(Quests.end_date))
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(query)
            quests = list(result.scalars().all())
            quests_data = [item.model_dump() for item in quests]
            await client.redis.set(quests_cache_key, quests_data, ttl=60 * 5)

    max_page = str(ceil(count / limit)) if limit > 0 else "1"
    response.headers["X-MAX-PAGE"] = max_page
    client.service_logger.info(f"Quest list fetched. count={count}, returned={len(quests)}, limit={limit}, offset={offset}")

    return ResponseModel(success=True, data=quests)


@router.get(
    "/{quest_id}",
    response_model=ResponseModel[Quests],
    responses={
        200: {"description": "퀘스트 조회 성공"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        404: {"model": ErrorResponse, "description": "퀘스트를 찾을 수 없음"},
        403: {"model": ErrorResponse, "description": "권한이 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="퀘스트 조회",
    description="퀘스트 상세 정보를 조회합니다.",
)
async def get_quest(quest_id: int, auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.VIEW_QUEST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    quest = await client.get_quest(quest_id, cache=True)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found."
        )

    return ResponseModel(success=True, data=quest)


@router.put(
    "/{quest_id}",
    response_model=ResponseModel[Quests],
    responses={
        200: {"description": "퀘스트 수정 성공"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        404: {"model": ErrorResponse, "description": "퀘스트를 찾을 수 없음"},
        429: {"model": ErrorResponse, "description": "퀘스트 보상 한도 초과"},
    },
    status_code=status.HTTP_200_OK,
    summary="퀘스트 수정",
    description="퀘스트 정보를 수정합니다. (생성한 교사 또는 관리자 전용)",
)
async def update_quest(quest_id: int, operation: QuestUpdate, auth_data: LoginDep):
    user, _ = auth_data
    quest = await client.get_quest(quest_id, cache=True)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found."
        )

    if quest.author_id != user.id and not user.has_permission(
        UserPermission.MANAGE_QUEST
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the quest creator can update this quest.",
        )

    if operation.reward is not None and operation.reward > QUEST_MAX_POINT_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"The maximum point reward for a quest is {QUEST_MAX_POINT_LIMIT}.",
        )

    await quest.edit(**operation.model_dump(mode="json"))
    return ResponseModel(success=True, data=quest)


@router.delete(
    "/{quest_id}",
    responses={
        204: {"description": "퀘스트 삭제 성공"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        404: {"model": ErrorResponse, "description": "퀘스트를 찾을 수 없음"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="퀘스트 삭제",
    description="퀘스트를 삭제합니다. (생성한 교사 또는 관리자 전용)",
)
async def delete_quest(quest_id: int, auth_data: LoginDep):
    user, _ = auth_data
    quest = await client.get_quest(quest_id, cache=True)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found."
        )

    if quest.author_id != user.id and not user.has_permission(
        UserPermission.MANAGE_QUEST
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the quest creator can delete this quest.",
        )

    await quest.delete()


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
async def complete_quest(quest_id: int, auth_data: LoginDep):
    user, _ = auth_data

    if user.has_permission(UserPermission.JOIN_QUEST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not have permission to participate in the quest",
        )

    quest = await client.get_quest(quest_id, cache=True)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found."
        )

    try:
        await quest.complete(user)
    except ExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Quest is expired."
        )
    except LimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="This quest can only be completed once.",
        )
    return ResponseModel(success=True, data=user.point)
