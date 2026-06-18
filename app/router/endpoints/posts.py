from math import ceil
from typing import List

from fastapi import APIRouter, status, HTTPException, Response, Query
from pydantic import BaseModel, Field
from sqlmodel import select, func

from app.core import SessionDep, LoginDep
from app.core.redis import redis
from app.schemas.post import Posts, PostContent
from app.schemas.response import ResponseModel, ErrorResponse

router = APIRouter(prefix="/posts", tags=["posts"])


class PostCreateRequest(BaseModel):
    title: str = Field(..., description="게시글 제목")
    content_data: dict = Field(..., description="게시글의 본문 데이터")


class PostUpdateRequest(BaseModel):
    title: str | None = Field(None, description="수정할 게시글 제목")
    content_data: dict | None = Field(None, description="수정할 게시글의 본문 데이터")


@router.get(
    "",
    response_model=ResponseModel[List[Posts]],
    responses={
        200: {"description": "게시글 목록 조회 성공"},
        401: {"model": ErrorResponse, "description": "인증되지 않은 사용자"},
    },
    status_code=status.HTTP_200_OK,
    summary="게시글 목록 조회",
    description="전체 게시글 목록을 페이징하여 조회합니다.",
)
async def get_posts(
    response: Response,
    auth_data: LoginDep,
    session: SessionDep,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(
        20, ge=1, le=100, description="페이지 당 게시글 데이터 갯수 (최대 100)"
    ),
):
    # 1. 총 게시글 수 조회 (캐싱 적용)
    count_cache_key = "posts_count"
    cached_count = await redis.get(count_cache_key)

    if cached_count is not None:
        total_count = int(cached_count)
    else:
        count_query = select(func.count()).select_from(Posts)
        total_count = (await session.execute(count_query)).scalar_one()
        # 캐시 저장 (TTL: 1일)
        await redis.set(count_cache_key, total_count, ttl=60 * 60 * 24)

    # 최대 페이지 계산 (데이터가 없으면 1페이지)
    max_page = ceil(total_count / size) if total_count > 0 else 1

    response.headers["X-MAX-PAGE"] = str(max_page)

    # 2. 목록 데이터 조회 (캐싱 적용)
    list_cache_key = f"posts:list:{page}:{size}"
    cached_list = await redis.get(list_cache_key)

    if cached_list is not None:
        posts = [Posts(**item) for item in cached_list]
        response.headers["X-CACHED"] = "true"
    else:
        response.headers["X-CACHED"] = "false"
        offset = (page - 1) * size
        query = select(Posts).order_by(Posts.id.desc()).offset(offset).limit(size)

        result = await session.execute(query)
        posts = list(result.scalars().all())
        posts_data = [item.model_dump() for item in posts]
        await redis.set(list_cache_key, posts_data, ttl=60 * 60 * 24)

    return ResponseModel[List[Posts]](success=True, data=posts)


@router.get(
    "/{post_id}",
    response_model=ResponseModel[Posts],
    responses={
        200: {"description": "게시글 상세 조회 성공"},
        401: {"model": ErrorResponse, "description": "인증되지 않은 사용자"},
        404: {"model": ErrorResponse, "description": "게시글을 찾을 수 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="게시글 단일 조회",
    description="특정 ID의 게시글 상세 정보를 조회합니다.",
)
async def get_post(
    post_id: int,
    auth_data: LoginDep,
    session: SessionDep,
):
    # 게시글 단일 조회 (캐싱 적용)
    cache_key = f"post:{post_id}"
    cached_post = await redis.get(cache_key)

    if cached_post is not None:
        return ResponseModel[Posts](success=True, data=Posts(**cached_post))

    result = await session.execute(select(Posts).where(Posts.id == post_id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    # 캐시 저장 (TTL: 1일)
    await redis.set(cache_key, post.model_dump(), ttl=60 * 60 * 24)

    return ResponseModel[Posts](success=True, data=post)


@router.post(
    "",
    response_model=ResponseModel[Posts],
    responses={
        201: {"description": "게시글 작성 완료"},
        401: {"model": ErrorResponse, "description": "인증되지 않은 사용자"},
        403: {"model": ErrorResponse, "description": "권한이 없음"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="게시글 작성",
    description="새로운 게시글을 작성합니다.",
)
async def create_post(
    request: PostCreateRequest,
    auth_data: LoginDep,
    session: SessionDep,
):
    user, _ = auth_data

    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # 관계형 데이터(PostContent)를 객체 생성 시 직접 할당합니다.
    new_post = Posts(title=request.title, author_id=user.id)
    new_post.content = PostContent(data=request.content_data)

    session.add(new_post)
    await session.commit()
    await session.refresh(new_post)

    # 데이터 변경 시 목록 관련 캐시 무효화
    await redis.delete("posts_count")
    await redis.delete_pattern("posts:list:*")

    return ResponseModel[Posts](success=True, data=new_post)


@router.patch(
    "/{post_id}",
    response_model=ResponseModel[Posts],
    responses={
        200: {"description": "게시글 수정 완료"},
        401: {"model": ErrorResponse, "description": "인증되지 않은 사용자"},
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        404: {"model": ErrorResponse, "description": "게시글을 찾을 수 없음"},
    },
    status_code=status.HTTP_200_OK,
    summary="게시글 수정",
    description="기존 게시글을 수정합니다.",
)
async def update_post(
    post_id: int,
    request: PostUpdateRequest,
    auth_data: LoginDep,
    session: SessionDep,
):
    user, _ = auth_data

    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # 게시글 조회
    result = await session.execute(select(Posts).where(Posts.id == post_id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    # 데이터 업데이트
    if request.title is not None:
        post.title = request.title

    if request.content_data is not None:
        if post.content:
            post.content.data = request.content_data
        else:
            post.content = PostContent(data=request.content_data)

    session.add(post)
    await session.commit()
    await session.refresh(post)

    # 데이터 변경 시 관련된 캐시 무효화
    await redis.delete(f"post:{post_id}")
    await redis.delete_pattern("posts:list:*")

    return ResponseModel[Posts](success=True, data=post)


@router.delete(
    "/{post_id}",
    responses={
        204: {"description": "게시글 삭제 완료"},
        401: {"model": ErrorResponse, "description": "인증되지 않은 사용자"},
        403: {"model": ErrorResponse, "description": "권한이 없음"},
        404: {"model": ErrorResponse, "description": "게시글을 찾을 수 없음"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 삭제",
    description="기존 게시글을 삭제합니다.",
)
async def delete_post(
    post_id: int,
    auth_data: LoginDep,
    session: SessionDep,
):
    user, _ = auth_data

    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # 게시글 조회
    result = await session.execute(select(Posts).where(Posts.id == post_id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    # 데이터 삭제
    await session.delete(post)
    await session.commit()

    # 데이터 변경 시 관련된 캐시 무효화
    await redis.delete(f"post:{post_id}")
    await redis.delete("posts_count")
    await redis.delete_pattern("posts:list:*")
