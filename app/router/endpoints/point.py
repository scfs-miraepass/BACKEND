from math import ceil

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select, col

from app.core import LoginDep, SessionDep
from app.core.loggers import service_logger
from app.core.redis import redis
from app.schemas import PointHistory, Users, UserType, PointHistoryType
from app.schemas.response import ErrorResponse, ResponseModel

router = APIRouter(prefix="/point", tags=["users", "point"])
TEACHER_POINT_LIMIT = 500
STUDENT_POINT_LIMIT = 200


class PointOperation(BaseModel):
    target_user_id: int
    amount: int = Field(..., gt=0, description="처리할 포인트")
    change_type: PointHistoryType | None = Field(None, description="포인트를 처리하는 이유의 종류")


class GetLimitResponse(BaseModel):
    limit: int
    target_limit: int


async def _process_point_change(
    session: AsyncSession,
    operator: Users,
    target_user_id: int,
    amount: int,
    is_deduction: bool = False,
    change_type: PointHistoryType | None = None,
) -> int:
    """포인트 변경 로직을 처리하는 내부 함수 (Locking 및 History 생성 포함)"""
    # 동시성 문제 해결을 위해 Row-level Lock 적용 (SELECT ... FOR UPDATE)
    query = select(Users).where(Users.id == target_user_id).with_for_update()
    result = await session.execute(query)
    target_user: Users | None = result.scalar_one_or_none()

    action_name = "Deduct" if is_deduction else "Grant"

    if not target_user:
        service_logger.warning(f"{action_name} points failed. Target User ID {target_user_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    if is_deduction:
        if target_user.point < amount:
            service_logger.debug(
                f"Deduct points failed. Insufficient balance. Target: {target_user.id}, Current: {target_user.point}, Required: {amount}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient point balance.",
            )
        change_amount = -amount
    else:
        limit_key = f"point_limit:student:{target_user.id}"
        limit: int = await redis.get(limit_key)
        if limit is None:
            limit = STUDENT_POINT_LIMIT
        use_limit = limit - amount
        if use_limit < 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The target user's daily point limit has been exceeded.",
            )
        await redis.set(limit_key, use_limit, ttl=60 * 60 * 24 * 1)

        change_amount = amount

    target_user.point += change_amount

    # 포인트 이력 생성
    reason = f"{operator.name} 선생님" if operator.type == UserType.teacher else operator.name
    session.add(
        PointHistory(
            user_id=target_user.id,
            changed_amount=change_amount,
            reason=reason,
            type=change_type,
        )
    )

    # 교사가 포인트를 지급하는 경우, 교사에게도 지급
    if not is_deduction and operator.type == UserType.teacher and amount > 0:
        op_result = await session.execute(select(Users).where(Users.id == operator.id).with_for_update())
        op_user = op_result.scalar_one()
        op_user.point += amount
        session.add(
            PointHistory(
                user_id=op_user.id,
                changed_amount=amount,
                reason=f"{target_user.name} 포인트 지급",
                type=PointHistoryType.grant,
            )
        )

        await redis.delete(f"user:{op_user.id}")
        await redis.delete(f"point_history_count:{op_user.id}")
        await redis.delete_pattern(f"point_history:{op_user.id}:*")

    await session.commit()
    await session.refresh(target_user)

    # 캐시 무효화
    await redis.delete(f"user:{target_user.id}")
    await redis.delete(f"point_history_count:{target_user.id}")
    await redis.delete_pattern(f"point_history:{target_user.id}:*")
    await redis.delete_pattern("search_users:*")

    service_logger.debug(
        f"Points {action_name}ed. Executor: {operator.id}, Target: {target_user.id}, New Balance: {target_user.point}"
    )
    return target_user.point


