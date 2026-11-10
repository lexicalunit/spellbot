# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import alembic
import alembic.command
import alembic.config
from sqlalchemy import BigInteger, Integer, create_engine, text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Query

from . import import_models

if TYPE_CHECKING:
    from sqlalchemy.engine.url import URL
    from sqlalchemy.orm import QueryableAttribute

MODULE_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = MODULE_ROOT.parent
MIGRATIONS_DIR = PACKAGE_ROOT / "migrations"
ALEMBIC_INI = MIGRATIONS_DIR / "alembic.ini"

logger = logging.getLogger(__name__)

now = text("(now() at time zone 'utc')")


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all SpellBot models."""


# Marker placed in a column's `doc` to flag it as editable from the web admin panel.
WEB_EDITABLE = "[web-editable]"


def column_length(column: Any) -> int:
    """Return the maximum length of a string column, e.g. `column_length(Game.rules)`."""
    return column.property.columns[0].type.length


# Largest value of each Postgres integer type the models use. `BigInteger` subclasses
# `Integer`, so it's listed first.
INTEGER_MAXIMUMS: tuple[tuple[type[Integer], int], ...] = (
    (BigInteger, 2**63 - 1),
    (Integer, 2**31 - 1),
)


def column_max(column: QueryableAttribute[int]) -> int:
    """Return the largest value an integer column can hold, e.g. `column_max(Game.id)`."""
    column_type = column.expression.type
    for integer_type, maximum in INTEGER_MAXIMUMS:
        if isinstance(column_type, integer_type):
            return maximum
    msg = f"{column} is not an integer column"
    raise TypeError(msg)


def web_editable(doc: str) -> str:
    """Return `doc` tagged with the web-editable marker, for use in model column docs."""
    return f"{doc} {WEB_EDITABLE}"


def ensure_database_exists(url: URL) -> None:  # pragma: no cover
    """Postgres-only: create the target database if it does not yet exist."""
    database_name = url.database
    server_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with server_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        server_engine.dispose()


def create_all(database_url: str) -> None:
    import_models()
    engine = create_engine(database_url, echo=False)
    try:
        ensure_database_exists(engine.url)
        with engine.connect() as connection:
            config = alembic.config.Config(str(ALEMBIC_INI))
            config.set_main_option("script_location", str(MIGRATIONS_DIR))
            config.set_main_option("sqlalchemy.url", database_url)
            config.attributes["connection"] = connection
            alembic.command.upgrade(config, "head")
    finally:
        engine.dispose()


def reverse_all(database_url: str) -> None:
    import_models()
    engine = create_engine(database_url, echo=False)
    try:
        with engine.connect() as connection:
            config = alembic.config.Config(str(ALEMBIC_INI))
            config.set_main_option("script_location", str(MIGRATIONS_DIR))
            config.set_main_option("sqlalchemy.url", database_url)
            config.attributes["connection"] = connection
            alembic.command.downgrade(config, "base")
    finally:
        engine.dispose()


def literalquery(statement: Any) -> str:  # pragma: no cover
    """WARNING: This is **insecure**. DO NOT execute returned strings."""
    if isinstance(statement, Query):
        statement = statement.statement
    return statement.compile(compile_kwargs={"literal_binds": True}).string
