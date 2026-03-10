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

    yield

    await database_close()
    global_logger.info("Database Closed.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-MAX-PAGE"],
)


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
