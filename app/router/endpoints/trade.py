from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select, col

from app.schemas import PointHistoryType, Trades, TradeStatus
from app.schemas.response import ErrorResponse, ResponseModel
from app.core import ServiceClient, LoginDep

router = APIRouter(
    prefix="/trade",
    tags=["trade"],
)
client = ServiceClient()
CACHE_KEY_LIST_ALL = "CACHE_KEY_LIST_ALL"


class RequestBody(BaseModel):
    buyer_id: int
    amount: int
    reason: str


@router.get(
    "/list",
    responses={
        200: {"description": "정상 처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    response_model=ResponseModel[list[Trades]],
    summary="전체 거래 목록",
    description="모든 유저의 거래 목록을 가져옵니다.",
)
async def list_all_trades(auth_data: LoginDep):
    user, _ = auth_data
    if user.type != user.type.service:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        query = select(Trades).order_by(col(Trades.id).desc())
        result = await session.execute(query)
        trades = result.scalars().all()

    json_data = [item.model_dump() for item in trades]
    await client.redis.set(CACHE_KEY_LIST_ALL, json_data, ttl=60 * 60 * 24)  # 하루 캐싱

    return ResponseModel[list[Trades]](success=True, data=trades)


@router.post(
    "/{trade_id}/approval",
    responses={
        204: {"description": "정상 처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
        404: {
            "model": ErrorResponse,
            "description": "거래를 찾을 수 없음",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="거래 승인",
    description="거래를 승인합니다.",
)
async def approval(trade_id: int, auth_data: LoginDep):
    user, _ = auth_data
    if user.type != user.type.service:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        trade = await session.get(Trades, trade_id)
        if trade is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found.")

        trade.status = TradeStatus.approval
        seller = await client.get_user(trade.seller_id, cache=True)
        buyer = await client.get_user(trade.buyer_id, cache=True)

        if seller is None or buyer is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="WTF")

        await seller.point_grant(
            amount=trade.amount,
            reason=f"'{buyer.name}' 거래",
            type=PointHistoryType.trade,
        )
    await client.redis.delete(CACHE_KEY_LIST_ALL)
    client.logs.service.info(
        f"{seller.id}({seller.name})와 {buyer.id}({buyer.name})의 거래가 승인 되었습니다. (id {trade.id})"
    )


@router.post(
    "/{trade_id}/refusal",
    responses={
        204: {"description": "정상 처리"},
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
        404: {
            "model": ErrorResponse,
            "description": "거래를 찾을 수 없음",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="거래 거부",
    description="거래를 거부합니다.",
)
async def refusal(trade_id: int, auth_data: LoginDep):
    user, _ = auth_data
    if user.type != user.type.service:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    async with client.session as session:
        trade = await session.get(Trades, trade_id)
        if trade is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found.")

        trade.status = TradeStatus.refusal
        seller = await client.get_user(trade.seller_id, cache=True)
        buyer = await client.get_user(trade.buyer_id, cache=True)

        if seller is None or buyer is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="WTF")

        await buyer.point_grant(
            amount=trade.amount,
            reason=f"'{seller.name}' 거래 거부",
            type=PointHistoryType.trade,
        )
    await client.redis.delete(CACHE_KEY_LIST_ALL)
    client.logs.service.info(
        f"{seller.id}({seller.name})와 {buyer.id}({buyer.name})의 거래가 거부 되었습니다. (id {trade.id})"
    )


@router.post(
    "/request",
    responses={
        204: {"description": "정상 처리"},
        404: {
            "model": ErrorResponse,
            "description": "거래 하려는 유저를 찾지 못할 경우 발생합니다.",
        },
        400: {
            "model": ErrorResponse,
            "description": "포인트 부족",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="거래 신청",
    description="거래를 신청합니다.",
)
async def request(item: RequestBody, auth_data: LoginDep):
    user, _ = auth_data

    async with client.session as session:
        buyer_user = await client.get_user(item.buyer_id, cache=True)
        if buyer_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer user not found")

        try:
            await buyer_user.point_deduct(
                amount=item.amount,
                reason=f"'{user.name}' 거래",
                type=PointHistoryType.trade,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient point balance.",
            )

        session.add(
            Trades(
                seller_id=user.id,
                buyer_id=buyer_user.id,
                amount=item.amount,
                reason=item.reason,
            )
        )
        await client.redis.delete(CACHE_KEY_LIST_ALL)
        client.logs.service.info(
            f"{user.id}({user.name})가 {buyer_user.id}({buyer_user.name})과 거래를 신청했습니다. ({item.amount}. {item.reason[:10] + '...' if len(item.reason) > 10 else item.reason})"
        )


@router.get(
    "",
    responses={200: {"description": "정상 처리"}},
    response_model=ResponseModel[list[Trades]],
    status_code=status.HTTP_200_OK,
    summary="거래 목록",
    description="자기자신의 거래 목록을 가져옵니다.",
)
async def list_trade(auth_data: LoginDep):
    user, _ = auth_data

    async with client.session as session:
        query = (
            select(Trades)
            .where((Trades.seller_id == user.id) | (Trades.buyer_id == user.id))
            .order_by(col(Trades.id).desc())
        )
        result = await session.execute(query)
        trades = result.scalars().all()
    return ResponseModel[list[Trades]](success=True, data=trades)
