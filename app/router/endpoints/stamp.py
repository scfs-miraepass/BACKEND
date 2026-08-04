from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import func, select

from app.core.dependency import LoginDep, ServiceClient
from app.schemas import PointHistoryType, Stamps, StampType, UserPermission
from app.schemas.response import ErrorResponse, ResponseModel

router = APIRouter(
    prefix="/stamp",
    tags=["stamp"],
)
client = ServiceClient()

STAMP_POINT = 50
BONUS_POINT = 500
BONUS_STAMP_COUNT = 10


class StampCreate(BaseModel):
    user_id: int
    stamp_type: StampType


class StampsList(BaseModel):
    stamp: str
    name: str
    have: bool
    time: datetime | None


@router.post(
    "",
    responses={
        204: {"description": "정상 처리"},
        404: {"model": ErrorResponse, "description": "유저를 찾을 수 없음"},
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
        409: {"model": ErrorResponse, "description": "이미 해당 스탬프를 발급 받음"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="스탬프 발급",
    description="유저에게 스탬프를 지급합니다.",
)
async def create_stamp(
    stamp_data: StampCreate,
    auth_data: LoginDep,
):
    current_user, _ = auth_data
    if not current_user.has_permission(UserPermission.GIVE_STAMP):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        user = await client.get_user(stamp_data.user_id, cache=True)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # 2. 스탬프 중복 수령 확인
        existing_stamp = (
            await session.execute(
                select(Stamps).where(
                    Stamps.user_id == user.id,
                    Stamps.stamp_type == stamp_data.stamp_type,
                )
            )
        ).scalar_one_or_none()
        if existing_stamp is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Stamp already exists for this user",
            )

        # 3. 스탬프 생성 및 저장
        new_stamp = Stamps(user_id=user.id, stamp_type=stamp_data.stamp_type)
        session.add(new_stamp)

        await user.point_grant(
            amount=STAMP_POINT,
            reason=f"'{stamp_data.stamp_type.value}' 스탬프",
            memo="7월 13일 '탄소중립 동아리 페스티벌'",
            type=PointHistoryType.stamp,
        )

        # 5. 보너스 포인트 지급 조건 확인
        # 현재 세션에 추가된 스탬프를 포함하여 개수를 세어야 하므로, DB 쿼리 후 +1
        user_stamps_count = (
            await session.execute(
                select(func.count(Stamps.id)).where(Stamps.user_id == user.id)
            )
        ).one()[0]
        if user_stamps_count == BONUS_STAMP_COUNT:
            await user.point_grant(
                amount=BONUS_POINT,
                reason="스탬프 10개 달성 보너스",
                memo="7월 13일 '탄소중립 동아리 페스티벌'",
                type=PointHistoryType.stamp_bonus,
            )

    client.logs.service.info(
        f"{user.id}({user.name})가 '{stamp_data.stamp_type.value}' 스탬프를 받았습니다."
    )


@router.get(
    "",
    response_model=ResponseModel[list[StampsList]],
    responses={
        200: {"description": "정상 처리"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="스탬프 목록",
    description="자기 자신의 스탬프 목록을 가져옵니다.",
)
async def get_user_stamps(auth_data: LoginDep):
    user, _ = auth_data
    if not user.has_permission(UserPermission.VIEW_STAMP):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        result = await session.execute(select(Stamps).where(Stamps.user_id == user.id))
        stamps = result.scalars().all()

    stamp_map = {stamp.stamp_type: stamp for stamp in stamps}
    payload = [
        StampsList(
            stamp=stamp_type.name,
            name=stamp_type.value,
            have=(stamp_type in stamp_map),
            time=stamp_map[stamp_type].created_at if stamp_type in stamp_map else None,
        )
        for stamp_type in StampType
    ]

    return ResponseModel[list[StampsList]](success=True, data=payload)
