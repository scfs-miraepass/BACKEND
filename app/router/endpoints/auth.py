from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core import LoginDep, SessionDep, settings
from app.core.redis import redis
from app.core.security import get_password_hash, verify_password
from app.schemas.response import ErrorResponse, ResponseModel
from app.schemas.users import User, Users

router = APIRouter(prefix="/auth", tags=["users", "auth"])


class LoginForm(BaseModel):
    id: int
    password: str


class ChangePasswordForm(BaseModel):
    old_password: str
    new_password: str


def _set_session_cookie(response: Response, session_id: str):
    """응답에 세션 쿠키를 설정합니다."""
    response.set_cookie(
        key=settings.service.session.cookie_name,
        value=session_id,
        httponly=True,  # JavaScript에서 접근 불가 (보안)
        secure=not settings.debug,  # 개발 환경(Debug)에서는 False, 배포 시 True (HTTPS 필요)
        samesite="lax",  # CSRF 보호
        max_age=settings.service.session.expire_seconds,
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
    session: SessionDep,
):
    # 1. 유저 조회
    user: Users | None = await session.get(Users, form.id)

    # 2. 유저 검증 (비밀번호 비교)
    if not user or not user.password or not verify_password(form.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # 3. 세션 생성
    session_id = str(uuid4())

    # Redis에 세션 저장 (Key: session:{uuid}, Value: user_id)
    # TTL 설정
    await redis.set(f"session:{session_id}", user.id, ttl=settings.service.session.expire_seconds)

    # 4. 유저 정보 캐싱 (Cache Warming)
    # 로그인 시점에 미리 캐시에 올려두어 이후 요청 시 DB 접근을 줄임
    await redis.set(f"user:{user.id}", user.model_dump(), ttl=settings.service.session.expire_seconds)

    # 5. 쿠키 설정
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
        user_id = await redis.get(f"session:{session_id}")
        # Redis에서 세션 삭제
        await redis.delete(f"session:{session_id}")
        if user_id:
            # 유저 정보 캐시도 함께 삭제 (선택 사항이지만 보안상 권장)
            await redis.delete(f"user:{user_id}")

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

    # 4. 세션 연장 (Sliding Session)
    # Redis TTL 갱신
    await redis.expire(f"session:{session_id}", settings.service.session.expire_seconds)
    # 유저 정보 캐시 TTL도 함께 갱신
    await redis.expire(f"user:{user.id}", settings.service.session.expire_seconds)

    # 쿠키 갱신 (만료 시간 초기화)
    _set_session_cookie(response, session_id)

    return ResponseModel[User](success=True, data=user)


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
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="비밀번호 변경",
    description="로그인된 유저의 비밀번호를 변경합니다.",
)
async def change_password(form: ChangePasswordForm, auth_data: LoginDep, session: SessionDep):
    user, session_id = auth_data

    # 기존 비밀번호 확인. 비밀번호가 없을경우는 PASS
    if (user.password is not None) and (not verify_password(form.old_password, user.password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )

    # 새 비밀번호 해싱 및 저장
    user.password = get_password_hash(form.new_password)
    session.add(user)
    await session.commit()

    # 캐시 및 세션 삭제 (비밀번호 변경 시 모든 기기 로그아웃 유도)
    # 참고: 모든 세션을 추적하는 별도의 Set이 없다면 현재 세션과 유저 캐시를 우선 삭제합니다.
    await redis.delete(f"user:{user.id}")
    await redis.delete(f"session:{session_id}")


@router.get(
    "/password/exists/{user_id}",
    response_model=ResponseModel[bool],
    responses={
        404: {
            "model": ErrorResponse,
            "description": "유저를 찾을 수 없음",
        },
    },
    summary="비밀번호 존재 여부 확인",
    description="특정 ID의 유저가 비밀번호를 가지고 있는지(None이 아닌지) 여부를 확인합니다.",
)
async def check_password_exists(user_id: int, session: SessionDep):
    """특정 ID의 유저가 비밀번호를 가지고 있는지(None이 아닌지) 여부를 확인합니다."""
    user: Users | None = await session.get(Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return ResponseModel[bool](success=True, data=user.password is not None)
