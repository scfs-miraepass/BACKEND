"""
로그인 세션 관리

세션은 `Keys.Auth.SESSION`(세션 ID → 유저 ID)에 저장하고,
유저별 세션 ID 목록을 `Keys.Auth.USER_SESSIONS`(Set)에 함께 기록해 한 유저의 모든 세션을 종료할 수 있도록 합니다.
"""

from uuid import uuid4

from .config import settings
from .loggers import LoggerCore
from .redis import RedisCore
from .redis_keys import Keys


async def create_session(user_id: int) -> str:
    """
    새로운 로그인 세션을 생성합니다.

    Returns:
        str: 생성된 세션 ID
    """
    session_id = str(uuid4())
    await RedisCore.set(Keys.Auth.SESSION(session_id=session_id), user_id)
    await RedisCore.sadd(Keys.Auth.USER_SESSIONS(user_id=user_id), session_id)
    return session_id


async def get_session_user_id(session_id: str) -> int | None:
    return await RedisCore.get(Keys.Auth.SESSION(session_id=session_id))


async def track_session(user_id: int, session_id: str):
    """
    세션을 유저의 세션 목록에 기록합니다. (이미 기록된 경우 목록의 TTL만 갱신)
    세션 목록 기능이 추가되기 전에 생성된 세션도 목록에 포함시키기 위해 사용합니다.
    """
    await RedisCore.sadd(Keys.Auth.USER_SESSIONS(user_id=user_id), session_id)


async def extend_session(user_id: int, session_id: str):
    """세션과 유저 캐시, 세션 목록의 만료 시간을 연장합니다."""
    expire = settings.service.session.expire_seconds
    async with RedisCore().pipeline() as pipe:
        pipe.expire(Keys.Auth.SESSION(session_id=session_id), expire)
        pipe.expire(Keys.User.ITEM(user_id=user_id), expire)
        pipe.expire(Keys.Auth.USER_SESSIONS(user_id=user_id), expire)
        await pipe.execute()


async def delete_session(session_id: str, user_id: int | None = None):
    """
    세션을 삭제합니다.

    Args:
        session_id: 삭제할 세션 ID
        user_id: 세션의 유저 ID. 알고 있는 경우 유저의 세션 목록에서도 제거합니다.
    """
    await RedisCore.delete(Keys.Auth.SESSION(session_id=session_id))
    if user_id is not None:
        await RedisCore.srem(Keys.Auth.USER_SESSIONS(user_id=user_id), session_id)


async def revoke_user_sessions(user_id: int) -> int:
    """
    유저의 모든 로그인 세션을 종료합니다. (비밀번호 변경/초기화, 유저 삭제 시 사용)

    Returns:
        int: 종료한 세션 개수
    """
    index_key = Keys.Auth.USER_SESSIONS(user_id=user_id)
    session_ids = await RedisCore.smembers(index_key)
    await RedisCore.delete(index_key, *(Keys.Auth.SESSION(session_id=session_id) for session_id in session_ids))
    LoggerCore.service.info(f"유저 {user_id}의 로그인 세션 {len(session_ids)}개를 종료했습니다.")
    return len(session_ids)
