from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.core.database import get_async_session
from app.core.redis import redis
from app.schemas.users import Users
from app.core import settings


async def verify_session(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> tuple[Users, str]:
    """
    요청의 쿠키와 Redis를 확인하여 유효한 세션인지 검증합니다.
    유효하다면 (User 객체, session_id)를 반환합니다.
    """
    session_id = request.cookies.get(settings.service.session.cookie_name)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = await redis.get(f"session:{session_id}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    user = await session.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user, session_id


LoginDep = Annotated[tuple[Users, str], Depends(verify_session)]
