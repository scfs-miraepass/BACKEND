from fastapi import APIRouter, status, HTTPException, Response
from pydantic import BaseModel, Field
from datetime import date as dt_date, datetime
from sqlmodel import select, col

from app.core import ServiceClient, LoginDep
from app.schemas import Karaokes, UserPermission
from app.schemas.response import ResponseModel, ErrorResponse

router = APIRouter(prefix="/karaoke", tags=["karaoke"])
client = ServiceClient()

# 예약 경매 목록 조회 (GET /karaoke)
# 예약 경매 생성 (POST /karaoke)
# 예약 경매 조회 (GET /karaoke/{id})
# 예약 경매 삭제 (DELETE /karaoke/{id})
# TODO: 예약 경매 입찰 (POST /karaoke/{id}/bid)
# TODO: 파티원 초대
# TODO: 파티 나감
# TODO: 웹 소켓


class KaraokeCreate(BaseModel):
    date: dt_date = Field(description="예약 일자")
    time: int = Field(ge=1, le=8, description="예약 시간 (1~7교시, 점심시간 8)")

    start_time: datetime = Field(description="예약 경매 시작 시간")
    end_time: datetime = Field(description="예약 경매 종료 시간, 'start_time' 시간보다 앞서 있으면 안됩니다.")

    min_point: int = Field(default=0, description="최소 입찰가")


@router.get(
    "",
    response_model=ResponseModel[list[Karaokes]],
    responses={
        200: {"description": "정상적으로 처리됨."},
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="예약 목록 조회",
    description="현재 예약할 수 있는 목록을 조회합니다",
)
async def get_list_karaoke(response: Response, auth_data: LoginDep, date: dt_date | None = None):
    user, _ = auth_data

    if not user.has_permission(UserPermission.VIEW_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if date is None:
        date = dt_date.today()

    cache_key = f"karaoke_list:{date}"
    cached = await client.redis.get(cache_key)
    if cached is not None:
        # 캐시가 있는경우 캐시 응답
        response.headers["X-CACHED"] = "true"
        return ResponseModel[list[Karaokes]](success=True, data=[Karaokes(**item) for item in cached])

    async with client.session as session:
        response.headers["X-CACHED"] = "false"
        query = select(Karaokes).order_by(col(Karaokes.time))
        result = await session.execute(query)
        karaokes = list(result.scalars().all())

        # 캐시 저장
        await client.redis.set(cache_key, [item.model_dump() for item in karaokes], ttl=60 * 5)

    return ResponseModel[list[Karaokes]](success=True, data=karaokes)


@router.post(
    "",
    response_model=ResponseModel[Karaokes],
    responses={
        201: {"description": "정상적으로 생성이 완료됨"},
        400: {
            "model": ErrorResponse,
            "description": "잘못된 요청 데이터",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        },
        409: {
            "model": ErrorResponse,
            "description": "중복된 경매 존재",
        },
    },
    status_code=status.HTTP_201_CREATED,
    summary="노래방 경매 생성",
    description="특정 시간대의 노래방 경매를 생성합니다.",
)
async def create_karaoke(body: KaraokeCreate, auth_data: LoginDep):
    user, _ = auth_data

    if not user.has_permission(UserPermission.MANAGE_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if body.end_time <= body.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time.",
        )

    async with client.session as session:
        # 해당 일자, 해당 시간에 이미 경매가 생성되어 있는지 확인
        query = select(Karaokes).where(Karaokes.date == body.date, Karaokes.time == body.time)
        result = await session.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Karaoke already exists for the given date and time.",
            )

        # 생성
        karaoke = Karaokes(
            date=body.date,
            time=body.time,
            start_time=body.start_time,
            end_time=body.end_time,
            min_point=body.min_point,
        )
        session.add(karaoke)
        await session.flush()

    client.logs.service_karaoke.info(
        f"{user.name}({user.id})님이 {karaoke.id}({karaoke.date} / {karaoke.time}) 노래방 예약을 생성했습니다"
    )
    return ResponseModel[Karaokes](success=True, data=karaoke)


@router.get(
    "/{karaoke_id}",
    response_model=ResponseModel[Karaokes],
    responses={
        200: {"description": "정상적으로 처리됨."},
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        },
        404: {
            "model": ErrorResponse,
            "description": "예약을 찾을 수 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="예약 조회",
    description="특정 예약을 조회합니다.",
)
async def get_karaoke(auth_data: LoginDep, karaoke_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.VIEW_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    karaoke = await client.get_karaoke(karaoke_id, cache=True)
    if karaoke is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Karaoke not found")

    return ResponseModel[Karaokes](success=True, data=karaoke)


@router.delete(
    "/{karaoke_id}",
    responses={
        204: {"description": "정상적으로 처리됨."},
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        },
        404: {
            "model": ErrorResponse,
            "description": "예약을 찾을 수 없음",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="예약 삭제",
    description="특정 예약을 삭제합니다.",
)
async def delete_karaoke(auth_data: LoginDep, karaoke_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.MANAGE_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    karaoke = await client.get_karaoke(karaoke_id, cache=True)
    if karaoke is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Karaoke not found")

    await karaoke.delete()
