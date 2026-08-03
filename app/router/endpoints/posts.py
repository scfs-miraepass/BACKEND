from math import ceil
from typing import List

from fastapi import APIRouter, status, HTTPException, Response, Query
from pydantic import BaseModel, Field
from sqlmodel import select, func

from app.core import LoginDep, ServiceClient
from app.schemas import Posts, UserPermission
from app.schemas.response import ResponseModel, ErrorResponse

router = APIRouter(prefix="/posts", tags=["posts"])
client = ServiceClient()


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
        403: {"model": ErrorResponse, "description": "권한이 없음"}
    },
    status_code=status.HTTP_200_OK,
    summary="게시글 목록 조회",
    description="전체 게시글 목록을 페이징하여 조회합니다.",
)
async def get_posts(
    response: Response,
    auth: LoginDep,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 당 게시글 데이터 갯수 (최대 100)"),
):
    user, _ = auth

    if not user.has_permission(UserPermission.VIEW_POST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    # 1. 총 게시글 수 조회 (캐싱 적용)
    count_cache_key = "posts_count"
    cached_count = await client.redis.get(count_cache_key)

    async with client.session as session:
        if cached_count is not None:
            total_count = int(cached_count)
        else:
            count_query = select(func.count()).select_from(Posts)
            total_count = (await session.execute(count_query)).scalar_one()
            # 캐시 저장 (TTL: 1일)
            await client.redis.set(count_cache_key, total_count, ttl=60 * 60 * 24)

        # 최대 페이지 계산 (데이터가 없으면 1페이지)
        max_page = ceil(total_count / size) if total_count > 0 else 1

        response.headers["X-MAX-PAGE"] = str(max_page)

        # 2. 목록 데이터 조회 (캐싱 적용)
        list_cache_key = f"posts:list:{page}:{size}"
        cached_list = await client.redis.get(list_cache_key)

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
            await client.redis.set(list_cache_key, posts_data, ttl=60 * 60 * 24)

    return ResponseModel[List[Posts]](success=True, data=posts)


@router.get(
    "/{post_id}",
    response_model=ResponseModel[Posts],
    responses={
        200: {"description": "게시글 상세 조회 성공"},
        401: {"model": ErrorResponse, "description": "인증되지 않은 사용자"},
        404: {"model": ErrorResponse, "description": "게시글을 찾을 수 없음"},
        403: {"model": ErrorResponse, "description": "권한이 없음"}
    },
    status_code=status.HTTP_200_OK,
    summary="게시글 단일 조회",
    description="특정 ID의 게시글 상세 정보를 조회합니다.",
)
async def get_post(
    post_id: int,
    auth: LoginDep
):
    user, _ = auth

    if not user.has_permission(UserPermission.VIEW_POST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )


    post = await client.get_post(post_id, cache=True)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

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
async def create_post(request: PostCreateRequest, auth_data: LoginDep):
    user, _ = auth_data

    if not user.has_permission(UserPermission.CREATE_POST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    post = await user.create_post(title=request.title, content=request.content_data)
    return ResponseModel[Posts](success=True, data=post)


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
async def update_post(post_id: int, request: PostUpdateRequest, auth_data: LoginDep):
    user, _ = auth_data
    post = await client.get_post(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    if not user.has_permission(UserPermission.MANAGE_POST) and post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    await post.edit(title=request.title, content=request.content_data)
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
):
    user, _ = auth_data
    post = await client.get_post(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    if not user.has_permission(UserPermission.MANAGE_POST) and post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    await post.delete()
