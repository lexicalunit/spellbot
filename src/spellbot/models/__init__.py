from __future__ import annotations

import logging
from importlib import import_module
from inspect import getmembers, isclass
from pathlib import Path
from pkgutil import iter_modules

import alembic
import alembic.command
import alembic.config
from sqlalchemy import create_engine, text
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.sqltypes import String
from sqlalchemy_utils import create_database, database_exists

MODULE_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = MODULE_ROOT.parent
MIGRATIONS_DIR = PACKAGE_ROOT / "migrations"
ALEMBIC_INI = MIGRATIONS_DIR / "alembic.ini"

logger = logging.getLogger(__name__)

Base = declarative_base()
now = text("(now() at time zone 'utc')")


def import_models():
    package_dir = Path(__file__).resolve().parent
    for info in iter_modules([str(package_dir)]):
        module = import_module(f"{__name__}.{info.name}")
        for name, _object in getmembers(module, isclass):
            if isclass(_object) and issubclass(_object, Base):
                if name not in globals():
                    globals()[name] = _object


def create_all(DATABASE_URL: str) -> None:
    import_models()
    engine = create_engine(DATABASE_URL, echo=False)
    if not database_exists(engine.url):  # pragma: no cover
        create_database(engine.url)
    connection: Connection = engine.connect()
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    config.attributes["connection"] = connection  # pylint: disable=E1137
    alembic.command.upgrade(config, "head")


def reverse_all(DATABASE_URL: str) -> None:
    import_models()
    engine = create_engine(DATABASE_URL, echo=False)
    connection: Connection = engine.connect()
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    config.attributes["connection"] = connection  # pylint: disable=E1137
    alembic.command.downgrade(config, "base")


class StringLiteral(String):  # pragma: no cover
    def literal_processor(self, dialect):
        super_processor = super().literal_processor(dialect)

        def process(value):
            if isinstance(value, int):
                return text(value)  # type: ignore
            if not isinstance(value, str):
                value = text(value)
            result = super_processor(value)  # type: ignore
            if isinstance(result, bytes):
                result = result.decode(dialect.encoding)
            return result

        return process


def literalquery(statement):  # pragma: no cover
    """WARNING: This is **insecure**. DO NOT execute returned strings."""
    import sqlalchemy.orm

    if isinstance(statement, sqlalchemy.orm.Query):
        statement = statement.statement
    return statement.compile(compile_kwargs={"literal_binds": True}).string
