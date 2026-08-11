from math import ceil
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlmodel import col, func, select

from app.core import LoginDep, ServiceClient
from app.schemas import PointHistory, PointHistoryType, UserPermission, Users, UserType
from app.schemas.response import ErrorResponse, ResponseModel

router = APIRouter(prefix="/point", tags=["users", "point"])
client = ServiceClient()
TEACHER_POINT_LIMIT = 1000
STUDENT_POINT_LIMIT = 1000


class PointOperation(BaseModel):
    target_user_id: int
    amount: int = Field(..., gt=0, description="처리할 포인트")
    change_type: PointHistoryType | None = Field(
        None, description="포인트를 처리하는 이유의 종류"
    )
    memo: str | None = Field(None, description="포인트를 처리하는 이유")


class GetLimitResponse(BaseModel):
    limit: int
    target_limit: int


class RankingResponse(BaseModel):
    id: int = Field(
        description="고유 ID. 교사, 서비스의 경우 자동생성. 학생의 경우 학번 사용"
    )
    name: str = Field(description="이름")
    grade: int | None = Field(description="학년")
    number: int | None = Field(description="반")
    total_point: int = Field(description="누적 포인트")
    rank: int = Field(description="현재 순위")


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
    student_limit = await client.redis.get(f"point_limit:student:{target_user_id}")
    if student_limit is None:
        student_limit = STUDENT_POINT_LIMIT
    if user.has_permission(UserPermission.NO_LIMIT_POINT):
        return ResponseModel[GetLimitResponse](
            success=True,
            data=GetLimitResponse(
                limit=TEACHER_POINT_LIMIT, target_limit=student_limit
            ),
        )

    limit_key = f"point_limit:grant:{user.id}"
    limit = await client.redis.get(limit_key)
    if limit is None:
        limit = TEACHER_POINT_LIMIT

    return ResponseModel[GetLimitResponse](
        success=True, data=GetLimitResponse(limit=limit, target_limit=student_limit)
    )


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
    if user.has_permission(UserPermission.NO_LIMIT_POINT):
        return ResponseModel[int](success=True, data=TEACHER_POINT_LIMIT)
    limit_key = f"point_limit:grant:{user.id}"
    limit = await client.redis.get(limit_key)
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
):
    user, _ = auth_data

    if not user.has_permission(UserPermission.GRANT_POINT):
        client.logs.service_point.warning(
            f"Unauthorized grant attempt. UserID: {user.id}, Role: {user.type}, Admin: {user.is_admin}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if not user.has_permission(UserPermission.NO_LIMIT_POINT):
        limit_key = f"point_limit:grant:{user.id}"
        limit = await client.redis.get(limit_key)
        if limit is None:
            limit = TEACHER_POINT_LIMIT
        use_limit = limit - operation.amount
        if use_limit < 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The teacher's weekly point limit has been exceeded.",
            )

        await client.redis.set(limit_key, use_limit, ttl=60 * 60 * 24 * 7)

    limit_key = f"point_limit:student:{operation.target_user_id}"
    limit = await client.redis.get(limit_key)
    if limit is None:
        limit = STUDENT_POINT_LIMIT
    use_limit = limit - operation.amount
    if use_limit < 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The target user's daily point limit has been exceeded.",
        )

    async with client.session:
        target_user = await client.get_user(operation.target_user_id, lock=True)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found."
            )

        reason = f"{user.name} 선생님" if user.type == UserType.teacher else user.name

        await target_user.point_grant(
            amount=operation.amount,
            reason=reason,
            memo=operation.memo,
            type=operation.change_type,
        )

        back_limit_key = f"point_limit:grant:{user.id}"
        back_limit: int = TEACHER_POINT_LIMIT
        if user.has_permission(UserPermission.NO_LIMIT_POINT):
            _ = await client.redis.get(back_limit_key)
            if _ is not None:
                back_limit = _

        # 교사가 포인트를 지급하는 경우, 교사에게도 지급
        if user.type == UserType.teacher:
            back_amount = min(back_limit, operation.amount)
            if back_amount > 0:
                await user.point_grant(
                    amount=back_amount,
                    reason=f"{target_user.name} 포인트 지급",
                    type=PointHistoryType.grant,
                    memo=operation.memo,
                )

                if user.has_permission(UserPermission.NO_LIMIT_POINT):
                    await client.redis.set(
                        back_limit_key, back_limit - back_amount, ttl=60 * 60 * 24 * 7
                    )
    await client.redis.set(limit_key, use_limit, ttl=60 * 60 * 24 * 1)


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
):
    user, _ = auth_data

    if not user.has_permission(UserPermission.DEDUCT_POINT):
        client.logs.service_point.warning(
            f"Unauthorized deduct attempt. UserID: {user.id}, Role: {user.type}, Admin: {user.is_admin}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Only service users or admins can deduct points.",
        )

    async with client.session:
        target_user = await client.get_user(operation.target_user_id, lock=True)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found."
            )

        try:
            await target_user.point_deduct(
                amount=operation.amount,
                reason=user.name,
                memo=operation.memo,
                type=operation.change_type,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient point balance.",
            )

    return ResponseModel[int](success=True, data=target_user.point)


