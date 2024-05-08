from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Generic, NoReturn, TypeVar
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
ProxiedObject = TypeVar("ProxiedObject")
context_vars: dict[ContextLocal, ContextVar] = {}  # type: ignore


class ContextLocal(Generic[ProxiedObject]):
    def __init__(self) -> None:
        context_vars[self] = ContextVar(str(uuid4()))

    @classmethod
    def of_type(cls, _: type[ProxiedObject]) -> ProxiedObject:
        return cls()  # type: ignore

    def set(self, obj: ProxiedObject) -> None:
        context_vars[self].set(obj)

    def __getattr__(self, name: str) -> Any:
        obj = context_vars[self].get()
        return getattr(obj, name)

    def __copy__(self) -> NoReturn:
        raise NotImplementedError

    def __deepcopy__(self, memo: Any) -> NoReturn:
        raise NotImplementedError


class TypedProxy(Generic[ProxiedObject], CallableObjectProxy):
    def __init__(self) -> None:
        super().__init__(None)  # type: ignore

    @classmethod
    def of_type(cls, _: type[ProxiedObject]) -> ProxiedObject:
        return cls()  # type: ignore

    def set(self, obj: ProxiedObject) -> None:
        super().__init__(obj)  # type: ignore

    def __copy__(self) -> NoReturn:
        raise NotImplementedError

    def __deepcopy__(self, memo: Any) -> NoReturn:
        raise NotImplementedError


engine = TypedProxy.of_type(Engine)
connection = TypedProxy.of_type(Connection)
transaction = TypedProxy.of_type(Transaction)
db_session_maker = TypedProxy.of_type(sessionmaker)
DatabaseSession = ContextLocal.of_type(Session)


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
    db_session = db_session_maker()
    DatabaseSession.set(db_session)


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
    yield
    await end_session()


@sync_to_async()
def rollback_transaction() -> None:
    if transaction.is_active:
        transaction.rollback()
    if not connection.closed:  # pragma: no cover
        connection.close()
    print(engine.pool.status())  # noqa: T201
    engine.dispose()


def delete_test_database(worker_id: str) -> None:
    reverse_all(f"{settings.DATABASE_URL}-{worker_id}")
