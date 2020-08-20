from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import alembic  # type: ignore
import alembic.command  # type: ignore
import alembic.config  # type: ignore
import discord
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    and_,
    between,
    create_engine,
    func,
    or_,
    text,
)
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker
from sqlalchemy.sql.expression import desc, distinct

from spellbot.constants import THUMB_URL

PACKAGE_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_ROOT / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = PACKAGE_ROOT / "versions"

logger = logging.getLogger(__name__)
Base = declarative_base()


class Server(Base):
    __tablename__ = "servers"
    guild_xid = Column(BigInteger, primary_key=True, nullable=False)
    prefix = Column(String(10), nullable=False, default="!")
    expire = Column(Integer, nullable=False, server_default=text("30"))  # minutes
    links = Column(String(10), nullable=False, server_default=text("'public'"))
    games = relationship("Game", back_populates="server", uselist=True)
    channels = relationship("Channel", back_populates="server", uselist=True)
    teams = relationship("Team", back_populates="server", uselist=True)

    def bot_allowed_in(self, channel_xid: int) -> bool:
        return not self.channels or any(
            channel.channel_xid == channel_xid for channel in self.channels
        )

    def games_data(self) -> Dict[str, List[str]]:
        data: Dict[str, List[str]] = {
            "id": [],
            "size": [],
            "status": [],
            "message": [],
            "system": [],
            "channel_xid": [],
            "url": [],
            "event_id": [],
            "created_at": [],
            "tags": [],
        }
        for game in sorted(self.games, key=lambda game: game.id):
            if game.status == "pending":
                continue
            tags_str = f"{','.join(sorted(tag.name for tag in game.tags))}"
            tags_str = (
                f'"{tags_str}"' if len(cast(List[Tag], game.tags)) > 1 else tags_str
            )
            event_id = game.event.id if game.event else None
            data["id"].append(str(game.id))
            data["size"].append(str(game.size))
            data["status"].append(game.status)
            data["message"].append(game.message or "")
            data["system"].append(game.system)
            data["channel_xid"].append(str(game.channel_xid) if game.channel_xid else "")
            data["url"].append(game.url or "")
            data["event_id"].append(str(event_id) if event_id else "")
            data["created_at"].append(str(game.created_at))
            data["tags"].append(tags_str)
        return data

    def __repr__(self) -> str:
        return json.dumps(
            {
                "guild_xid": self.guild_xid,
                "prefix": self.prefix,
                "expire": self.expire,
                "channels": [channel.channel_xid for channel in self.channels],
                "teams": [team.id for team in self.teams],
            }
        )


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(50), nullable=False)
    server = relationship("Server", back_populates="teams")

    @classmethod
    def points(cls, session: Session, guild_xid: int) -> dict:
        rows = (
            session.query(Team.name, func.sum(UserPoints.points))
            .select_from(User)
            .join(UserTeam)
            .join(UserPoints)
            .join(Team)
            .group_by(Team.name)
            .all()
        )
        results = {}
        for row in rows:
            results[row[0]] = row[1]
        return results


class Channel(Base):
    __tablename__ = "channels"
    channel_xid = Column(BigInteger, primary_key=True, nullable=False)
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server = relationship("Server", back_populates="channels")


games_tags = Table(
    "games_tags",
    Base.metadata,
    Column(
        "game_id", Integer, ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    ),
)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    games = relationship("Game", back_populates="event", uselist=True)

    @property
    def started(self) -> bool:
        return any(game.status == "started" for game in self.games)

    def __repr__(self) -> str:
        return json.dumps({"id": self.id})


class User(Base):
    __tablename__ = "users"
    xid = Column(BigInteger, primary_key=True, nullable=False)
    game_id = Column(
        Integer, ForeignKey("games.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cached_name = Column(String(50))
    invited = Column(Boolean, server_default=text("false"), nullable=False)
    invite_confirmed = Column(Boolean, server_default=text("false"), nullable=False)
    power = Column(Integer, nullable=True)
    game = relationship("Game", back_populates="users")

    @property
    def waiting(self) -> bool:
        if self.game and self.game.status in ["pending", "ready"]:
            return True
        return False

    def points(self, guild_xid) -> int:
        session = Session.object_session(self)
        results = (
            session.query(func.sum(UserPoints.points))
            .filter_by(user_xid=self.xid, guild_xid=guild_xid)
            .scalar()
        )
        return results or 0

    def to_json(self) -> dict:
        return {
            "xid": self.xid,
            "game_id": self.game_id,
            "cached_name": self.cached_name,
            "invited": self.invited,
            "invite_confirmed": self.invite_confirmed,
            "power": self.power,
        }


class UserTeam(Base):
    __tablename__ = "user_teams"
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)


class UserPoints(Base):
    __tablename__ = "user_points"
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    points = Column(Integer, nullable=False)


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(50), nullable=False)
    games = relationship(
        "Game", secondary=games_tags, back_populates="tags", uselist=True
    )

    @classmethod
    def create_many(cls, session: Session, tag_names: List[str]) -> List[Tag]:
        created_at_least_one = False
        tags = []
        for tag_name in tag_names:
            tag = session.query(Tag).filter_by(name=tag_name).one_or_none()
            if not tag:
                created_at_least_one = True
                tag = Tag(name=tag_name)
                session.add(tag)
            tags.append(tag)
        if created_at_least_one:
            session.commit()
        return tags