@router.get(
    "/history",
    response_model=ResponseModel[list[PointHistory]],
    responses={
        200: {"description": "정상처리"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        }
    },
    status_code=status.HTTP_200_OK,
    summary="포인트 기록",
    description="현재 로그인한 자기자신의 포인트 기록을 조회합니다.",
)
async def get_history_list(
    response: Response,
    auth_data: LoginDep,
    limit: int = 20,
    offset: int = 0,
):
    user, _ = auth_data

    if not user.has_permission(UserPermission.VIEW_POINT_HISTORY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # 1. 총 개수 조회 (캐싱 적용)
    count_cache_key = f"point_history_count:{user.id}"
    cached_count = await client.redis.get(count_cache_key)

    async with client.session as session:
        if cached_count is not None:
            count = int(cached_count)
        else:
            # Cache Miss: DB 조회
            query = (
                select(func.count())
                .select_from(PointHistory)
                .where(PointHistory.user_id == user.id)
            )
            result = await session.execute(query)
            count = result.scalar() or 0
            # 캐시 저장 (TTL: 1일)
            await client.redis.set(count_cache_key, count, ttl=60 * 60 * 24)

        # 2. 히스토리 목록 조회
        history_cache_key = f"point_history_list:{user.id}:{limit}:{offset}"
        cached_history = await client.redis.get(history_cache_key)

        if cached_history is not None:
            historys = [PointHistory(**item) for item in cached_history]
            response.headers["X-CACHED"] = "true"
        else:
            response.headers["X-CACHED"] = "false"
            query = (
                select(PointHistory)
                .where(PointHistory.user_id == user.id)
                .order_by(col(PointHistory.created_at).desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(query)
            historys = list(result.scalars().all())
            # 캐시 저장 (TTL: 1일)
            history_data = [item.model_dump() for item in historys]
            await client.redis.set(history_cache_key, history_data, ttl=60 * 60 * 24)

    max_page = str(ceil(count / limit)) if limit > 0 else "1"
    response.headers["X-MAX-PAGE"] = max_page

    return ResponseModel[list[PointHistory]](success=True, data=historys)


@router.get(
    "/history/{target_id}",
    response_model=ResponseModel[PointHistory],
    responses={
        200: {"description": "정상처리"},
        404: {
            "model": ErrorResponse,
            "description": "포인트 기록을 찾을 수 없음",
        },
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "포인트 기록을 볼 권한이 없습니다.",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="특정 포인트 기록",
    description="특정한 포인트 기록의 데이터를 가져옵니다. 자기자신의 기록만 가져올 수 있습니다",
)
async def get_history(auth_data: LoginDep, target_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.VIEW_POINT_HISTORY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session:
        history = await client.get_history(target_id)
        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Point history not found"
            )

    if history.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied."
        )

    return ResponseModel[PointHistory](success=True, data=history)


async def _get_ranking(
    user_type: UserType,
    response: Response,
    limit: int = 20,
    offset: int = 0,
):
    async with client.session as session:
        type_str = "student" if user_type == UserType.student else "teacher"
        count_cache_key = f"ranking_count:{type_str}"
        cached_count = await client.redis.get(count_cache_key)

        if cached_count is not None:
            count = int(cached_count)
        else:
            # 기본 쿼리
            query = select(func.count()).select_from(Users)

            # 조건 추가
            conditions: Any = [Users.type == user_type]
            if user_type == UserType.teacher:
                conditions.append(
                    col(Users.permissions).op("&")(UserPermission.NO_LIMIT_POINT.value)
                    == 0
                )
            query = query.where(*conditions)

            result = await session.execute(query)
            count = result.scalar() or 0
            await client.redis.set(count_cache_key, count, ttl=60 * 5)  # 5분 캐시

        ranking_cache_key = f"ranking:{type_str}:{limit}:{offset}"
        cached_ranking = await client.redis.get(ranking_cache_key)

        if cached_ranking is not None:
            rankings = [RankingResponse(**item) for item in cached_ranking]
        else:
            # 서브쿼리 없이 Users 모델 전체와 rank를 바로 선택 (SQLModel / Pydantic 경고 방지 및 성능 개선)
            conditions: Any = [Users.type == user_type]
            if user_type == UserType.teacher:
                conditions.append(
                    col(Users.permissions).op("&")(UserPermission.NO_LIMIT_POINT.value)
                    == 0
                )

            query = (
                select(
                    Users,
                    func.dense_rank()
                    .over(order_by=col(Users.total_point).desc())
                    .label("rank"),
                )
                # 페이지네이션 시 동일 포인트의 정렬이 변경되지 않도록 tie-breaker (id) 추가
                .where(*conditions)
                .order_by(col(Users.total_point).desc(), col(Users.id).asc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(query)
            rankings = [
                RankingResponse(
                    rank=rank,
                    id=user.id,
                    name=user.name,
                    total_point=user.total_point,
                    grade=user.grade,
                    number=user.number,
                )
                for user, rank in result.all()
            ]

            ranking_data = [item.model_dump() for item in rankings]
            await client.redis.set(
                ranking_cache_key, ranking_data, ttl=60 * 5
            )  # 5분 캐시

    max_page = str(ceil(count / limit)) if limit > 0 else "1"
    response.headers["X-MAX-PAGE"] = max_page

    return ResponseModel[list[RankingResponse]](success=True, data=rankings)


@router.get(
    "/ranking/student",
    response_model=ResponseModel[list[RankingResponse]],
    responses={
        200: {"description": "정상 처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="학생 포인트 랭킹 조회",
    description="학생들의 누적 포인트를 기준으로 랭킹을 조회합니다.",
)
async def get_student_ranking(
    auth: LoginDep, response: Response, limit: int = 20, offset: int = 0
):
    user, _ = auth
    if not user.has_permission(UserPermission.VIEW_RANK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    return await _get_ranking(UserType.student, response, limit, offset)


@router.get(
    "/ranking/teacher",
    response_model=ResponseModel[list[RankingResponse]],
    responses={
        200: {"description": "정상 처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="교사 포인트 랭킹 조회",
    description="교사들의 누적 포인트를 기준으로 랭킹을 조회합니다.",
)
async def get_teacher_ranking(
    auth: LoginDep, response: Response, limit: int = 20, offset: int = 0
):
    user, _ = auth
    if not user.has_permission(UserPermission.VIEW_RANK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    return await _get_ranking(UserType.teacher, response, limit, offset)


@router.get(
    "/{target_user_id}",
    response_model=ResponseModel[int],
    responses={
        200: {"description": "정상 처리"},
        404: {"model": ErrorResponse, "description": "유저를 찾을 수 없음"},
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="포인트 조회",
    description="특정 유저의 현재 포인트를 조회합니다.",
)
async def get_point_balance(
    target_user_id: int,
    auth_data: LoginDep,
):
    user, _ = auth_data
    if not user.has_permission(UserPermission.VIEW_USER_POINT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    user = await client.get_user(target_user_id, cache=True)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return ResponseModel[int](success=True, data=user.point)
