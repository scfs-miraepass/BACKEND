from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, select

from app.core import LoginDep, ServiceClient
from app.core.redis_keys import Keys
from app.schemas import User, UserPermission, Users, UserSearch, UserType
from app.schemas.response import ErrorResponse, ResponseModel

router = APIRouter(prefix="/search", tags=["search"])
client = ServiceClient()


async def _load_users(user_ids: list[int]) -> list[User]:
    """
    유저 ID 목록의 유저 데이터를 순서대로 가져옵니다.
    유저 캐시(`Keys.User.ITEM`)를 우선 사용하고, 캐시에 없는 유저만 DB에서 한 번에 조회한 뒤 캐싱합니다.
    """
    cached = await client.redis.mget([Keys.User.ITEM(user_id=user_id) for user_id in user_ids])
    users: dict[int, User] = {
        user_id: User.model_validate(data) for user_id, data in zip(user_ids, cached, strict=True) if data
    }

    missing = [user_id for user_id in user_ids if user_id not in users]
    if missing:
        async with client.session as session:
            result = await session.execute(select(Users).where(col(Users.id).in_(missing)))
            for row in result.scalars().all():
                await client.redis.set(Keys.User.ITEM(user_id=row.id), row.model_dump())
                users[row.id] = User.model_validate(row.model_dump())

    # 조회 사이에 삭제된 유저는 제외합니다.
    return [users[user_id] for user_id in user_ids if user_id in users]


@router.get(
    "",
    response_model=ResponseModel[list[User]],
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
    summary="유저 검색",
    description="유저를 이름 또는 ID(학번)으로 검색합니다.",
)
async def search(auth_data: LoginDep, q: str, t: list[UserType] | None = Query(None)):
    """
    사용자 검색 API

    - 입력값이 숫자로만 구성된 경우: 학번(ID)으로 검색 (4자리 이상인 경우만)
    - 입력값에 문자가 포함된 경우: 이름을 자모로 분리하여 검색

    Redis 캐싱을 적용하여 동일한 검색어에 대한 DB 부하를 줄입니다.
    검색 결과 캐시에는 유저 ID만 저장하므로, 포인트 등 유저 데이터가 바뀌어도 검색 캐시를 지울 필요가 없습니다.
    """
    user, _ = auth_data

    if not user.has_permission(UserPermission.SEARCH_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if t is None:
        t = []

    # 입력값 양끝 공백 제거
    q = q.strip()

    # 빈 검색어 처리
    if not q:
        return ResponseModel(success=True, data=[])

    decomposed_query = client.normalize_and_decompose(q)
    # 캐시 키 생성
    cache_key = Keys.Search.USERS(query=decomposed_query, types=",".join(t))

    # Redis 캐시 조회 (유저 ID 목록)
    cached_ids = await client.redis.get(cache_key)
    if cached_ids is not None:
        return ResponseModel(success=True, data=await _load_users(cached_ids))

    async with client.session as session:
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
            # UserSearch 테이블과 조인하여 검색
            # 학생 타입(UserType.student)인 유저만 필터링
            # like 검색을 통해 부분 일치(prefix) 검색 수행
            stmt = (
                select(Users)
                .join(UserSearch, cast(Any, Users.id == UserSearch.user_id))
                .where(col(UserSearch.value).like(f"%{decomposed_query}%"))
            )
            if t:
                stmt = stmt.where(col(Users.type).in_(t))

            result = await session.execute(stmt)
            # 중복 제거 (Users 객체 기준)
            users = result.scalars().unique().all()

    # 검색 결과(유저 ID 목록)를 Redis에 캐싱
    await client.redis.set(cache_key, [user.id for user in users])

    return ResponseModel(success=True, data=users)


@router.get(
    "/teacher/{user_name}",
    response_model=ResponseModel[User],
    responses={
        200: {"description": "정상 처리"},
        404: {
            "model": ErrorResponse,
            "description": "유저를 찾을 수 없음",
        },
    },
    status_code=status.HTTP_200_OK,
    summary="교사 데이터",
    description="교사의 정확한 이름을 가지고 교사의 데이터를 가져옵니다.",
)
async def teacher_get_by_name(user_name: str):
    async with client.session as session:
        stmt = select(Users).where(Users.name == user_name, Users.type == UserType.teacher)
        result = await session.execute(stmt)
        teacher = result.scalar_one_or_none()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found.",
        )

    return ResponseModel(success=True, data=teacher)
