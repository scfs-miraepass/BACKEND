from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from math import ceil


from app.core.database import get_async_session
from app.core.dependency import LoginDep
from app.core.loggers import service_logger
from app.schemas.response import ResponseModel, ErrorResponse
from app.schemas import Users, UserType, PointHistory

router = APIRouter(prefix="/point", tags=["users", "point"])


class PointOperation(BaseModel):
    target_user_id: int
    amount: int = Field(..., gt=0, description="Amount of points")


async def _process_point_change(
    session: AsyncSession,
    operator: Users,
    target_user_id: int,
    amount: int,
    is_deduction: bool = False,
) -> int:
    """포인트 변경 로직을 처리하는 내부 함수 (Locking 및 History 생성 포함)"""
    # 동시성 문제 해결을 위해 Row-level Lock 적용 (SELECT ... FOR UPDATE)
    query = select(Users).where(Users.id == target_user_id).with_for_update()
    result = await session.execute(query)
    target_user = result.scalar_one_or_none()

    action_name = "Deduct" if is_deduction else "Grant"

    if not target_user:
        service_logger.debug(f"{action_name} points failed. Target User ID {target_user_id} not found.")
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
        change_amount = amount

    target_user.point += change_amount

    # 포인트 이력 생성
    history = PointHistory(
        user_id=target_user.id,
        changed_amount=change_amount,
        reason=operator.name,
    )
    session.add(history)

    await session.commit()
    await session.refresh(target_user)

    service_logger.debug(
        f"Points {action_name}ed. Executor: {operator.id}, Target: {target_user.id}, Amount: {amount}, New Balance: {target_user.point}"
    )
    service_logger.debug(f"Point history recorded for user {target_user.id}")

    return target_user.point


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
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="포인트 지급",
    description="특정 유저에게 포인트를 지급합니다. (교사 전용)",
)
async def grant_points(
    operation: PointOperation,
    auth_data: LoginDep,
    session: AsyncSession = Depends(get_async_session),
):
    user, _ = auth_data

    # 권한 확인: Teacher only
    if user.type != UserType.teacher:
        service_logger.warning(f"Unauthorized grant attempt. UserID: {user.id}, Role: {user.type}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Only teachers can grant points.",
        )

    await _process_point_change(
        session=session,
        operator=user,
        target_user_id=operation.target_user_id,
        amount=operation.amount,
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
    description="특정 유저의 포인트를 차감합니다. (서비스 유저 전용)",
)
async def deduct_points(
    operation: PointOperation,
    auth_data: LoginDep,
    session: AsyncSession = Depends(get_async_session),
):
    user, _ = auth_data

    # 권한 확인: Service only
    if user.type != UserType.service:
        service_logger.warning(f"Unauthorized deduct attempt. UserID: {user.id}, Role: {user.type}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Only service users can deduct points.",
        )

    new_balance = await _process_point_change(
        session=session,
        operator=user,
        target_user_id=operation.target_user_id,
        amount=operation.amount,
        is_deduction=True,
    )

    return ResponseModel[int](success=True, data=new_balance)


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
    auth_data: LoginDep,
    session: AsyncSession = Depends(get_async_session),
):
    query = select(Users.point).where(Users.id == target_user_id)
    result = await session.execute(query)
    point = result.scalar_one_or_none()

    if point is None:
        service_logger.debug(f"UserNotFound: User ID {target_user_id} does not exist.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return ResponseModel[int](success=True, data=point)


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
    session: AsyncSession = Depends(get_async_session),
    limit: int = 20,
    offset: int = 0,
):
    user, _ = auth_data

    query = select(func.count()).select_from(PointHistory).where(PointHistory.user_id == user.id)
    result = await session.execute(query)
    count = result.scalar() or 0

    query = (
        select(PointHistory)
        .where(PointHistory.user_id == user.id)
        .order_by(PointHistory.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    historys = list(result.scalars().all())

    max_page = str(ceil(count / limit))
    response.headers["X-MAX-PAGE"] = max_page

    return ResponseModel[list[PointHistory]](success=True, data=historys)
