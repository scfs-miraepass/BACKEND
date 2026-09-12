from fastapi import APIRouter, status, HTTPException, Response
from pydantic import BaseModel, Field
from datetime import date as dt_date, datetime
from sqlmodel import select, col

from app.core import ServiceClient, LoginDep
from app.schemas import Karaokes, User, UserPermission, KaraokeBids, KaraokeMembers, KaraokePartis, KaraokeStatus
from app.schemas.karaokes import Karaoke as SchemasKaraoke
from app.schemas.response import ResponseModel, ErrorResponse
from app.core.service.karaoke import KaraokeParty, KaraokeMember, Karaoke
from app.core.error import Conflict, PointInsufficient
from fastapi import WebSocket, WebSocketDisconnect
from asyncio import create_task

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


class KaraokeResponse(SchemasKaraoke):
    highest_bid: int | None = None


class KaraokeFinalBidResponse(BaseModel):
    id: int
    auction_id: int
    party_id: int | None
    amount: int
    created_at: datetime
    bidder: User


class KaraokePartyDetail(BaseModel):
    id: int
    auction_id: int
    leader_id: int
    dispersed: bool
    leader: User
    members: list[User] = Field(description="파티에 소속된 멤버 목록 (초대 수락 완료)")
    pending_members: list[User] = Field(description="파티에 초대되어 수락 대기중인 멤버 목록")


async def _build_party_detail(party: KaraokeParty) -> KaraokePartyDetail:
    leader = await client.get_user(party.leader_id)
    if leader is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party leader user not found")

    members = await party.get_members()
    pending_members = await party.get_pending_members()

    # noinspection bad-argument-type
    return KaraokePartyDetail(
        id=party.id,
        auction_id=party.auction_id,
        leader_id=party.leader_id,
        dispersed=party.dispersed,
        leader=leader,
        members=members,
        pending_members=pending_members,
    )


