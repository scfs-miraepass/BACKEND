from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.core.database import get_async_session
from app.core.redis import redis
from app.schemas.users import Users, User
from app.schemas.response import ResponseModel, ErrorResponse
from app.core import settings

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE_NAME = "session_id"
SESSION_EXPIRE_SECONDS = 3600 * 24 * 7  # 7 days


class LoginForm(BaseModel):
    id: int
    password: str


def _get_redis_key(session_id: str) -> str:
    """Redis에 저장될 세션 키를 생성합니다."""
    return f"session:{session_id}"


def _set_session_cookie(response: Response, session_id: str):
    """응답에 세션 쿠키를 설정합니다."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,  # JavaScript에서 접근 불가 (보안)
        secure=not settings.debug,  # 개발 환경(Debug)에서는 False, 배포 시 True (HTTPS 필요)
        samesite="lax",  # CSRF 보호
        max_age=SESSION_EXPIRE_SECONDS,
    )


async def verify_session(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> tuple[Users, str]:
    """
    요청의 쿠키와 Redis를 확인하여 유효한 세션인지 검증합니다.
    유효하다면 (User 객체, session_id)를 반환합니다.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = await redis.get(_get_redis_key(session_id))
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    user = await session.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user, session_id


@router.post(
    "/login",
    response_model=ResponseModel[User],
    responses={
        200: {"description": "정상적으로 로그인이 되었음"},
        401: {
            "model": ErrorResponse,
            "description": "ID 또는 비밀번호가 일치하지 않습니다.",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="로그인",
    description="ID와 비밀번호를 통해 로그인을 진행합니다. 로그인을 성공한 경우 해당 유저의 정보를 응답합니다.",
)
async def login(
    response: Response,
    form: LoginForm,
    session: AsyncSession = Depends(get_async_session),
):
    # 1. 유저 조회
    user = await session.get(Users, form.id)

    # 2. 유저 검증 (비밀번호 비교)
    if not user or user.password != form.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # 3. 세션 생성
    session_id = str(uuid4())

    # Redis에 세션 저장 (Key: session:{uuid}, Value: user_id)
    # TTL 설정
    await redis.set(_get_redis_key(session_id), user.id, ttl=SESSION_EXPIRE_SECONDS)

    # 4. 쿠키 설정
    _set_session_cookie(response, session_id)

    return ResponseModel[User](success=True, data=user)


@router.post(
    "/logout",
    responses={204: {"description": "정상적으로 로그아웃이 되었음"}},
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
    description="현재 로그인된 세션을 종료합니다.",
)
async def logout(response: Response, request: Request):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        # Redis에서 세션 삭제
        await redis.delete(_get_redis_key(session_id))

    # 쿠키 삭제
    response.delete_cookie(SESSION_COOKIE_NAME)


@router.get(
    "",
    response_model=ResponseModel[User],
    responses={
        200: {"description": "세션이 정상적으로 유효함"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음.",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="인증",
    description="현재 로그인된 유저의 정보를 반환합니다.",
)
async def get_current_user(
    response: Response,
    auth_data: tuple[Users, str] = Depends(verify_session),
):
    user, session_id = auth_data

    # 4. 세션 연장 (Sliding Session)
    # Redis TTL 갱신
    await redis.expire(_get_redis_key(session_id), SESSION_EXPIRE_SECONDS)

    # 쿠키 갱신 (만료 시간 초기화)
    _set_session_cookie(response, session_id)

    return ResponseModel[User](success=True, data=user)
