from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .router import router
from .schemas.response import ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


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
        status_code=exc.status_code, content=ErrorResponse(success=False, message=exc.detail).model_dump()
    )


@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

app.include_router(router)
