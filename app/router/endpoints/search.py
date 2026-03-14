from functools import lru_cache
from typing import List, cast, Any

from fastapi import APIRouter, status, HTTPException
from hangulpy import split_hangul_string
from sqlmodel import select, col

from app.core import SessionDep, LoginDep
from app.core.redis import redis
from app.schemas import User, Users, UserSearch, UserType
from app.schemas.response import ResponseModel, ErrorResponse

router = APIRouter(prefix="/search", tags=["search"])


@lru_cache(maxsize=128)
def normalize_and_decompose(query: str) -> str:
    """
    검색어의 공백을 제거하고 한글 자모를 분리합니다.
    동일한 검색어에 대한 중복 연산을 방지하기 위해 캐싱을 사용합니다.
    """
    return "".join(split_hangul_string(query.replace(" ", "")))


@router.get(
    "/student",
    response_model=ResponseModel[List[User]],
    responses={
        200: {"description": "정상 처리"},
        401: {
            "model": ErrorResponse,
            "description": "세션이 만료되었거나 유효하지 않음",
        },
        403: {
            "model": ErrorResponse,
            "description": "권한이 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="학생 검색",
    description="학생 유저를 이름 또는 ID(학번)으로 검색합니다.",
)
async def search_student(session: SessionDep, auth_data: LoginDep, q: str):
    """
    사용자 검색 API

    - 입력값이 숫자로만 구성된 경우: 학번(ID)으로 검색 (4자리 이상인 경우만)
    - 입력값에 문자가 포함된 경우: 이름을 자모로 분리하여 검색

    Redis 캐싱을 적용하여 동일한 검색어에 대한 DB 부하를 줄입니다.
    """
    user, _ = auth_data

    # 권한 확인: Teacher, Service only
    if user.type != UserType.teacher and user.type != UserType.service:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # 입력값 양끝 공백 제거
    q = q.strip()

    # 빈 검색어 처리
    if not q:
        return ResponseModel(success=True, data=[])

    # 캐시 키 생성
    cache_key = f"search_users:{q}"

    # Redis 캐시 조회
    cached_data = await redis.get(cache_key)
    if cached_data is not None:
        # 캐시된 데이터 반환 (JSON -> Dict List -> Pydantic Model List)
        # cached_data는 이미 dict 형태의 리스트
        return ResponseModel(success=True, data=cached_data)

    # 1. 숫자만 있는 경우: ID(학번) 검색
    if q.isdigit():
        # 학번은 총 4자이므로 4자 미만일 경우 빈 결과 반환
        if len(q) < 4:
            return ResponseModel(success=True, data=[])

        # ID로 정확히 일치하는 사용자 검색
        stmt = select(Users).where(Users.id == int(q))
        result = await session.execute(stmt)
        users = result.scalars().all()

    # 2. 문자가 포함된 경우: 이름 검색 (한글 자모 분리)
    else:
        # 캐시된 자모 분리 함수 사용
        decomposed_query = normalize_and_decompose(q)

        # UserSearch 테이블과 조인하여 검색
        # 학생 타입(UserType.student)인 유저만 필터링
        # like 검색을 통해 부분 일치(prefix) 검색 수행
        stmt = (
            select(Users)
            .join(UserSearch, cast(Any, Users.id == UserSearch.user_id))
            .where(Users.type == UserType.student)
            .where(col(UserSearch.value).like(f"%{decomposed_query}%"))
        )

        result = await session.execute(stmt)
        # 중복 제거 (Users 객체 기준)
        users = result.scalars().unique().all()

    # DB 조회 결과를 Redis에 캐싱 (TTL: 300초 = 5분)
    # Users 객체 리스트를 dict 리스트로 변환하여 저장
    users_data = [user.model_dump() for user in users]
    await redis.set(cache_key, users_data, ttl=300)

    return ResponseModel(success=True, data=users)
