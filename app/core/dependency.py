from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.schemas import Users
from .core import ServiceClient


async def verify_session(request: Request) -> tuple[Users, str]:
    client = ServiceClient()
    session_id = request.cookies.get(settings.service.session.cookie_name)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = await client.redis.get(f"session:{session_id}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    user_cache_key = f"user:{user_id}"
    cached_user_data = await client.redis.get(user_cache_key)
    if cached_user_data:
        user = Users.model_validate(cached_user_data)
        return user, session_id

    user = await client.get_user(user_id)
    if not user:
        await client.redis.delete(f"session:{session_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    await client.redis.set(user_cache_key, user.model_dump(), ttl=settings.service.session.expire_seconds)

    return user, session_id


LoginDep = Annotated[tuple[Users, str], Depends(verify_session)]
