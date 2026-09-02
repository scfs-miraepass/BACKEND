import json
import asyncio
from datetime import date as dt_date, datetime

from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlmodel import select, col

from app.core import LoginDep, ServiceClient
from app.schemas.users import UserPermission
from app.schemas.response import ErrorResponse, ResponseModel
from app.schemas.karaoke import KaraokeAuction, KaraokeBid, PeriodType, AuctionStatus, KaraokeBidStatus
from app.schemas.point import PointHistoryType

router = APIRouter(prefix="/karaoke", tags=["karaoke"])
client = ServiceClient()


class AuctionCreate(BaseModel):
    target_date: dt_date
    period: PeriodType
    start_time: datetime
    end_time: datetime
    min_bid: int = Field(default=0, description="최소 입찰가")


class BidRequest(BaseModel):
    amount: int = Field(..., gt=0, description="입찰 금액")


@router.post(
    "/auctions",
    response_model=ResponseModel[int],
    responses={
        201: {"description": "정상처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        },
    },
    status_code=status.HTTP_201_CREATED,
    summary="노래방 경매 생성",
    description="특정 시간대의 노래방 경매를 생성합니다.",
)
async def create_auction(request: AuctionCreate, auth_data: LoginDep):
    user, _ = auth_data

    if not user.has_permission(UserPermission.MANAGE_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. You do not have permission to manage karaoke auctions.",
        )

    async with client.session as session:
        auction = KaraokeAuction(
            target_date=request.target_date,
            period=request.period,
            start_time=request.start_time,
            end_time=request.end_time,
            min_bid=request.min_bid,
            status=AuctionStatus.SCHEDULED,
            current_highest_bid_amount=request.min_bid,
        )
        session.add(auction)
        await session.flush()

    return ResponseModel[int](success=True, data=auction.id)


@router.get(
    "/auctions",
    response_model=ResponseModel[list[KaraokeAuction]],
    responses={
        200: {"description": "정상처리"},
    },
    status_code=status.HTTP_200_OK,
    summary="노래방 경매 목록 조회",
)
async def get_auctions(target_date: dt_date):
    async with client.session as session:
        query = (
            select(KaraokeAuction)
            .where(KaraokeAuction.target_date == target_date)
            .order_by(col(KaraokeAuction.period).asc())
        )
        result = await session.execute(query)
        auctions = list(result.scalars().all())

    return ResponseModel[list[KaraokeAuction]](success=True, data=[a.model_dump() for a in auctions])


@router.post(
    "/auctions/{auction_id}/bid",
    response_model=ResponseModel[bool],
    responses={
        200: {"description": "정상처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        },
        409: {
            "model": ErrorResponse,
            "description": "서버가 처리중일 경우 발생합니다. 잠시 후 시도 바랍니다.",
        },
        404: {
            "model": ErrorResponse,
            "description": "해당하는 경매를 찾지 못할경우 발생합니다.",
        },
        400: {
            "model": ErrorResponse,
            "description": "포인트 부족 등으로 잘못된 포인트 값이 입력될 경우 발생합니다.",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="경매 입찰 및 환불 처리",
    description="포인트를 즉시 차감하여 입찰하고 상위 입찰자 발생시 기존 낙찰자 즉시 환불 처리합니다.",
)
async def place_bid(auction_id: int, request: BidRequest, auth_data: LoginDep):
    user, _ = auth_data

    if not user.has_permission(UserPermission.JOIN_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. You do not have permission to participate in karaoke auctions.",
        )

    lock_key = f"karaoke_bid_lock:{auction_id}"
    lock = client.redis.lock(lock_key, timeout=5.0)
    acquired = await lock.acquire(blocking_timeout=2.0)

    if not acquired:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Too many concurrent bids. Try again.")

    try:
        async with client.session as session:
            auction = await session.get(KaraokeAuction, auction_id)
            if not auction:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")

            # 스케줄러가 상태를 안바꿨을수도 있으므로 시간 체크 (또는 ACTIVE 상태 체크)
            now = datetime.now()
            if auction.start_time > now or auction.end_time < now:
                # 상태가 아직 SCHEDULED이거나 CLOSED일 상황 대비 실시간 체크
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not bidding time")

            if request.amount <= auction.current_highest_bid_amount or request.amount < auction.min_bid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bid amount must be higher than current highest bid and minimum bid",
                )

            current_user = await client.get_user(user.id, lock=True)
            if current_user is None or current_user.point < request.amount:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient points")

            # 기존 최고 입찰자 환불
            prev_bid_id = auction.current_highest_bid_id
            if prev_bid_id:
                prev_bid = await session.get(KaraokeBid, prev_bid_id)
                if prev_bid:
                    prev_bid.status = KaraokeBidStatus.OUTBID

                    prev_user = await client.get_user(prev_bid.user_id, lock=True)
                    if prev_user:
                        await prev_user.point_grant(
                            amount=prev_bid.amount, reason="노래방 예약 환불", type=PointHistoryType.karaoke_refund
                        )
                        # 환불 시점 웹소켓 이벤트 전송 (pubsub)
                        await client.redis.publish(
                            "karaoke_updates",
                            json.dumps(
                                {
                                    "type": "REFUND",
                                    "user_id": prev_user.id,
                                    "auction_id": auction.id,
                                    "amount": prev_bid.amount,
                                }
                            ),
                        )

            # 새 입찰자 차감
            await current_user.point_deduct(
                amount=request.amount, reason="노래방 예약", type=PointHistoryType.karaoke_bid
            )

            new_bid = KaraokeBid(auction_id=auction.id, user_id=current_user.id, amount=request.amount)
            session.add(new_bid)
            await session.flush()

            auction.current_highest_bid_id = new_bid.id
            auction.current_highest_bid_amount = new_bid.amount

            # 브로드캐스트 이벤트 전송 (새로운 최고가)
            await client.redis.publish(
                "karaoke_updates",
                json.dumps(
                    {
                        "type": "NEW_HIGHEST_BID",
                        "auction_id": auction.id,
                        "bid_amount": new_bid.amount,
                        "target_date": auction.target_date.isoformat(),
                        "period": auction.period,
                    }
                ),
            )

    finally:
        await lock.release()

    return ResponseModel[bool](success=True, data=True)


@router.delete(
    "/auctions/{auction_id}",
    response_model=ResponseModel[bool],
    responses={
        200: {"description": "정상처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한 없음",
        },
        404: {
            "model": ErrorResponse,
            "description": "예약 경매를 찾을 수 없을 경우 발생합니다.",
        },
        400: {
            "model": ErrorResponse,
            "description": "이미 종료된 경매를 종료하려 할경우 발생합니다.",
        },
        409: {
            "model": ErrorResponse,
            "description": "서버가 처리중일 경우 발생합니다. 잠시 후 시도 바랍니다.",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="노래방 경매 취소",
    description="경매를 취소하고, 만약 최고 입찰자가 있다면 포인트를 환불합니다.",
)
async def cancel_auction(auction_id: int, auth_data: LoginDep):
    user, _ = auth_data

    if not user.has_permission(UserPermission.MANAGE_KARAOKE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. You do not have permission to cancel karaoke auctions.",
        )

    lock_key = f"karaoke_bid_lock:{auction_id}"
    lock = client.redis.lock(lock_key, timeout=5.0)
    acquired = await lock.acquire(blocking_timeout=2.0)

    if not acquired:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="서버가 바쁩니다. 잠시 후 다시 시도해 주세요.")

    try:
        async with client.session as session:
            auction = await session.get(KaraokeAuction, auction_id)
            if not auction:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")

            if auction.status == AuctionStatus.CLOSED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="이미 종료된 옥션은 취소할 수 없습니다."
                )

            auction.status = AuctionStatus.CLOSED

            # 기존 최고 입찰자 환불
            prev_bid_id = auction.current_highest_bid_id
            if prev_bid_id:
                prev_bid = await session.get(KaraokeBid, prev_bid_id)
                if prev_bid and prev_bid.status == KaraokeBidStatus.ACTIVE:
                    prev_bid.status = KaraokeBidStatus.CANCELED

                    prev_user = await client.get_user(prev_bid.user_id, lock=True)
                    if prev_user:
                        await prev_user.point_grant(
                            amount=prev_bid.amount,
                            reason="노래방 경매 취소로 인한 환불",
                            type=PointHistoryType.karaoke_refund,
                        )
                        # 환불 시점 웹소켓 이벤트 전송
                        import json

                        await client.redis.publish(
                            "karaoke_updates",
                            json.dumps(
                                {
                                    "type": "REFUND_CANCEL",
                                    "user_id": prev_user.id,
                                    "auction_id": auction.id,
                                    "amount": prev_bid.amount,
                                }
                            ),
                        )

            # 브로드캐스트 이벤트 전송
            import json

            await client.redis.publish("karaoke_updates", json.dumps({"type": "CANCELED", "auction_id": auction.id}))

    finally:
        await lock.release()

    return ResponseModel[bool](success=True, data=True)


# 실시간 알림을 위한 WebSocket 엔드포인트
@router.websocket("/ws")
async def karaoke_websocket(websocket: WebSocket):
    await websocket.accept()
    pubsub = client.redis.pubsub()
    await pubsub.subscribe("karaoke_updates")

    async def reader_task():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await websocket.send_text(data)
        except Exception:
            pass

    task = asyncio.create_task(reader_task())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        await pubsub.unsubscribe("karaoke_updates")
