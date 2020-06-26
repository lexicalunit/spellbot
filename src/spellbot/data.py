from os.path import dirname, realpath
from pathlib import Path

import alembic
import alembic.config
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    and_,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

PACKAGE_ROOT = Path(dirname(realpath(__file__)))
ASSETS_DIR = PACKAGE_ROOT / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = PACKAGE_ROOT / "versions"


Base = declarative_base()


class AuthorizedChannel(Base):
    __tablename__ = "authorized_channels"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild = Column(BigInteger, primary_key=True, nullable=False)
    name = Column(String(100), nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, nullable=False)

    queue = relationship("Queue", uselist=False, back_populates="user")

    def enqueue(self, guild):
        session = Session.object_session(self)
        row = Queue(user_id=self.id, guild=guild)
        session.add(row)
        session.commit()
        return row


class Queue(Base):
    __tablename__ = "queue"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    guild = Column(BigInteger, primary_key=True, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="queue")

    @classmethod
    def playgroup(cls, session, include, guild, size):
        others = (
            session.query(Queue)
            .filter(
                and_(Queue.guild == guild, ~Queue.user_id.in_([x.id for x in include]))
            )
            .order_by(Queue.created_at)
            .limit(size - len(include))
            .all()
        )
        if len(others) + len(include) < size:
            return None
        return (
            include
            + session.query(User).filter(User.id.in_(r.user_id for r in others)).all()
        )

    @classmethod
    def dequeue(cls, session, group):
        session.query(Queue).filter(
            Queue.user_id.in_([user.id for user in group])
        ).delete(synchronize_session=False)


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
