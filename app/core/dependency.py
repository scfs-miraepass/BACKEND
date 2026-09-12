from typing import Annotated

from fastapi import Depends, HTTPException, status
from starlette.requests import HTTPConnection

from .client import ServiceClient
from .config import settings
from .service import User


async def verify_session(conn: HTTPConnection) -> tuple[User, str]:
    client = ServiceClient()
    session_id = conn.cookies.get(settings.service.session.cookie_name)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = await client.redis.get(f"session:{session_id}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    user = await client.get_user(user_id, cache=True)
    if not user:
        await client.redis.delete(f"session:{session_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user, session_id


LoginDep = Annotated[tuple[User, str], Depends(verify_session)]
