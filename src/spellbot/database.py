from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, NoReturn
from uuid import uuid4

from asgiref.sync import sync_to_async
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Connection, Engine, Transaction
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from wrapt import CallableObjectProxy

from .models import create_all, reverse_all
from .settings import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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


class TypedProxy[ProxiedObject](CallableObjectProxy):
    __wrapped__: ProxiedObject | None

    def __init__(self) -> None:
        super().__init__(None)

    @classmethod
    def of_type(cls, _: type[ProxiedObject]) -> TypedProxy[ProxiedObject]:
        return cls()

    def set(self, obj: ProxiedObject) -> None:
        super().__init__(obj)

    def __copy__(self) -> NoReturn:
        raise NotImplementedError

    def __deepcopy__(self, memo: Any) -> NoReturn:
        raise NotImplementedError


engine = TypedProxy[Engine].of_type(Engine)
connection = TypedProxy[Connection].of_type(Connection)
transaction = TypedProxy[Transaction].of_type(Transaction)
db_session_maker = TypedProxy[sessionmaker].of_type(sessionmaker)
DatabaseSession = ContextLocal[Session].of_type(Session)


@sync_to_async()
def initialize_connection(
    app: str,
    *,
    use_transaction: bool = False,
    run_migrations: bool = True,
    worker_id: str | None = None,
) -> None:
    """
    Connect to the database.

    SpellBot follows the "thread-local scoped database sessions per request" model
    of typical web applications except that instead of web requests, we're dealing
    with bot interactions. And instead of thread local, we have context local aysnc
    context. SpellBot maintains a database connection for the lifetime of the bot,
    which is created in this function.

    Subsequent interactions then will create their own transaction and session
    with which to execute database queries. For more details on how this flow works,
    see the section named "Using Thread-Local Scope with Web Applications" in the
    SQLAlchemy documentation: https://docs.sqlalchemy.org/en/14/orm/contextual.html

    If `use_transaction` is set to `True`, then a transaction is setup before any
    sessions are created. This transaction can then be entirely rolled back using
    `rollback_transaction()`. This is useful for allowing tests to run within their
    own transaction that is always rolled back.
    """
    db_url = settings.DATABASE_URL
    if worker_id:
        db_url += f"-{worker_id}"
        app += f"-{worker_id}"
    if run_migrations:  # pragma: no cover
        create_all(db_url)
    engine_obj = create_engine(
        db_url,
        echo=settings.DATABASE_ECHO,
        connect_args={"application_name": app},
        isolation_level=None if use_transaction else "AUTOCOMMIT",
    )
    connection_obj = engine_obj.connect()

    if use_transaction:  # pragma: no cover
        transaction_obj = connection_obj.begin()
        transaction.set(transaction_obj)

    db_session_maker_obj = sessionmaker(bind=connection_obj)

    engine.set(engine_obj)
    connection.set(connection_obj)
    db_session_maker.set(db_session_maker_obj)


@sync_to_async()
def begin_session() -> None:
    session = db_session_maker()
    DatabaseSession.set(session)


@sync_to_async()
def rollback_session() -> None:  # pragma: no cover
    DatabaseSession.rollback()


@sync_to_async()
def end_session() -> None:
    DatabaseSession.commit()
    DatabaseSession.close()


@asynccontextmanager
async def db_session_manager() -> AsyncGenerator[None, None]:
    await begin_session()
    try:
        yield
    finally:
        await end_session()


@sync_to_async()
def rollback_transaction() -> None:
    if transaction.__wrapped__ and transaction.__wrapped__.is_active:
        transaction.__wrapped__.rollback()
    if connection.__wrapped__ and not connection.__wrapped__.closed:  # pragma: no cover
        connection.__wrapped__.close()
    status = engine.__wrapped__.pool.status() if engine.__wrapped__ else None
    print(f"pool status: {status}")  # noqa: T201
    if engine.__wrapped__:
        engine.__wrapped__.dispose()


def delete_test_database(worker_id: str) -> None:
    reverse_all(f"{settings.DATABASE_URL}-{worker_id}")
