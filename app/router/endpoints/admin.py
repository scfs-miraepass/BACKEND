from math import ceil

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlmodel import col, func, select, update

from app.core import LoginDep, ServiceClient
from app.schemas import (
    PointHistory,
    PointHistoryType,
    User,
    UserPermission,
    Users,
    UserType,
)
from app.schemas.response import ErrorResponse, ResponseModel


class AdminPointRequest(BaseModel):
    user_ids: list[int] = Field(
        ...,
        description="포인트를 지급/차감할 대상 유저 ID 목록",
    )
    amount: int = Field(..., description="변동될 포인트 (양수는 지급, 음수는 차감)")
    reason: str = Field(..., description="포인트 변동 사유")


router = APIRouter(prefix="/admin", tags=["admin"])
client = ServiceClient()


@router.get(
    "/student",
    response_model=ResponseModel[list[User]],
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

    return ResponseModel[list[User]](success=True, data=users)


@router.get(
    "/users",
    response_model=ResponseModel[list[User]],
    responses={
        200: {"description": "정상적으로 처리 됨"},
        403: {
            "model": ErrorResponse,
            "description": "권한 거부",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="전체 사용자 목록",
    description="전체 사용자 목록을 조회합니다. 유저 타입 및 권한으로 필터링할 수 있습니다.",
)
async def get_users(
    response: Response,
    auth_data: LoginDep,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(
        20, ge=1, le=100, description="페이지 당 유저 데이터 갯수 (최대 100)"
    ),
    user_type: UserType | None = Query(None, description="유저 타입 필터 (student, teacher, service)"),
    permission: UserPermission | None = Query(None, description="유저 권한 필터 (해당 권한을 포함하는 유저 검색)"),
):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        conditions = []
        if user_type is not None:
            conditions.append(Users.type == user_type)
        if permission is not None:
            conditions.append(Users.permissions.op("&")(permission.value) == permission.value)

        count_query = select(func.count()).select_from(Users)
        query = select(Users)

        for condition in conditions:
            count_query = count_query.where(condition)
            query = query.where(condition)

        total_count = (await session.execute(count_query)).scalar_one()
        max_page = ceil(total_count / size) if total_count > 0 else 1
        response.headers["X-MAX-PAGE"] = str(max_page)
        
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)

        result = await session.execute(query)
        users = result.scalars().all()

    return ResponseModel[list[User]](success=True, data=users)


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
async def update_users_point(request: AdminPointRequest, auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if not request.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_ids must be provided.",
        )

    async with client.session as session:
        target_query = select(Users).where(col(Users.id).in_(request.user_ids))
        result = await session.execute(target_query)
        target_users = result.scalars().all()

        if not target_users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No target users found.",
            )

        target_ids = [u.id for u in target_users]
        
        values = {"point": Users.point + request.amount}
        if request.amount > 0:
            values["total_point"] = Users.total_point + request.amount

        update_stmt = (
            update(Users)
            .where(col(Users.id).in_(target_ids))
            .values(**values)
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
        
        for uid in target_ids:
            await client.redis.delete(f"user:{uid}")
            await client.redis.delete(f"point_history_count:{uid}")
            await client.redis.delete_pattern(f"point_history:{uid}:*")
        
        await client.redis.delete_pattern("ranking:student:*")
        await client.redis.delete_pattern("ranking:teacher:*")
                
