from fastapi import APIRouter, status, HTTPException, Response
from pydantic import BaseModel, Field
from datetime import date as dt_date, datetime
from sqlmodel import select, col

from app.core import ServiceClient, LoginDep
from app.schemas import Karaokes, UserPermission, KaraokeBids, KaraokeMembers, KaraokePartis
from app.schemas.response import ResponseModel, ErrorResponse
from app.core.service.karaoke import KaraokeParty, KaraokeMember
from app.core.error import PointInsufficient

router = APIRouter(prefix="/karaoke", tags=["karaoke"])
client = ServiceClient()


class KaraokeCreate(BaseModel):
    date: dt_date = Field(description="일자")
    time: int = Field(ge=1, le=8, description="시간 (1~7교시, 점심시간 8)")

    start_time: datetime = Field(description="경매 시작 시간")
    end_time: datetime = Field(description="경매 종료 시간, 'start_time' 시간보다 앞서 있으면 안됩니다.")

    min_point: int = Field(default=0, description="최소 입찰가")


class KaraokeBidCreate(BaseModel):
    amount: int = Field(gt=0, description="입찰 금액")


class KaraokeInviteAction(BaseModel):
    accept: bool = Field(description="초대 수락 여부")


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


@router.post(
    "/{karaoke_id}/party",
    response_model=ResponseModel[KaraokePartis],
    responses={
        201: {"description": "정상적으로 파티 생성 완료"},
        400: {"model": ErrorResponse, "description": "파티 생성 조건 불만족 (이미 생성 등)"},
        403: {"model": ErrorResponse, "description": "권한 없음"},
        404: {"model": ErrorResponse, "description": "예약을 찾을 수 없음"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="예약 경매 파티 생성",
    description="진행중인 노래방 예약 경매에 파티를 생성합니다.",
)
async def create_karaoke_party(auth_data: LoginDep, karaoke_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    karaoke = await client.get_karaoke(karaoke_id)
    if not karaoke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Karaoke not found")

    try:
        party = await karaoke.create_party(leader=user)
        return ResponseModel[KaraokePartis](success=True, data=party)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{karaoke_id}/bid",
    response_model=ResponseModel[KaraokeBids],
    responses={
        201: {"description": "정상적으로 입찰 완료"},
        400: {"model": ErrorResponse, "description": "입찰 조건 불만족 (금액 부족 등)"},
        402: {"model": ErrorResponse, "description": "포인트 부족"},
        403: {"model": ErrorResponse, "description": "권한 없음"},
        404: {"model": ErrorResponse, "description": "예약/파티를 찾을 수 없음"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="예약 경매 입찰",
    description="진행중인 노래방 예약 경매에 입찰합니다.",
)
async def create_karaoke_bid(auth_data: LoginDep, karaoke_id: int, body: KaraokeBidCreate):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    karaoke = await client.get_karaoke(karaoke_id)
    if not karaoke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Karaoke not found")

    party = await user.get_party(karaoke)
    if party is not None:
        if party.leader_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only party leader can bid on behalf of the party"
            )

    try:
        bid = await karaoke.add_bid(bidder=user, amount=body.amount, party=party)
        return ResponseModel[KaraokeBids](success=True, data=bid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PointInsufficient as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))


class KaraokeInviteCreate(BaseModel):
    user_id: int = Field(description="초대할 유저의 ID")


@router.post(
    "/party/{party_id}/invite",
    response_model=ResponseModel[KaraokeMembers],
    responses={
        204: {"description": "정상적으로 초대 완료"},
        403: {"model": ErrorResponse, "description": "권한 없음 (파티장이 아님)"},
        404: {"model": ErrorResponse, "description": "파티나 초대할 유저를 찾을 수 없음"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="파티원 초대",
    description="자신이 파티장인 파티에 파티원을 초대합니다.",
)
async def invite_karaoke_party_member(auth_data: LoginDep, party_id: int, body: KaraokeInviteCreate):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    party = await KaraokeParty.get_by_id(party_id)
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")

    if party.leader_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the party leader can invite members")

    invite_user = await client.get_user(body.user_id)
    if not invite_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to invite not found")

    await party.invite_user(invite_user)


@router.get(
    "/party/invites/me",
    response_model=ResponseModel[list[KaraokeMembers]],
    status_code=status.HTTP_200_OK,
    summary="파티원 초대장 목록 보기",
    description="자기 자신에게 온 파티원 초대장 목록을 조회합니다.",
)
async def get_my_party_invites(auth_data: LoginDep):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        query = select(KaraokeMembers).where(KaraokeMembers.user_id == user.id, KaraokeMembers.pending == True)
        exc = await session.execute(query)
        invites = list(exc.scalars().all())

    return ResponseModel[list[KaraokeMembers]](success=True, data=invites)


@router.post(
    "/party/{party_id}/action",
    response_model=ResponseModel[bool],
    responses={
        200: {"description": "정상적으로 수락/거절 완료"},
        404: {"model": ErrorResponse, "description": "대기 중인 초대장을 찾을 수 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="파티원 초대장 수락 및 거절",
    description="받은 파티원 초대장을 수락하거나 거절합니다.",
)
async def decide_karaoke_party_invite(auth_data: LoginDep, party_id: int, body: KaraokeInviteAction):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # noinspection bad-argument-type
    member = await KaraokeMember.get_member(party_id, user.id)
    if not member or not member.pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending invitation not found")

    if body.accept:
        await member.accept()
    else:
        await member.reject()

    return ResponseModel[bool](success=True, data=True)
