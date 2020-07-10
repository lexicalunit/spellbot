import json
from datetime import datetime, timedelta
from pathlib import Path

import alembic
import alembic.config
from humanize import naturaldelta
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    and_,
    create_engine,
    func,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker
from sqlalchemy.sql.expression import label

from spellbot.constants import AVG_QUEUE_TIME_WINDOW_MIN

PACKAGE_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_ROOT / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = PACKAGE_ROOT / "versions"


Base = declarative_base()


class WaitTime(Base):
    __tablename__ = "wait_times"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild_xid = Column(BigInteger, nullable=False)
    channel_xid = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    seconds = Column(Integer, nullable=False)

    @classmethod
    def log(cls, session, *, guild_xid, channel_xid, seconds):
        row = WaitTime(guild_xid=guild_xid, channel_xid=channel_xid, seconds=seconds)
        session.add(row)

    @classmethod
    def average(cls, session, *, guild_xid, channel_xid, scope, window_min):
        filters = [
            WaitTime.guild_xid == guild_xid,
            WaitTime.created_at > datetime.utcnow() - timedelta(minutes=window_min),
        ]
        if scope == "channel":
            filters.append(WaitTime.channel_xid == channel_xid)
        row = (
            session.query(label("average", func.sum(WaitTime.seconds) / func.count()))
            .filter(and_(*filters))
            .one_or_none()
        )
        return row.average if row else None


class Server(Base):
    __tablename__ = "servers"
    guild_xid = Column(BigInteger, primary_key=True, nullable=False)
    prefix = Column(String(10), nullable=False, default="!")
    scope = Column(String(10), nullable=False, default="server")
    expire = Column(Integer, nullable=False, server_default=text("30"))  # minutes
    games = relationship("Game", back_populates="server")
    authorized_channels = relationship("AuthorizedChannel", back_populates="server")

    def __repr__(self):
        return json.dumps(
            {
                "guild_xid": self.guild_xid,
                "prefix": self.prefix,
                "scope": self.scope,
                "expire": self.expire,
            }
        )


class AuthorizedChannel(Base):
    __tablename__ = "authorized_channels"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild_xid = Column(
        BigInteger, ForeignKey("servers.guild_xid", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    server = relationship("Server", back_populates="authorized_channels")


games_tags = Table(
    "games_tags",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id", ondelete="CASCADE")),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)


class User(Base):
    __tablename__ = "users"
    xid = Column(BigInteger, primary_key=True, nullable=False)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="SET NULL"), nullable=True)
    queued_at = Column(DateTime, nullable=True)
    game = relationship("Game", back_populates="users")

    @property
    def waiting(self):
        return self.queued_at is not None

    def enqueue(self, *, server, channel_xid, include, size, power, tags):
        session = Session.object_session(self)
        guild_xid = server.guild_xid
        required_tag_ids = set(tag.id for tag in tags)
        filters = [
            games_tags.c.tag_id.in_([tag.id for tag in tags]),
            Game.status == "pending",
            Game.guild_xid == guild_xid,
            Game.size == size,
        ]
        if server.scope == "channel":
            filters.append(Game.channel_xid == channel_xid)
        if power:
            filters.append(Game.power >= power - 2)
            filters.append(Game.power <= power + 2)
        considerations = (
            session.query(games_tags.c.game_id, func.count(games_tags.c.game_id))
            .join(Game)
            .filter(and_(*filters))
            .group_by(games_tags.c.game_id)
            .having(func.count(games_tags.c.game_id) == len(tags))
            .all()
        )
        existing_game = None
        for row in considerations:
            # FIXME: How can we move these checks into the query statement?
            game = session.query(Game).get(row.game_id)
            if set(tag.id for tag in game.tags) != required_tag_ids:
                continue
            if len(game.users) >= size - len(include):
                continue
            existing_game = game
            break
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=server.expire)
        if existing_game:
            already_seated = len(existing_game.users)
            self.game = existing_game
            self.game.updated_at = now
            self.game.expires_at = expires_at
            if power:
                # recalculating the average power for this game
                newly_seated = 1 + len(include)
                now_seated = already_seated + newly_seated
                total_power = self.game.power * already_seated + power * newly_seated
                self.game.power = total_power / now_seated
        else:
            self.game = Game(
                channel_xid=channel_xid if server.scope == "channel" else None,
                created_at=now,
                expires_at=expires_at,
                guild_xid=guild_xid,
                power=power,
                size=size,
                tags=tags,
                updated_at=now,
            )
            session.add(self.game)
        self.queued_at = now
        for user in include:
            user.game = self.game
            user.queued_at = now

    def dequeue(self):
        session = Session.object_session(self)
        if self.game and len(self.game.users) == 1:
            self.game.tags = []  # cascade delete tag associations
            session.delete(self.game)
        self.game = None
        self.queued_at = None


class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    size = Column(Integer, nullable=False)
    guild_xid = Column(
        BigInteger, ForeignKey("servers.guild_xid", ondelete="CASCADE"), nullable=False
    )
    channel_xid = Column(BigInteger)
    power = Column(Float)
    url = Column(String(255))
    status = Column(String(30), nullable=False, server_default=text("'pending'"))
    message = Column(String(255))
    users = relationship("User", back_populates="game")
    tags = relationship("Tag", secondary=games_tags, back_populates="games")
    server = relationship("Server", back_populates="games")

    @classmethod
    def expired(cls, session):
        return (
            session.query(Game)
            .filter(and_(datetime.utcnow() >= Game.expires_at, Game.url == None))
            .all()
        )

    def __repr__(self):
        return json.dumps(
            {
                "id": self.id,
                "created_at": str(self.created_at),
                "updated_at": str(self.updated_at),
                "expires_at": str(self.expires_at),
                "size": self.size,
                "guild_xid": self.guild_xid,
                "channel_xid": self.channel_xid,
                "power": self.power,
                "url": self.url,
                "status": self.status,
                "message": self.message,
            }
        )

    def to_str(self):
        session = Session.object_session(self)
        rvalue = ""
        if self.url:
            if self.message:
                rvalue += f"{self.message}\n"
            else:
                rvalue += "**Your SpellTable game is ready!**\n"
            rvalue += f"{self.url}\n"
        else:
            rvalue += (
                "**You have been entered in a play queue"
                f" for a {self.size} player game.**"
            )
            average = WaitTime.average(
                session,
                guild_xid=self.server.guild_xid,
                channel_xid=self.channel_xid,
                scope=self.server.scope,
                window_min=AVG_QUEUE_TIME_WINDOW_MIN,
            )
            if average:
                delta = naturaldelta(timedelta(seconds=average))
                rvalue += f" _The average wait time is {delta}._\n"
            else:
                rvalue += "\n"
            rvalue += (
                "\n🚨 When your game is ready I will"
                " send you another Direct Message! 🚨\n\n"
            )
        players = ", ".join(sorted([f"<@{user.xid}>" for user in self.users]))
        rvalue += f"Players: {players}\n"
        if self.channel_xid:
            rvalue += f"Channel: <#{self.channel_xid}>\n"
        if not (len(self.tags) == 1 and self.tags[0].name == "default"):
            tag_names = ", ".join(sorted([tag.name for tag in self.tags]))
            rvalue += f"Tags: {tag_names}\n"
        if self.power:
            rvalue += f"Average Power Level: {self.power:.1f}\n"
        return rvalue.strip()


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
