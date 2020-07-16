import json
from datetime import datetime
from pathlib import Path

import alembic
import alembic.config
import discord
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    and_,
    create_engine,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from spellbot.constants import THUMB_URL

PACKAGE_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_ROOT / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = PACKAGE_ROOT / "versions"


Base = declarative_base()


class Server(Base):
    __tablename__ = "servers"
    guild_xid = Column(BigInteger, primary_key=True, nullable=False)
    prefix = Column(String(10), nullable=False, default="!")
    expire = Column(Integer, nullable=False, server_default=text("30"))  # minutes
    games = relationship("Game", back_populates="server")
    channels = relationship("Channel", back_populates="server")

    def bot_allowed_in(self, channel_name):
        return not self.channels or any(
            channel.name == channel_name for channel in self.channels
        )

    def __repr__(self):
        return json.dumps(
            {
                "guild_xid": self.guild_xid,
                "prefix": self.prefix,
                "expire": self.expire,
                "channels": [channel.name for channel in self.channels],
            }
        )


class Channel(Base):
    __tablename__ = "authorized_channels"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild_xid = Column(
        BigInteger, ForeignKey("servers.guild_xid", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    server = relationship("Server", back_populates="channels")


games_tags = Table(
    "games_tags",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id", ondelete="CASCADE")),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    games = relationship("Game", back_populates="event")

    @property
    def started(self):
        return any(game.status == "started" for game in self.games)

    def __repr__(self):
        return json.dumps({"id": self.id})


class User(Base):
    __tablename__ = "users"
    xid = Column(BigInteger, primary_key=True, nullable=False)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="SET NULL"), nullable=True)
    cached_name = Column(String(50))
    game = relationship("Game", back_populates="users")

    @property
    def waiting(self):
        return self.game and self.game.status in ["pending", "ready"]


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
    url = Column(String(255))
    status = Column(String(30), nullable=False, server_default=text("'pending'"))
    message = Column(String(255))
    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    message_xid = Column(BigInteger)
    users = relationship("User", back_populates="game")
    tags = relationship("Tag", secondary=games_tags, back_populates="games")
    server = relationship("Server", back_populates="games")
    event = relationship("Event", back_populates="games")

    @classmethod
    def expired(cls, session):
        return (
            session.query(Game)
            .filter(
                and_(
                    datetime.utcnow() >= Game.expires_at,
                    Game.url == None,
                    Game.status != "ready",
                )
            )
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
                "url": self.url,
                "status": self.status,
                "message": self.message,
                "message_xid": self.message_xid,
            }
        )

    def to_embed(self):
        if self.url:
            title = self.message if self.message else "**Your game is ready!**"
        else:
            remaining = self.size - len(self.users)
            plural = "s" if remaining > 1 else ""
            title = f"**Waiting for {remaining} more player{plural} to join...**"
        embed = discord.Embed(title=title)
        embed.set_thumbnail(url=THUMB_URL)
        if self.url:
            embed.description = (
                f"Click the link below to join your SpellTable game.\n<{self.url}>"
            )
            players = ", ".join(sorted([f"<@{user.xid}>" for user in self.users]))
            embed.add_field(name="Players", value=players)
        else:
            embed.description = "To join/leave this game, react with ➕/➖."
        tag_names = None
        if not (len(self.tags) == 1 and self.tags[0].name == "default"):
            tag_names = ", ".join(sorted([tag.name for tag in self.tags]))
            embed.add_field(name="Tags", value=tag_names)
        embed.color = discord.Color(0x5A3EFD)
        return embed


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
