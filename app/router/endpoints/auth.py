from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core import LoginDep, settings, ServiceClient
from app.core.security import verify_password
from app.schemas import UserType
from app.schemas.response import ErrorResponse, ResponseModel
from app.schemas.users import User

router = APIRouter(prefix="/auth", tags=["users", "auth"])
client = ServiceClient()


class LoginForm(BaseModel):
    id: int
    password: str


class ChangePasswordForm(BaseModel):
    old_password: str
    new_password: str


class ChangePasswordNewForm(BaseModel):
    user: int
    password: str


def _set_session_cookie(response: Response, session_id: str):
    """응답에 세션 쿠키를 설정합니다."""
    response.set_cookie(
        key=settings.service.session.cookie_name,
        value=session_id,
        httponly=True,  # JavaScript에서 접근 불가 (보안)
        secure=not settings.debug,  # 개발 환경(Debug)에서는 False, 배포 시 True (HTTPS 필요)
        samesite="lax",  # CSRF 보호
        max_age=settings.service.session.expire_seconds,
        path="/",
    )


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
):
    user = await client.get_user(form.id, cache=True)

    if not user or not user.password or not verify_password(form.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    session_id = str(uuid4())
    await client.redis.set(f"session:{session_id}", user.id, ttl=settings.service.session.expire_seconds)
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
    session_id = request.cookies.get(settings.service.session.cookie_name)
    if session_id:
        user_id = await client.redis.get(f"session:{session_id}")
        # Redis에서 세션 삭제
        await client.redis.delete(f"session:{session_id}")
        if user_id:
            # 유저 정보 캐시도 함께 삭제 (선택 사항이지만 보안상 권장)
            await client.redis.delete(f"user:{user_id}")

    # 쿠키 삭제
    response.delete_cookie(settings.service.session.cookie_name)


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
    auth_data: LoginDep,
):
    user, session_id = auth_data

    # 1. 현재 세션의 남은 TTL(수명) 확인
    current_ttl = await client.redis.ttl(f"session:{session_id}")

    # 2. 남은 시간이 설정된 만료 시간의 50% 미만일 때만 연장 (조건부 갱신)
    # (current_ttl이 정상적인 양수일 때만 동작하도록 예외 처리 포함)
    if 0 <= current_ttl < (settings.service.session.expire_seconds * 0.5):
        # 3. Redis 파이프라인을 사용하여 네트워크 왕복(RTT) 최소화
        async with client.redis.pipeline() as pipe:
            pipe.expire(f"session:{session_id}", settings.service.session.expire_seconds)
            pipe.expire(f"user:{user.id}", settings.service.session.expire_seconds)
            await pipe.execute()

        # 쿠키 갱신 (만료 시간 초기화)
        _set_session_cookie(response, session_id)

    return ResponseModel[User](success=True, data=user)


@router.post(
    "/password",
    responses={
        204: {"description": "비밀번호 변경 성공"},
        404: {
            "model": ErrorResponse,
            "description": "유저을 찾을 수 없음",
        },
        400: {
            "model": ErrorResponse,
            "description": "이미 비밀번호가 설정되어있음.",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="비밀번호 초기 변경",
    description="첫 로그인시 비밀번호 변경을 합니다.",
)
async def change_password_new(form: ChangePasswordNewForm):
    user = await client.get_user(form.user, cache=True, save_cache=False)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.password is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password already set",
        )
    await user.update_password(form.password)


@router.put(
    "/password",
    responses={
        204: {"description": "비밀번호 변경 성공"},
        400: {
            "model": ErrorResponse,
            "description": "기존 비밀번호가 일치하지 않음",
        },
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음.",
        },
        404: {
            "model": ErrorResponse,
            "description": "초기회 되지 않은 유저.",
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="비밀번호 변경",
    description="로그인된 유저의 비밀번호를 변경합니다.",
)
async def change_password(form: ChangePasswordForm, auth_data: LoginDep):
    user, session_id = auth_data
    if user.password is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have a password",
        )

    # 기존 비밀번호 확인. 비밀번호가 없을경우는 PASS
    if not verify_password(form.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )

    # 새 비밀번호 해싱 및 저장
    await user.update_password(form.new_password)

    await client.redis.delete(f"session:{session_id}")


@router.get(
    "/password/exists/{user_id}",
    response_model=ResponseModel[bool],
    responses={
        200: {"description": "정상 조회"},
        404: {
            "model": ErrorResponse,
            "description": "유저를 찾을 수 없음",
        },
        400: {
            "model": ErrorResponse,
            "description": "해당 유저의 타입이 지정된 타입과 일치하지 않음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="비밀번호 존재 여부 확인",
    description="특정 ID의 유저가 비밀번호를 가지고 있는지(None이 아닌지) 여부를 확인합니다.",
)
async def check_password_exists(user_id: int, t: UserType | None = None):
    """특정 ID의 유저가 비밀번호를 가지고 있는지(None이 아닌지) 여부를 확인합니다. 로그인시 유저가 있는지 확인할때 사용합니다."""
    user = await client.get_user(user_id, cache=True)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if t is not None and user.type != t:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User type does not match",
        )
    return ResponseModel[bool](success=True, data=user.password is not None)
