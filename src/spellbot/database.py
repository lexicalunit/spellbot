import logging
from typing import Generic, Type, TypeVar

from asgiref.sync import sync_to_async
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Connection, Engine, Transaction
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm.session import sessionmaker
from wrapt import CallableObjectProxy

from spellbot.models import create_all
from spellbot.models.guild import Guild

logger = logging.getLogger(__name__)

ProxiedObject = TypeVar("ProxiedObject")


class ContextLocal(Generic[ProxiedObject], CallableObjectProxy):
    def __init__(self):
        super().__init__(None)

    @classmethod
    def of_type(cls, _: Type[ProxiedObject]) -> ProxiedObject:
        return cls()  # type: ignore

    def set(self, obj: ProxiedObject):
        super().__init__(obj)

    def __copy__(self):
        raise NotImplementedError()

    def __deepcopy__(self, memo):
        raise NotImplementedError()


# Thread sensitive module attributes, only use them within sync_to_async code!
engine = ContextLocal.of_type(Engine)
connection = ContextLocal.of_type(Connection)
transaction = ContextLocal.of_type(Transaction)

# Thread local scoped database session, can be used inside/outside sync_to_async code,
# but only AFTER initialize_connection() has finished running.
DatabaseSession = ContextLocal.of_type(scoped_session)


@sync_to_async
def initialize_connection(
    app: str,
    *,
    use_transaction: bool = False,
    autocommit: bool = False,
    run_migrations: bool = True,
):
    """
    Connect to the database.

    SpellBot follows the "thread-local scoped database sessions per request" model
    of typical web applications except that instead of web requests, we're dealing
    with bot interactions. SpellBot maintains a database connection for the lifetime
    of the bot, which is created in this function.

    Subsequent interactions then will create their own transaction and session
    with which to execute database queries. For more details on how this flow works,
    see the section named "Using Thread-Local Scope with Web Applications" in the
    SQLAlchemy documentation: https://docs.sqlalchemy.org/en/14/orm/contextual.html

    If `use_transaction` is set to `True`, then a transaction is setup before any
    sessions are created. This transaction can then be entirely rolled back using
    `rollback_transaction()`. This is useful for allowing tests to run within their
    own transaction that is always rolled back.
    """
    from spellbot.settings import Settings

    settings = Settings()
    if run_migrations:
        create_all(settings.DATABASE_URL)
    engine_obj = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        connect_args={"application_name": app},
        isolation_level="AUTOCOMMIT" if autocommit else None,
    )
    connection_obj = engine_obj.connect()

    if use_transaction:  # pragma: no cover
        transaction_obj = connection_obj.begin()
        transaction.set(transaction_obj)  # type: ignore

    db_session_obj = scoped_session(
        sessionmaker(
            bind=connection_obj,
            autocommit=autocommit,
        ),
    )

    engine.set(engine_obj)  # type: ignore
    connection.set(connection_obj)  # type: ignore
    DatabaseSession.set(db_session_obj)  # type: ignore


@sync_to_async
def rollback_transaction():
    DatabaseSession.close()
    transaction.rollback()
    connection.close()


@sync_to_async
def get_legacy_prefixes() -> dict:  # pragma: no cover
    return {
        row[0]: row[1]
        for row in DatabaseSession.query(Guild.xid, Guild.legacy_prefix).all()
    }
