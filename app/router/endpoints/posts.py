from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core import SessionDep, LoginDep
from app.schemas.post import Posts, PostContent
from app.schemas.response import ResponseModel, ErrorResponse

router = APIRouter(prefix="/posts", tags=["posts"])


class PostCreateRequest(BaseModel):
    title: str = Field(..., description="게시글 제목")
    content_data: dict = Field(..., description="게시글의 본문 데이터")


class PostUpdateRequest(BaseModel):
    title: str | None = Field(None, description="수정할 게시글 제목")
    content_data: dict | None = Field(None, description="수정할 게시글의 본문 데이터")


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

    return ResponseModel[Posts](success=True, data=new_post)


@router.put(
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
