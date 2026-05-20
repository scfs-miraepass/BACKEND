from tomllib import load
from pathlib import Path
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .router import router
from .schemas.response import ErrorResponse
from .core import settings
from .core.loggers import global_logger, service_logger
from .core.database import database_init, database_close
from .core.redis import redis

# pyproject.toml에서 버전을 동적으로 불러오기
pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject_data = load(f)
    app_version = pyproject_data.get("project", {}).get("version")
    if not app_version:
        raise KeyError("Failed to find 'version' in [project] section of pyproject.toml")


async def reset_limit():
    service_logger.debug("Resetting point distribution limits.")
    await redis.delete_pattern("point_limit:*")
    service_logger.info("Point distribution limit reset complete.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    애플리케이션 라이프사이클 관리
    시작 시 데이터베이스 초기화, 종료 시 연결 정리
    """
    if settings.debug:
        global_logger.warning("Enable Debug Mode!")

    await database_init()
    global_logger.info("Database Initialized.")

    await redis.init()
    global_logger.info("Redis Initialized.")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(reset_limit, CronTrigger(day_of_week="mon", hour=0, minute=0))

    scheduler.start()
    global_logger.info("Scheduler Start")

    yield

    scheduler.shutdown()
    global_logger.info("Scheduler Stop")

    await redis.close()
    global_logger.info("Redis Closed.")

    await database_close()
    global_logger.info("Database Closed.")


# FastAPI 인스턴스에 version 정보를 명시합니다.
app = FastAPI(lifespan=lifespan, title="MIRAE PASS BACKEND", version=app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-MAX-PAGE", "X-Server-Version"],  # 클라이언트가 읽을 수 있도록 허용
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
        global_logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(success=False, message=exc.detail).model_dump(),
    )


@app.get("/")
async def read_root():
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
