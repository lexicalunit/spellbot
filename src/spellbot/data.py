from os.path import dirname, realpath
from pathlib import Path

import alembic
import alembic.config
from sqlalchemy import BigInteger, Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

PACKAGE_ROOT = Path(dirname(realpath(__file__)))
ASSETS_DIR = PACKAGE_ROOT / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = PACKAGE_ROOT / "versions"


Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    author = Column(BigInteger, primary_key=True, nullable=False)

    def to_dict(self):
        return {
            "author": self.author,
        }


class AuthorizedChannel(Base):
    __tablename__ = "authorized_channels"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild = Column(BigInteger, primary_key=True, nullable=False)
    name = Column(String(100), nullable=False)


def create_all(connection, db_url):
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(VERSIONS_DIR))
    config.set_main_option("sqlalchemy.url", db_url)
    config.attributes["connection"] = connection
    alembic.command.upgrade(config, "head")


def reverse_all(connection, db_url):
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(VERSIONS_DIR))
    config.set_main_option("sqlalchemy.url", db_url)
    config.attributes["connection"] = connection
    alembic.command.downgrade(config, "base")


class Data:
    """Persistent and in-memory store for user data."""

    def __init__(self, db_url):
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.conn = self.engine.connect()
        create_all(self.conn, db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = Base.metadata