@router.get(
    "/limit/{target_user_id}",
    responses={
        200: {"description": "정상적으로 처리됨"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    response_model=ResponseModel[GetLimitResponse],
    status_code=status.HTTP_200_OK,
    summary="포인트 지급 한도 조회",
    description="현재 로그인한 자기자신의과 지급하려는 대상의 포인트 지급 한도를 조회합니다.",
)
async def get_limit(auth_data: LoginDep, target_user_id: int):
    user, _ = auth_data
    limit_key = f"point_limit:teacher:{user.id}"
    limit: int = await redis.get(limit_key)
    if limit is None:
        limit = TEACHER_POINT_LIMIT
    student_limit: int = await redis.get(f"point_limit:student:{target_user_id}")
    if student_limit is None:
        student_limit = STUDENT_POINT_LIMIT

    return ResponseModel[GetLimitResponse](success=True, data=GetLimitResponse(limit=limit, target_limit=student_limit))


@router.get(
    "/limit",
    responses={
        200: {"description": "정상적으로 처리됨"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    response_model=ResponseModel[int],
    status_code=status.HTTP_200_OK,
    summary="포인트 지급 본인 한도 조회",
    description="현재 로그인한 자기자신의 포인트 지급 한도를 조회합니다.",
)
async def get_limit_session(
    auth_data: LoginDep,
):
    user, _ = auth_data
    limit_key = f"point_limit:teacher:{user.id}"
    limit: int = await redis.get(limit_key)
    if limit is None:
        limit = TEACHER_POINT_LIMIT

    return ResponseModel[int](success=True, data=limit)


@router.post(
    "/grant",
    responses={
        204: {"description": "정상적으로 지급이 되었음"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
        404: {
            "model": ErrorResponse,
            "description": "지급할 학생을 찾을 수 없음",
        },
        429: {
            "model": ErrorResponse,
            "description": "주간 포인트 지급 한도를 초과할 경우 발생합니다. 관리자 계정의 경우 한도가 적용되지 않습니다.",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="포인트 지급",
    description="특정 유저에게 포인트를 지급합니다. (교사 또는 관리자 전용)",
)
async def grant_points(
    operation: PointOperation,
    auth_data: LoginDep,
    session: SessionDep,
):
    user, _ = auth_data

    # 권한 확인: Teacher or Admin only
    if user.type != UserType.teacher and not user.is_admin:
        service_logger.warning(
            f"Unauthorized grant attempt. UserID: {user.id}, Role: {user.type}, Admin: {user.is_admin}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Only teachers or admins can grant points.",
        )

    if not user.is_admin:
        limit_key = f"point_limit:teacher:{user.id}"
        limit: int = await redis.get(limit_key)
        if limit is None:
            limit = TEACHER_POINT_LIMIT
        use_limit = limit - operation.amount
        if use_limit < 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The teacher's weekly point limit has been exceeded.",
            )

        await redis.set(limit_key, use_limit, ttl=60 * 60 * 24 * 7)

    await _process_point_change(
        session=session,
        operator=user,
        target_user_id=operation.target_user_id,
        amount=operation.amount,
        change_type=operation.change_type,
        is_deduction=False,
    )


@router.post(
    "/deduct",
    response_model=ResponseModel[int],
    responses={
        204: {"description": "정상적으로 차감이 되었음"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
        404: {
            "model": ErrorResponse,
            "description": "차감할 학생을 찾을 수 없음",
        },
        400: {
            "model": ErrorResponse,
            "description": "포인트 부족",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="포인트 차감",
    description="특정 유저의 포인트를 차감합니다. (서비스 유저 또는 관리자 전용)",
)
async def deduct_points(
    operation: PointOperation,
    auth_data: LoginDep,
    session: SessionDep,
):
    user, _ = auth_data

    # 권한 확인: Service or Admin only
    if user.type != UserType.service and not user.is_admin:
        service_logger.warning(
            f"Unauthorized deduct attempt. UserID: {user.id}, Role: {user.type}, Admin: {user.is_admin}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Only service users or admins can deduct points.",
        )

    new_point = await _process_point_change(
        session=session,
        operator=user,
        target_user_id=operation.target_user_id,
        amount=operation.amount,
        change_type=operation.change_type,
        is_deduction=True,
    )

    return ResponseModel[int](success=True, data=new_point)


@router.get(
    "/history",
    response_model=ResponseModel[list[PointHistory]],
    responses={
        200: {"description": "정상처리"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="포인트 기록",
    description="현재 로그인한 자기자신의 포인트 기록을 조회합니다.",
)
async def point_history(
    response: Response,
    auth_data: LoginDep,
    session: SessionDep,
    limit: int = 20,
    offset: int = 0,
):
    user, _ = auth_data

    # 1. 총 개수 조회 (캐싱 적용)
    count_cache_key = f"point_history_count:{user.id}"
    cached_count = await redis.get(count_cache_key)

    if cached_count is not None:
        count = int(cached_count)
    else:
        # Cache Miss: DB 조회
        query = select(func.count()).select_from(PointHistory).where(PointHistory.user_id == user.id)
        result = await session.execute(query)
        count = result.scalar() or 0
        # 캐시 저장 (TTL: 60초 - 짧게 설정하여 정합성 유지 노력)
        await redis.set(count_cache_key, count, ttl=60)

    # 2. 히스토리 목록 조회
    history_cache_key = f"point_history:{user.id}:{limit}:{offset}"
    cached_history = await redis.get(history_cache_key)

    if cached_history is not None:
        historys = [PointHistory(**item) for item in cached_history]
    else:
        query = (
            select(PointHistory)
            .where(PointHistory.user_id == user.id)
            .order_by(col(PointHistory.created_at).desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        historys = list(result.scalars().all())
        # 캐시 저장 (TTL: 60초)
        history_data = [item.model_dump() for item in historys]
        await redis.set(history_cache_key, history_data, ttl=60)

    max_page = str(ceil(count / limit)) if limit > 0 else "1"
    response.headers["X-MAX-PAGE"] = max_page

    return ResponseModel[list[PointHistory]](success=True, data=historys)


@router.get(
    "/{target_user_id}",
    response_model=ResponseModel[int],
    responses={
        200: {"description": "정상 처리"},
        404: {"model": ErrorResponse, "description": "유저를 찾을 수 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="포인트 조회",
    description="특정 유저의 현재 포인트를 조회합니다.",
)
async def get_point_balance(
    target_user_id: int,
    session: SessionDep,
):
    # 1. 유저 정보 캐시 확인
    cached_user = await redis.get(f"user:{target_user_id}")
    if cached_user:
        # 캐시가 있다면 그 중 포인트 정보만 반환
        return ResponseModel[int](success=True, data=cached_user.get("point", 0))

    # 2. 캐시 없으면 DB 조회
    query = select(Users.point).where(Users.id == target_user_id)
    result = await session.execute(query)
    point = result.scalar_one_or_none()

    if point is None:
        service_logger.debug(f"UserNotFound: User ID {target_user_id} does not exist.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return ResponseModel[int](success=True, data=point)
