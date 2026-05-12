from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, NoReturn
from uuid import uuid4

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from wrapt import CallableObjectProxy

from .models import create_all, reverse_all
from .settings import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    _CallableObjectProxyBase = CallableObjectProxy
else:

    class _CallableObjectProxyBase(CallableObjectProxy):
        def __class_getitem__(cls, item: object) -> type:
            return cls


logger = logging.getLogger(__name__)

context_vars: dict[ContextLocal[Any], ContextVar[Any]] = {}


class ContextLocal[ProxiedObject]:
    def __init__(self) -> None:
        context_vars[self] = ContextVar(str(uuid4()))

    @classmethod
    def of_type(cls, _: type[ProxiedObject]) -> ContextLocal[ProxiedObject]:
        return cls()

    def set(self, obj: ProxiedObject) -> None:
        context_vars[self].set(obj)

    def __getattr__(self, name: str) -> Any:
        obj = context_vars[self].get()
        return getattr(obj, name)

    def __copy__(self) -> NoReturn:
        raise NotImplementedError

    def __deepcopy__(self, memo: Any) -> NoReturn:
        raise NotImplementedError


class TypedProxy[ProxiedObject](_CallableObjectProxyBase[ProxiedObject]):
    __wrapped__: ProxiedObject | None

    def __init__(self) -> None:
        super().__init__(None)  # type: ignore[arg-type]

    @classmethod
    def of_type(cls, _: type[ProxiedObject]) -> TypedProxy[ProxiedObject]:
        return cls()

    def set(self, obj: ProxiedObject) -> None:
        super().__init__(obj)

    def __copy__(self) -> NoReturn:
        raise NotImplementedError

    def __deepcopy__(self, memo: Any) -> NoReturn:
        raise NotImplementedError


engine = TypedProxy[AsyncEngine].of_type(AsyncEngine)
connection = TypedProxy[AsyncConnection].of_type(AsyncConnection)
db_session_maker = TypedProxy[async_sessionmaker[AsyncSession]].of_type(async_sessionmaker)
DatabaseSession = ContextLocal[AsyncSession].of_type(AsyncSession)


def _to_async_url(db_url: str) -> str:
    if db_url.startswith("postgresql+psycopg://"):
        return db_url
    if db_url.startswith("postgresql://"):  # pragma: no cover
        return db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return db_url  # pragma: no cover


async def initialize_connection(
    app: str,
    *,
    use_transaction: bool = False,
    run_migrations: bool = True,
    worker_id: str | None = None,
) -> None:
    db_url = settings.DATABASE_URL
    if worker_id:
        db_url += f"-{worker_id}"
        app += f"-{worker_id}"
    if run_migrations:  # pragma: no cover
        create_all(db_url)

    async_url = _to_async_url(db_url)
    engine_obj: AsyncEngine = create_async_engine(
        async_url,
        echo=settings.DATABASE_ECHO,
        connect_args={"application_name": app},
        isolation_level=None if use_transaction else "AUTOCOMMIT",
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_POOL_MAX_OVERFLOW,
        pool_recycle=settings.DATABASE_POOL_RECYCLE_S,
        pool_pre_ping=True,
    )

    if use_transaction:  # pragma: no cover
        connection_obj = await engine_obj.connect()
        await connection_obj.begin()
        db_session_maker_obj = async_sessionmaker(
            bind=connection_obj,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        connection.set(connection_obj)
    else:
        db_session_maker_obj = async_sessionmaker(
            bind=engine_obj,
            expire_on_commit=False,
        )

    engine.set(engine_obj)
    db_session_maker.set(db_session_maker_obj)


async def begin_session() -> None:
    session = db_session_maker()
    DatabaseSession.set(session)


async def rollback_session() -> None:  # pragma: no cover
    await DatabaseSession.rollback()


async def end_session() -> None:
    await DatabaseSession.commit()
    await DatabaseSession.close()


@asynccontextmanager
async def db_session_manager() -> AsyncGenerator[None, None]:
    await begin_session()
    try:
        yield
    finally:
        await end_session()


async def rollback_transaction() -> None:
    if connection.__wrapped__ is not None and not connection.__wrapped__.closed:
        await connection.__wrapped__.rollback()
        await connection.__wrapped__.close()  # pragma: no cover
    if engine.__wrapped__ is not None:  # pragma: no cover
        await engine.__wrapped__.dispose()


def delete_test_database(worker_id: str) -> None:  # pragma: no cover
    reverse_all(f"{settings.DATABASE_URL}-{worker_id}")
