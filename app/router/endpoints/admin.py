from math import ceil

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlmodel import col, func, select, update, delete

from app.core import LoginDep, ServiceClient
from app.core.service import User as ServiceUser
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


class AdminUserCreateRequest(BaseModel):
    name: str = Field(..., description="사용자 이름")
    user_type: UserType = Field(..., description="사용자 유형 (student, teacher, service)")
    grade: int | None = Field(None, description="학년 (학생인 경우 필수)")
    number: int | None = Field(None, description="반 (학생인 경우 필수)")
    student_no: int | None = Field(None, description="번호 (학생인 경우 필수)")


class AdminUserUpdateRequest(BaseModel):
    name: str | None = Field(None, description="사용자 이름")
    permissions: int | None = Field(None, description="사용자 권한")


router = APIRouter(prefix="/admin", tags=["admin"])
client = ServiceClient()


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
    size: int = Query(20, ge=1, le=100, description="페이지 당 유저 데이터 갯수 (최대 100)"),
    user_type: UserType | None = Query(None, description="유저 타입 필터 (student, teacher, service)"),
    permission: int | None = Query(None, description="유저 권한 필터 (해당 권한을 포함하는 유저 검색)"),
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
            conditions.append(col(Users.permissions).op("&")(permission) == permission)

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

        update_stmt = update(Users).where(col(Users.id).in_(target_ids)).values(**values)
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

        client.logs.service.info(
            f"관리자(ID: {user.id})가 사용자들({target_ids})의 포인트를 {request.amount}만큼 일괄 변경했습니다. (사유: {request.reason})"
        )

        for uid in target_ids:
            await client.redis.delete(f"user:{uid}")
            await client.redis.delete(f"point_history_count:{uid}")
            await client.redis.delete_pattern(f"point_history:{uid}:*")

        await client.redis.delete_pattern("ranking:student:*")
        await client.redis.delete_pattern("ranking:teacher:*")


@router.post(
    "/user",
    response_model=ResponseModel[User],
    responses={
        201: {"description": "사용자 생성 완료"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
        403: {
            "model": ErrorResponse,
            "description": "Permission denied",
        },
        409: {
            "model": ErrorResponse,
            "description": "User already exists (e.g., duplicated student ID)",
        },
    },
    status_code=status.HTTP_201_CREATED,
    summary="사용자 생성",
    description="새로운 사용자를 생성합니다. (단일 사용자 생성)",
)
async def create_user(request: AdminUserCreateRequest, auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        if request.user_type == UserType.student:
            if not all([request.grade, request.number, request.student_no]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Grade, class number, and student number are required for a student user.",
                )

            user_id = int(f"{request.grade}{request.number}{request.student_no:02d}")
            existing_user = await session.get(Users, user_id)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User with ID {user_id} already exists.",
                )

            new_user = Users(
                id=user_id,
                type=UserType.student,
                name=request.name,
                grade=request.grade,
                number=request.number,
            )
        elif request.user_type == UserType.teacher:
            current_id = 4000
            while True:
                id_check = await session.get(Users, current_id)
                if not id_check:
                    break
                current_id += 1
            new_user = Users(id=current_id, type=UserType.teacher, name=request.name)
        elif request.user_type == UserType.service:
            current_id = 5000
            while True:
                id_check = await session.get(Users, current_id)
                if not id_check:
                    break
                current_id += 1
            new_user = Users(id=current_id, type=UserType.service, name=request.name)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported user type.",
            )

        session.add(new_user)

        client.logs.service.info(
            f"관리자(ID: {user.id})가 새 사용자(ID: {new_user.id}, 유형: {new_user.type})를 생성했습니다."
        )

    return ResponseModel[User](success=True, data=new_user)


@router.patch(
    "/users/{user_id}/password",
    responses={
        204: {"description": "정상 처리 (비밀번호 초기화됨)"},
        403: {
            "model": ErrorResponse,
            "description": "Permission denied",
        },
        404: {
            "model": ErrorResponse,
            "description": "User not found",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="사용자 비밀번호 초기화",
    description="특정 사용자의 비밀번호를 초기화(None으로 설정)합니다. 이후 사용자가 처음 로그인할 때 새로 설정하게 됩니다.",
)
async def reset_user_password(user_id: int, auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session:
        target_user = await client.get_user(user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found.",
            )

        await target_user.update_password(None)

        client.logs.service.info(f"관리자(ID: {user.id})가 사용자(ID: {user_id})의 비밀번호를 초기화했습니다.")


@router.patch(
    "/users/{user_id}",
    response_model=ResponseModel[User],
    responses={
        200: {"description": "사용자 정보 수정 완료"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
        403: {
            "model": ErrorResponse,
            "description": "Permission denied",
        },
        404: {
            "model": ErrorResponse,
            "description": "User not found",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="사용자 정보 수정",
    description="특정 사용자의 정보를 수정합니다. (이름, 권한 등)",
)
async def update_user(user_id: int, request: AdminUserUpdateRequest, auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify yourself.",
        )

    async with client.session as session:
        target_user = await client.get_user(user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found.",
            )

        update_data = request.model_dump(exclude_unset=True)
        if update_data:
            for key, value in update_data.items():
                setattr(target_user, key, value)
            session.add(target_user)

    if update_data:
        client.logs.service.info(
            f"관리자(ID: {user.id})가 사용자(ID: {target_user.id})의 정보를 수정했습니다: {update_data}"
        )

        await client.redis.delete(f"user:{target_user.id}")
        await client.redis.delete_pattern(f"ranking:{target_user.type!s}:*")
        await ServiceUser(target_user).clear_search_cache()

    return ResponseModel[User](success=True, data=target_user)


@router.delete(
    "/users/{user_id}",
    responses={
        204: {"description": "정상 처리"},
        403: {
            "model": ErrorResponse,
            "description": "Permission denied",
        },
        404: {
            "model": ErrorResponse,
            "description": "User not found",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="사용자 삭제",
    description="특정 사용자를 삭제합니다.",
)
async def delete_user(user_id: int, auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.MANAGE_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        target_user = await client.get_user(user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found.",
            )

        exc = delete(Users).where(col(Users.id) == target_user.id)
        await session.execute(exc)

        client.logs.service.info(f"관리자(ID: {user.id})가 사용자(ID: {user_id})를 삭제했습니다.")

    await client.redis.delete(f"user:{target_user.id}")
    await client.redis.delete(f"point_history_count:{target_user.id}")
    await client.redis.delete_pattern(f"point_history:{target_user.id}:*")
    await client.redis.delete_pattern(f"ranking:{target_user.type!s}:*")
    await target_user.clear_search_cache()