@router.get(
    "",
    operation_id="get_karaoke_list",
    response_model=ResponseModel[list[KaraokeResponse]],
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
        return ResponseModel[list[KaraokeResponse]](success=True, data=[KaraokeResponse(**item) for item in cached])

    async with client.session as session:
        response.headers["X-CACHED"] = "false"
        query = select(Karaokes).where(Karaokes.date == date).order_by(col(Karaokes.time))
        result = await session.execute(query)
        karaokes = list(result.scalars().all())

        karaoke_responses = []
        for k in karaokes:
            dump = k.model_dump()
            if k.status == KaraokeStatus.IN_PROGRESS:
                k_serv = await client.get_karaoke(k.id)
                if k_serv:
                    highest = await k_serv.get_highest()
                    dump["highest_bid"] = highest.amount if highest else None
            karaoke_responses.append(KaraokeResponse(**dump))

        # 캐시 저장
        await client.redis.set(cache_key, [item.model_dump(mode="json") for item in karaoke_responses], ttl=60 * 5)

    return ResponseModel[list[KaraokeResponse]](success=True, data=karaoke_responses)


@router.post(
    "",
    operation_id="create_karaoke",
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

    await client.redis.delete_pattern(f"karaoke_list:{body.date}")

    client.logs.service_karaoke.info(
        f"{user.name}({user.id})님이 {karaoke.id}({karaoke.date} / {karaoke.time}) 노래방 예약을 생성했습니다"
    )
    return ResponseModel[Karaokes](success=True, data=karaoke)


@router.get(
    "/{karaoke_id}",
    operation_id="get_karaoke",
    response_model=ResponseModel[KaraokeResponse],
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

    dump = karaoke.payload.model_dump()
    if karaoke.status == KaraokeStatus.IN_PROGRESS:
        highest = await karaoke.get_highest()
        dump["highest_bid"] = highest.amount if highest else None

    return ResponseModel[KaraokeResponse](success=True, data=KaraokeResponse(**dump))


@router.delete(
    "/{karaoke_id}",
    operation_id="delete_karaoke",
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
    operation_id="create_karaoke_party",
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


@router.get(
    "/{karaoke_id}/party/me",
    operation_id="get_my_karaoke_party",
    response_model=ResponseModel[KaraokePartyDetail],
    responses={
        200: {"description": "정상적으로 처리됨."},
        403: {"model": ErrorResponse, "description": "권한 없음"},
        404: {"model": ErrorResponse, "description": "예약을 찾을 수 없거나, 속한 파티가 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="내 파티 조회",
    description="특정 노래방 예약 경매에서 자신이 리더이거나 소속되어 있는 파티를 조회합니다.",
)
async def get_my_karaoke_party(auth_data: LoginDep, karaoke_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    karaoke = await client.get_karaoke(karaoke_id, cache=True)
    if not karaoke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Karaoke not found")

    party = await user.get_party(karaoke)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not in a party for this auction")

    return ResponseModel[KaraokePartyDetail](success=True, data=await _build_party_detail(party))


@router.post(
    "/{karaoke_id}/bid",
    operation_id="create_karaoke_bid",
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


@router.get(
    "/{karaoke_id}/final-bid",
    operation_id="get_karaoke_final_bid",
    response_model=ResponseModel[KaraokeFinalBidResponse],
    responses={
        200: {"description": "정상적으로 처리됨."},
        403: {"model": ErrorResponse, "description": "권한 없음"},
        404: {"model": ErrorResponse, "description": "예약을 찾을 수 없거나, 입찰 기록이 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="최종 입찰(낙찰자) 조회",
    description=(
        "해당 경매의 최종(마지막) 입찰 기록과 낙찰자 정보를 조회합니다. "
        "Redis 캐시(highest_bid)와 달리 DB를 직접 조회하므로 경매 종료 후 캐시가 만료되어도 확인할 수 있습니다."
    ),
)
async def get_karaoke_final_bid(auth_data: LoginDep, karaoke_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.VIEW_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    karaoke = await client.get_karaoke(karaoke_id, cache=True)
    if not karaoke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Karaoke not found")

    bid = await karaoke.get_final_bid()
    if bid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No bids have been placed for this auction")

    bidder = await client.get_user(bid.bidder_id)
    if bidder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bidder user not found")

    # noinspection bad-argument-type
    return ResponseModel[KaraokeFinalBidResponse](
        success=True,
        data=KaraokeFinalBidResponse(
            id=bid.id,
            auction_id=bid.auction_id,
            party_id=bid.party_id,
            amount=bid.amount,
            created_at=bid.created_at,
            bidder=bidder,
        ),
    )


@router.get(
    "/party/{party_id}",
    operation_id="get_karaoke_party",
    response_model=ResponseModel[KaraokePartyDetail],
    responses={
        200: {"description": "정상적으로 처리됨."},
        403: {"model": ErrorResponse, "description": "권한 없음 (파티에 소속되거나 초대받지 않음)"},
        404: {"model": ErrorResponse, "description": "파티를 찾을 수 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="파티 조회",
    description=(
        "파티 ID로 파티 상세 정보를 조회합니다. 자신이 파티장이거나, 파티에 소속(또는 초대 대기중)인 경우에만 "
        "조회할 수 있습니다. 초대장 목록(`/karaoke/party/invites/me`)에서 받은 `party_id`로 "
        "초대받은 파티가 어떤 경매의, 누구의 파티인지 확인할 때 사용합니다."
    ),
)
async def get_karaoke_party(auth_data: LoginDep, party_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    party = await KaraokeParty.get_by_id(party_id)
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")

    # 파티장 본인이거나, 파티에 소속(초대 대기중 포함)된 유저만 조회할 수 있습니다.
    if party.leader_id != user.id and await user.get_karaoke_member(party_id) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this party")

    return ResponseModel[KaraokePartyDetail](success=True, data=await _build_party_detail(party))


@router.delete(
    "/party/{party_id}",
    operation_id="disperse_karaoke_party",
    responses={
        204: {"description": "정상적으로 파티 해산 완료"},
        400: {"model": ErrorResponse, "description": "이미 해산된 파티"},
        403: {"model": ErrorResponse, "description": "권한 없음 (파티장이 아님)"},
        404: {"model": ErrorResponse, "description": "파티를 찾을 수 없음"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="파티 해산",
    description="파티장이 자신이 리더인 파티를 자발적으로 해산합니다.",
)
async def disperse_karaoke_party(auth_data: LoginDep, party_id: int):
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the party leader can disperse the party"
        )

    if party.dispersed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Party is already dispersed")

    await party.disperse()


@router.delete(
    "/party/{party_id}/leave",
    operation_id="leave_karaoke_party",
    responses={
        204: {"description": "정상적으로 파티 탈퇴 완료"},
        400: {"model": ErrorResponse, "description": "파티장은 탈퇴할 수 없음 (해산 API 사용 필요)"},
        403: {"model": ErrorResponse, "description": "권한 없음"},
        404: {"model": ErrorResponse, "description": "파티를 찾을 수 없거나, 소속된 멤버가 아님"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="파티 탈퇴",
    description="자신이 소속된 파티에서 스스로 탈퇴합니다. 파티장은 이 API를 사용할 수 없으며, 해산 API를 사용해야 합니다.",
)
async def leave_karaoke_party(auth_data: LoginDep, party_id: int):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    party = await KaraokeParty.get_by_id(party_id)
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")

    if party.leader_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Party leader cannot leave. Disperse the party instead."
        )

    member = await user.get_karaoke_member(party_id)
    if not member or member.pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not an active member of this party")

    await member.leave()


@router.delete(
    "/party/{party_id}/members/{user_id}",
    operation_id="kick_karaoke_party_member",
    response_model=ResponseModel[KaraokePartyDetail],
    responses={
        200: {"description": "정상적으로 멤버 강퇴 완료"},
        400: {"model": ErrorResponse, "description": "파티장은 강퇴할 수 없음"},
        403: {"model": ErrorResponse, "description": "권한 없음 (파티장이 아님)"},
        404: {"model": ErrorResponse, "description": "파티, 유저 또는 파티 멤버를 찾을 수 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="파티원 강퇴",
    description="파티장이 자신이 리더인 파티에서 특정 멤버를 강퇴합니다. 강퇴 시 새 파티가 생성되므로 응답으로 갱신된 파티 정보를 반환합니다.",
)
async def kick_karaoke_party_member(auth_data: LoginDep, party_id: int, user_id: int):
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the party leader can kick members")

    if user_id == party.leader_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot kick the party leader")

    target_user = await client.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to kick not found")

    member = await target_user.get_karaoke_member(party_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this party")

    new_party = await party.kick_members(target_user)
    return ResponseModel[KaraokePartyDetail](success=True, data=await _build_party_detail(new_party))


class KaraokeInviteCreate(BaseModel):
    user_id: int = Field(description="초대할 유저의 ID")


@router.post(
    "/party/{party_id}/invite",
    operation_id="invite_karaoke_party_member",
    responses={
        204: {"description": "정상적으로 초대 완료"},
        400: {"model": ErrorResponse, "description": "해산된 파티이거나, 파티장 자신을 초대함"},
        403: {"model": ErrorResponse, "description": "권한 없음 (파티장이 아님)"},
        404: {"model": ErrorResponse, "description": "파티나 초대할 유저를 찾을 수 없음"},
        409: {"model": ErrorResponse, "description": "이미 이 경매의 파티에 소속되었거나 초대된 유저"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="파티원 초대",
    description=(
        "자신이 파티장인 파티에 파티원을 초대합니다. "
        "한 유저는 하나의 경매에서 하나의 파티에만 소속될 수 있으므로, "
        "이미 같은 경매의 파티에 소속되었거나 초대 대기중인 유저는 초대할 수 없습니다."
    ),
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

    try:
        await party.invite_user(invite_user)
    except Conflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/party/invites/me",
    operation_id="get_my_karaoke_party_invites",
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
    operation_id="decide_karaoke_party_invite",
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


@router.websocket("/{karaoke_id}/ws")
async def karaoke_websocket(websocket: WebSocket, auth_data: LoginDep, karaoke_id: int):
    user, _ = auth_data

    await websocket.accept()

    if not user.has_permission(UserPermission.VIEW_KARAOKE):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    _karaoke = await client.get_karaoke(karaoke_id, cache=True)
    if _karaoke is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async def get_state(karaoke: Karaoke):
        highest_bid = await karaoke.get_highest()

        cache_key = f"karaoke:{karaoke.id}:bids_history"
        cached_bids = await client.redis.get(cache_key)

        if cached_bids is not None:
            bids_history_dump = cached_bids
        else:
            async with client.session as session:
                query = (
                    select(KaraokeBids)
                    .where(KaraokeBids.auction_id == karaoke_id)
                    .order_by(col(KaraokeBids.created_at).desc())
                )
                res = await session.execute(query)
                bids_history = res.scalars().all()
                bids_history_dump = [b.model_dump(mode="json") for b in bids_history]

            await client.redis.set(cache_key, bids_history_dump, ttl=60 * 5)

        now = datetime.now().astimezone() if karaoke.end_time.tzinfo else datetime.now()
        remaining_time = int((karaoke.end_time - now).total_seconds())

        return {
            "highest_bid": highest_bid.model_dump(mode="json") if highest_bid else None,
            "bids_history": bids_history_dump,
            "remaining_time": remaining_time if remaining_time > 0 else 0,
        }

    # 초기 상태 전송
    await websocket.send_json(await get_state(_karaoke))

    # Redis Pub/Sub 구독
    pubsub = client.redis.pubsub()
    await pubsub.subscribe(f"ws_karaoke_{karaoke_id}")

    async def redis_listener(karaoke: Karaoke):
        async for message in pubsub.listen():
            if message["type"] == "message":
                # 최고가가 갱신되면 다시 조회 후 상태 전송
                state = await get_state(karaoke)
                try:
                    await websocket.send_json(state)
                except Exception:
                    break

    listener_task = create_task(redis_listener(_karaoke))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        listener_task.cancel()
        await pubsub.unsubscribe(f"ws_karaoke_{karaoke_id}")
        await pubsub.close()
