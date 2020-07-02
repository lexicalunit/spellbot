from datetime import datetime, timedelta
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
    Table,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

PACKAGE_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_ROOT / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = PACKAGE_ROOT / "versions"


Base = declarative_base()


class BotPrefix(Base):
    __tablename__ = "bot_prefixes"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild_xid = Column(BigInteger, nullable=False)
    prefix = Column(String(10), nullable=False)


class AuthorizedChannel(Base):
    __tablename__ = "authorized_channels"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild_xid = Column(BigInteger, nullable=False)
    name = Column(String(100), nullable=False)


games_tags = Table(
    "games_tags",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id")),
    Column("tag_id", Integer, ForeignKey("tags.id")),
)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    xid = Column(BigInteger, nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True)
    game = relationship("Game", back_populates="users")

    @property
    def waiting(self):
        return self.game is not None

    def enqueue(self, *, size, guild_xid, include, tags):
        session = Session.object_session(self)
        required_tag_ids = set(tag.id for tag in tags)
        considerations = (
            session.query(games_tags.c.game_id, func.count(games_tags.c.game_id))
            .filter(games_tags.c.tag_id.in_([tag.id for tag in tags]))
            .group_by(games_tags.c.game_id)
            .having(func.count(games_tags.c.game_id) == len(tags))
            .all()
        )
        valid_game_ids = []
        for row in considerations:
            game = session.query(Game).get(row.game_id)
            if set(tag.id for tag in game.tags) != required_tag_ids:
                continue
            if len(game.users) >= size - len(include):
                continue
            if game.guild_xid != guild_xid:
                continue
            if game.size != size:
                continue
            valid_game_ids.append(row.game_id)
        existing_game = (
            session.query(Game)
            .filter(Game.id.in_(valid_game_ids))
            .order_by(Game.created_at)
            .first()
        )
        if existing_game:
            self.game = existing_game
        else:
            self.game = Game(size=size, guild_xid=guild_xid, tags=tags)
            session.add(self.game)
        for user in include:
            user.game = self.game

    def dequeue(self):
        session = Session.object_session(self)
        if len(self.game.users) == 1:
            session.delete(self.game)
        self.game = None


class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    size = Column(Integer, nullable=False)
    guild_xid = Column(BigInteger, nullable=False)
    users = relationship("User", back_populates="game")
    tags = relationship("Tag", secondary=games_tags, back_populates="games")

    @classmethod
    def expired(cls, session, window):
        cutoff = datetime.utcnow() - timedelta(minutes=window)
        return session.query(Game).filter(Game.created_at < cutoff).all()


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(50), nullable=False)
    games = relationship("Game", secondary=games_tags, back_populates="tags")


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
        self.engine = create_engine(db_url, echo=False)
        self.conn = self.engine.connect()
        create_all(self.conn, db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = Base.metadata
