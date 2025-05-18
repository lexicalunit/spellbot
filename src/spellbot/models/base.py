from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import alembic
import alembic.command
import alembic.config
from sqlalchemy import String, create_engine, text
from sqlalchemy.orm import declarative_base  # type: ignore (current type stubs are broken)
from sqlalchemy_utils import create_database, database_exists

from . import import_models

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection
    from sqlalchemy.ext.declarative import DeclarativeMeta

MODULE_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = MODULE_ROOT.parent
MIGRATIONS_DIR = PACKAGE_ROOT / "migrations"
ALEMBIC_INI = MIGRATIONS_DIR / "alembic.ini"

logger = logging.getLogger(__name__)

now = text("(now() at time zone 'utc')")
Base: DeclarativeMeta = declarative_base()


def create_all(database_url: str) -> None:
    import_models()
    engine = create_engine(database_url, echo=False)
    if not database_exists(engine.url):  # pragma: no cover
        create_database(engine.url)
    connection: Connection = engine.connect()
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["connection"] = connection
    alembic.command.upgrade(config, "head")


def reverse_all(database_url: str) -> None:
    import_models()
    engine = create_engine(database_url, echo=False)
    connection: Connection = engine.connect()
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["connection"] = connection
    alembic.command.downgrade(config, "base")


class StringLiteral(String):  # pragma: no cover
    def literal_processor(self, dialect: Any) -> Any:
        super_processor = super().literal_processor(dialect)

        def process(value: Any) -> Any:
            if isinstance(value, int):
                return text(value)  # type: ignore
            if not isinstance(value, str):
                value = text(value)
            result = super_processor(value)
            if isinstance(result, bytes):
                result = result.decode(dialect.encoding)
            return result

        return process


def literalquery(statement: Any) -> str:  # pragma: no cover
    """WARNING: This is **insecure**. DO NOT execute returned strings."""
    import sqlalchemy.orm

    if isinstance(statement, sqlalchemy.orm.Query):
        statement = statement.statement
    return statement.compile(compile_kwargs={"literal_binds": True}).string
