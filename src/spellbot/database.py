from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
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

    # For type checking, use the generic version from the stubs
    _CallableObjectProxyBase = CallableObjectProxy
else:
    # At runtime, CallableObjectProxy is not subscriptable, so create a wrapper
    # that allows subscripting but just returns itself

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

    def set(self, obj: ProxiedObject) -> Token[ProxiedObject]:
        return context_vars[self].set(obj)

    def reset(self, token: Token[ProxiedObject]) -> None:
        context_vars[self].reset(token)

    def is_set(self) -> bool:
        return context_vars[self].get(None) is not None

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
        super().__init__(None)  # type: ignore  # None is valid for lazy init

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


def to_async_url(db_url: str) -> str:
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
    """
    Connect to the database.

    SpellBot follows a "scoped session per request" model typical of web
    applications, except the "request" is a bot interaction (or web request)
    and scoping is done via a `ContextVar` rather than a thread local so the
    active session propagates correctly across `await` boundaries without
    bleeding between concurrent tasks. A single `AsyncEngine` is created here
    for the lifetime of the process; each interaction then checks out its own
    `AsyncSession` from the shared `async_sessionmaker` via `begin_session()`
    / `end_session()`. By default the engine runs with `AUTOCOMMIT` isolation
    and transactions are opened explicitly per session.

    See the SQLAlchemy asyncio extension docs for background on the
    `AsyncEngine` / `AsyncSession` patterns:
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

    If `use_transaction` is set to `True`, a long-lived connection is opened
    and an outer transaction is begun on it; the sessionmaker is bound to
    that connection with `join_transaction_mode="create_savepoint"` so each
    session nests inside the outer transaction via savepoints. The whole
    outer transaction can then be discarded via `rollback_transaction()`,
    which is useful for tests that want full isolation.
    """
    db_url = settings.RESOLVED_DATABASE_URL
    if worker_id:
        db_url += f"-{worker_id}"
        app += f"-{worker_id}"
    if run_migrations:  # pragma: no cover
        create_all(db_url)

    async_url = to_async_url(db_url)
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


async def begin_session() -> Token[AsyncSession]:
    session = db_session_maker()
    return DatabaseSession.set(session)


async def rollback_session() -> None:  # pragma: no cover
    await DatabaseSession.rollback()


async def end_session(token: Token[AsyncSession]) -> None:
    await DatabaseSession.commit()
    await DatabaseSession.close()
    DatabaseSession.reset(token)
    if DatabaseSession.is_set():  # pragma: no branch
        DatabaseSession.expire_all()


@asynccontextmanager
async def db_session_manager() -> AsyncGenerator[None]:
    token = await begin_session()
    try:
        yield
    finally:
        await end_session(token)


async def rollback_transaction() -> None:  # pragma: no cover
    if connection.__wrapped__ is not None and not connection.__wrapped__.closed:
        await connection.__wrapped__.rollback()
        await connection.__wrapped__.close()
    if engine.__wrapped__ is not None:
        await engine.__wrapped__.dispose()


def delete_test_database(worker_id: str) -> None:  # pragma: no cover
    reverse_all(f"{settings.RESOLVED_DATABASE_URL}-{worker_id}")
