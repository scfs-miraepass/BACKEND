from fastapi import APIRouter, HTTPException, status, Query, Response
from sqlmodel import select, func, update, col
from typing import List, Optional
from pydantic import BaseModel, Field
from math import ceil

from app.core import LoginDep, ServiceClient
from app.schemas import (
    User,
    Users,
    UserType,
    PointHistory,
    PointHistoryType,
    UserPermission,
)
from app.schemas.response import ErrorResponse, ResponseModel


class AdminPointRequest(BaseModel):
    user_ids: Optional[List[int]] = Field(
        None,
        description="포인트를 지급/차감할 학생 ID 목록. 전체 학생 대상일 경우 생략하거나 null/빈 리스트 전달",
    )
    amount: int = Field(..., description="변동될 포인트 (양수는 지급, 음수는 차감)")
    reason: str = Field(..., description="포인트 변동 사유")
    is_all_students: bool = Field(
        False, description="전체 학생 대상 여부. true일 경우 user_ids는 무시됩니다."
    )


router = APIRouter(prefix="/admin", tags=["admin"])
client = ServiceClient()


@router.get(
    "/student",
    response_model=ResponseModel[List[User]],
    responses={
        200: {"description": "정상적으로 처리 됨"},
        403: {
            "model": ErrorResponse,
            "description": "권한 거부",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="학생 목록",
    description="전체 학생 목록을 조회합니다.",
)
async def get_students(
    response: Response,
    auth_data: LoginDep,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(
        20, ge=1, le=100, description="페이지 당 유저 데이터 갯수 (최대 100)"
    ),
):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        count_query = (
            select(func.count())
            .select_from(Users)
            .where(Users.type == UserType.student)
        )
        total_count = (await session.execute(count_query)).scalar_one()
        max_page = ceil(total_count / size) if total_count > 0 else 1
        response.headers["X-MAX-PAGE"] = str(max_page)
        offset = (page - 1) * size
        query = (
            select(Users)
            .where(Users.type == UserType.student)
            .offset(offset)
            .limit(size)
        )

        result = await session.execute(query)
        users = result.scalars().all()

    return ResponseModel[List[User]](success=True, data=users)


@router.post(
    "/point",
    responses={
        204: {"description": "정상 처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한 거부",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="포인트 일괄 처리",
    description="일괄적으로 포인트를 지급하거나 차감합니다.",
)
async def update_students_point(request: AdminPointRequest, auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # 전체 학생 대상인지 여부에 따라 타겟 쿼리 설정
    async with client.session as session:
        if request.is_all_students:
            target_query = select(Users).where(Users.type == UserType.student)
        else:
            if not request.user_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="user_ids must be provided when not targeting all students.",
                )
            target_query = select(Users).where(col(Users.id).in_(request.user_ids))

        result = await session.execute(target_query)
        target_users = result.scalars().all()

        if not target_users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No target students found.",
            )

        target_ids = [user.id for user in target_users]
        update_stmt = (
            update(Users)
            .where(col(Users.id).in_(target_ids))
            .values(point=Users.point + request.amount)
        )
        await session.execute(update_stmt)

        history_entries = [
            PointHistory(
                user_id=uid,
                changed_amount=request.amount,
                reason=request.reason,
                type=PointHistoryType.teacher,
            )
            for uid in target_ids
        ]
        session.add_all(history_entries)
        # TODO: 이거 캐시 초기화는 안하는거임?
