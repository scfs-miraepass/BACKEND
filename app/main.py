from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .router import router
from .schemas.response import ErrorResponse
from .core import settings
from .core.loggers import global_logger
from .core.database import database_init, database_close
from .core.redis import redis


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

    yield

    await redis.close()
    await database_close()
    global_logger.info("Database Closed.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-MAX-PAGE"],
)

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


app.include_router(router)