class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime)
    size = Column(Integer, nullable=False, index=True)
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_xid = Column(BigInteger, index=True)
    url = Column(String(255))
    status = Column(
        String(30), nullable=False, server_default=text("'pending'"), index=True
    )
    message = Column(String(255))
    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_xid = Column(BigInteger)
    system = Column(
        String(30), nullable=False, server_default=text("'spelltable'"), index=True
    )
    users = relationship("User", back_populates="game", uselist=True)
    tags = relationship("Tag", secondary=games_tags, back_populates="games", uselist=True)
    server = relationship("Server", back_populates="games")
    event = relationship("Event", back_populates="games")
    reports = relationship("Report", back_populates="game", uselist=True)

    @property
    def power(self) -> Optional[float]:
        values: List[int] = [user.power for user in self.users if user.power]
        if values:
            return sum(values) / len(values)
        return None

    @classmethod
    def find_existing(
        cls,
        *,
        session: Session,
        server: Server,
        channel_xid: int,
        size: int,
        seats: int,
        tags: List[Tag],
        system: str,
        power: Optional[int],
    ) -> Optional[Game]:
        guild_xid = server.guild_xid
        required_tag_ids = set(tag.id for tag in tags)
        select_filters = [
            Game.status == "pending",
            Game.guild_xid == guild_xid,
            Game.size == size,
            Game.channel_xid == channel_xid,
            Game.system == system,
        ]
        having_filters = [
            func.count(distinct(games_tags.c.tag_id)) == len(required_tag_ids),
            func.count(distinct(User.xid)) <= size - seats,
        ]
        if power:
            having_filters.append(between(func.avg(User.power), power - 1, power + 1))
        else:
            select_filters.append(User.power == None)
        inner = (
            session.query(Game.id)
            .join(User, isouter=True)
            .join(games_tags, isouter=True)
            .filter(and_(*select_filters))
            .group_by(Game.id)
            .having(and_(*having_filters))
        )
        tag_filters = []
        for tid in required_tag_ids:
            tag_filters.append(games_tags.c.tag_id == tid)
        outer = (
            session.query(Game)
            .join(games_tags, isouter=True)
            .filter(and_(Game.id.in_(inner), or_(*tag_filters)))
            .group_by(Game.id)
            .having(having_filters[0])
            .order_by(desc(Game.updated_at))
        )
        game: Optional[Game] = outer.first()
        return game

    @classmethod
    def expired(cls, session: Session) -> List[Game]:
        return cast(
            List[Game],
            session.query(Game)
            .filter(
                and_(
                    datetime.utcnow() >= Game.expires_at,
                    Game.url == None,
                    Game.status != "ready",
                )
            )
            .all(),
        )

    def __repr__(self) -> str:
        return json.dumps(self.to_json())

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "created_at": str(self.created_at),
            "updated_at": str(self.updated_at),
            "expires_at": str(self.expires_at),
            "size": self.size,
            "guild_xid": self.guild_xid,
            "channel_xid": self.channel_xid,
            "url": self.url,
            "status": self.status,
            "system": self.system,
            "message": self.message,
            "message_xid": self.message_xid,
            "tags": [tag.name for tag in self.tags],
            "power": self.power,
        }

    def to_embed(self, dm=False) -> discord.Embed:
        show_link = True if dm else self.server.links == "public"
        if self.status == "pending":
            remaining = int(self.size) - len(cast(List[User], self.users))
            plural = "s" if remaining > 1 else ""
            title = f"**Waiting for {remaining} more player{plural} to join...**"
        else:
            title = self.message if self.message else "**Your game is ready!**"
        embed = discord.Embed(title=title)
        embed.set_thumbnail(url=THUMB_URL)
        if self.status == "pending":
            embed.description = "To join/leave this game, react with ➕/➖."
        elif self.system == "spelltable":
            if show_link:
                assert self.url is not None  # TODO: Shouldn't be possible?
                embed.description = (
                    f"Click the link below to join your SpellTable game.\n<{self.url}>"
                )
            else:
                embed.description = (
                    "Please check your Direct Messages for your SpellTable link."
                )
        elif self.system == "mtgo":
            embed.description = (
                "Please exchange MTGO contact information and head over there to play!"
            )
        else:  # self.system == "arena"
            embed.description = (
                "Please exchange Arena contact information and head over there to play!"
            )
        tag_names = None
        if self.tags and len(cast(List[Tag], self.tags)) >= 1:
            sorted_tag_names: List[str] = sorted([tag.name for tag in self.tags])
            tag_names = ", ".join(sorted_tag_names)
            embed.add_field(name="Tags", value=tag_names)
        power = self.power
        if power:
            embed.add_field(name="Average Power Level", value=f"{power:.1f}")
        if self.users:
            players = ", ".join(
                sorted(
                    [
                        f"<@{user.xid}>"
                        + (f" (Power: {user.power})" if user.power else "")
                        for user in self.users
                    ]
                )
            )
            embed.add_field(name="Players", value=players, inline=False)
        embed.set_footer(text=f"SpellBot Reference #SB{self.id}")
        embed.color = discord.Color(0x5A3EFD)
        return embed


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    game_id = Column(
        Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    game = relationship("Game", back_populates="reports")


def create_all(connection: Connection, db_url: str) -> None:
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(VERSIONS_DIR))
    config.set_main_option("sqlalchemy.url", db_url)
    cast(Any, config.attributes)["connection"] = connection
    alembic.command.upgrade(config, "head")


def reverse_all(connection: Connection, db_url: str) -> None:
    config = alembic.config.Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(VERSIONS_DIR))
    config.set_main_option("sqlalchemy.url", db_url)
    cast(Any, config.attributes)["connection"] = connection
    alembic.command.downgrade(config, "base")


class Data:
    """Persistent and in-memory store for user data."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=False)
        self.conn = self.engine.connect()
        create_all(self.conn, db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = Base.metadata
