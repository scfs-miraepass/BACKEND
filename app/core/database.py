from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from .config import settings
from .loggers import LoggerCore


class DatabaseCore:
    instance = None
    async_engine: AsyncEngine | None = None
    AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

    _session_context: ContextVar[AsyncSession] = ContextVar("db_session_context")

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[AsyncSession, None]:
        if cls.AsyncSessionLocal is None:
            raise RuntimeError("Call DatabaseCore.initialize() first.")

        try:
            existing_session = cls._session_context.get()
            yield existing_session

        except LookupError:
            async with cls.AsyncSessionLocal() as session:
                token = cls._session_context.set(session)
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()
                    cls._session_context.reset(token)

    @classmethod
    async def initialize(cls) -> None:
        if cls.async_engine is None:
            LoggerCore.database.info("Database Initializing...")
            if settings.debug:
                cls.async_engine = create_async_engine(
                    str(settings.database.url),
                    echo=settings.debug,
                    poolclass=NullPool,
                )
                LoggerCore.database.debug(f"AsyncEngine connected to '{settings.database.url}' in debug mode.")
            else:
                cls.async_engine = create_async_engine(
                    str(settings.database.url),
                    echo=settings.debug,
                    pool_size=settings.database.pool_size,
                    max_overflow=settings.database.max_overflow,
                    pool_timeout=settings.database.pool_timeout,
                    pool_recycle=3600,
                    pool_pre_ping=True,  # 연결 유효성 검사
                )
                LoggerCore.database.debug(
                    f"AsyncEngine connected to '{settings.database.url}' with "
                    f"pool_size={settings.database.pool_size}, max_overflow={settings.database.max_overflow}, "
                    f"pool_timeout={settings.database.pool_timeout}"
                )

            cls.AsyncSessionLocal = async_sessionmaker(
                bind=cls.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,  # 트랜잭션 커밋 후 객체 만료 방지
                autoflush=False,  # 자동 flush (쿼리 전 변경사항 반영)
                autocommit=False,  # 수동 트랜잭션 관리
            )
            LoggerCore.database.info("Database Initialized.")
        else:
            LoggerCore.database.warning("Database is already initialized.")

    @classmethod
    async def dispose(cls) -> None:
        if cls.async_engine:
            LoggerCore.database.info("Database Disposing...")
            await cls.async_engine.dispose()
            cls.async_engine = None
            cls.AsyncSessionLocal = None
            LoggerCore.database.info("Database Disposed.")
        else:
            LoggerCore.database.warning("Database is not initialized.")
