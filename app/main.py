from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from tomllib import load

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .core import ServiceClient, settings
from .router import router
from .schemas import UserPermission
from .schemas.response import ErrorResponse
from .schemas.core import SchemaCore


scheduler = AsyncIOScheduler()
client = ServiceClient()

# pyproject.toml에서 버전을 동적으로 불러오기
pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject_data = load(f)
    app_version = pyproject_data.get("project", {}).get("version")
    if not app_version:
        raise KeyError("Failed to find 'version' in [project] section of pyproject.toml")


@scheduler.scheduled_job(CronTrigger(day_of_week="mon", hour=0, minute=0))
async def reset_grant_limit():
    await client.redis.delete_pattern("point_limit:grant:*")
    client.logs.service.info("포인트 지급 제한을 초기화 했습니다.")


@scheduler.scheduled_job(CronTrigger(hour=0, minute=0))
async def reset_student_limit():
    await client.redis.delete_pattern("point_limit:student:*")
    client.logs.service.info("학생 포인트 제한을 초기화 했습니다.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    애플리케이션 라이프사이클 관리
    시작 시 데이터베이스 초기화, 종료 시 연결 정리
    """
    if settings.debug:
        client.logs.global_.warning("디버그 모드가 활성화 되어있습니다!")

    await client.initialize()

    client.logs.global_.info("데이터베이스 서버와 시간대를 동기화")
    async with client.session as session:
        # PostgreSQL 사용하는경우 `SHOW TIME ZONE` 으로 SQL문 변경해야함
        tz_string = (await session.execute(text("SELECT @@time_zone"))).scalar()
        if tz_string.lower() == "system":
            tz_string = (await session.execute(text("SELECT @@system_time_zone"))).scalar()

        try:
            SchemaCore.timezone = ZoneInfo(tz_string)
            client.logs.global_.debug(f"DB의 시간대: {SchemaCore.timezone}")
        except ZoneInfoNotFoundError:
            client.logs.global_.warning("DB의 서버 시간대를 해석할 수 없습니다.")

    scheduler.start()
    client.logs.global_.info("Scheduler 시작")

    yield

    scheduler.shutdown()
    client.logs.global_.info("Scheduler 종료")
    await client.close()


# FastAPI 인스턴스에 version 정보를 명시합니다.
app = FastAPI(lifespan=lifespan, title="MIRAE PASS BACKEND", version=app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-MAX-PAGE",
        "X-Server-Version",
        "X-CACHED",
    ],  # 클라이언트가 읽을 수 있도록 허용
)


# 모든 응답에 서버 버전을 알려주는 미들웨어 추가
@app.middleware("http")
async def add_server_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Server-Version"] = app.version
    return response


# 디버그 모드가 비활성화 되어있으면 모든 에러가 발생하는 내용을 로그에 출력
if not settings.debug:
    import sys

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        client.logs.global_.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(success=False, message=exc.detail or "No Message").model_dump(),
    )


@app.get("/")
async def read_root(_: UserPermission | None = None):
    return {"message": "Hello, World!"}


# from .core import SessionDep
# from .schemas import Users, UserType
# @app.get("/test")
# async def test(session: SessionDep):
#
#     # 1101~3699 : 학생
#     # 4000~4999 : 교사
#     # 5000~ : 서비스
#
#     # 테스트 학생
#     # session.add(Users(id=3601, type=UserType.student, name="홍길동", grade=3, number=6))
#
#     # 테스트 서비스
#     session.add(Users(type=UserType.service, name="카페테리아", id=5000))
#     await session.commit()


app.include_router(router)
