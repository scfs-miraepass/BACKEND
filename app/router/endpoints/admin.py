from fastapi import APIRouter, HTTPException, status, Query, Response, Depends
from sqlmodel import select, func
from typing import List
from math import ceil

from app.core import SessionDep, LoginDep
from app.schemas import User, Users


async def verify_admin(login_user: LoginDep) -> Users:
    user, _ = login_user
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )
    return user


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin)])


@router.get("/student", response_model=List[User])
async def get_students(
    session: SessionDep,
    response: Response,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 당 유저 데이터 갯수 (최대 100)"),
):
    # 전체 유저 수 조회
    count_query = select(func.count()).select_from(Users)
    total_count = (await session.execute(count_query)).scalar_one()

    # 최대 페이지 계산 (데이터가 없으면 1페이지)
    max_page = ceil(total_count / size) if total_count > 0 else 1

    # 클라이언트가 읽을 수 있도록 헤더에 최대 페이지 전달
    response.headers["X-MAX-PAGE"] = str(max_page)

    # offset 계산 및 데이터 조회
    offset = (page - 1) * size
    query = select(Users).offset(offset).limit(size)

    result = await session.execute(query)
    users = result.scalars().all()

    return users
