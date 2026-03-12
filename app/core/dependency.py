from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import settings
from app.core.database import get_async_session
from app.core.redis import redis
from app.schemas import Users


async def verify_session(
    request: Request,
    session: "SessionDep",
) -> tuple[Users, str]:
    """
    요청의 쿠키와 Redis를 확인하여 유효한 세션인지 검증합니다.
    성능 향상을 위해 유저 정보를 캐싱합니다.
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

    # 1. User Cache에서 유저 정보 조회
    user_cache_key = f"user:{user_id}"
    cached_user_data = await redis.get(user_cache_key)
    if cached_user_data:
        # Cache Hit: Pydantic 모델로 변환하여 반환
        user = Users.model_validate(cached_user_data)
        return user, session_id

    # 2. Cache Miss: DB에서 유저 정보 조회
    user: Users | None = await session.get(Users, user_id)
    if not user:
        # DB에도 유저가 없는 경우, 비정상적인 상태이므로 세션 삭제
        await redis.delete(f"session:{session_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # 3. DB 조회 결과를 User Cache에 저장 (세션 만료 시간과 동일하게 설정)
    await redis.set(user_cache_key, user.model_dump(), ttl=settings.service.session.expire_seconds)

    return user, session_id


LoginDep = Annotated[tuple[Users, str], Depends(verify_session)]
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]
