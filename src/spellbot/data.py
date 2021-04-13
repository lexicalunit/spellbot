from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

import alembic  # type: ignore
import alembic.command  # type: ignore
import alembic.config  # type: ignore
import discord
import humanize  # type: ignore
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    and_,
    between,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy import create_engine, false, func, or_, text, true
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # type: ignore
from sqlalchemy.future import select  # type: ignore
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql.expression import asc, desc, distinct
from sqlalchemy.sql.schema import UniqueConstraint
from sqlalchemy.sql.sqltypes import Numeric

from spellbot.constants import (
    EMOJI_DROP_GAME,
    EMOJI_JOIN_GAME,
    THUMB_URL,
    VOICE_INVITE_EXPIRE_TIME_S,
)

PACKAGE_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_ROOT / "assets"
ALEMBIC_INI = ASSETS_DIR / "alembic.ini"
VERSIONS_DIR = PACKAGE_ROOT / "versions"

logger = logging.getLogger(__name__)
Base = declarative_base()


class Server(Base):
    __tablename__ = "servers"
    guild_xid = Column(BigInteger, primary_key=True, nullable=False)
    cached_name = Column(String(50))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    prefix = Column(String(10), nullable=False, default="!")
    expire = Column(Integer, nullable=False, server_default=text("30"))  # minutes
    links = Column(String(10), nullable=False, server_default=text("'public'"))
    show_spectate_link = Column(Boolean, nullable=False, server_default=false())
    motd = Column(String(10), nullable=False, server_default=text("'both'"))
    power_enabled = Column(Boolean, nullable=False, server_default=true())
    tags_enabled = Column(Boolean, nullable=False, server_default=true())
    queue_time_enabled = Column(Boolean, nullable=False, server_default=true())
    create_voice = Column(Boolean, nullable=False, server_default=false())
    smotd = Column(String(255))
    voice_category_prefix = Column(String(40))
    games = relationship("Game", back_populates="server", uselist=True, lazy="selectin")
    channels = relationship(
        "Channel", back_populates="server", uselist=True, lazy="selectin"
    )
    auto_verify_channels = relationship(
        "AutoVerifyChannel", back_populates="server", uselist=True, lazy="selectin"
    )
    unverified_only_channels = relationship(
        "UnverifiedOnlyChannel", back_populates="server", uselist=True, lazy="selectin"
    )
    channel_settings = relationship(
        "ChannelSettings", back_populates="server", uselist=True, lazy="selectin"
    )
    teams = relationship("Team", back_populates="server", uselist=True, lazy="selectin")

    def bot_allowed_in(self, channel_xid: int) -> bool:
        return not self.channels or any(
            channel.channel_xid == channel_xid for channel in self.channels
        )

    def channel_settings_for(self, channel_xid: int) -> Optional[ChannelSettings]:
        return next(
            (s for s in self.channel_settings if s.channel_xid == channel_xid), None
        )

    @classmethod
    async def recent_metrics(cls, session: AsyncSession) -> dict:
        data = [
            row[1]
            for row in (
                (
                    await session.execute(
                        select(
                            func.date(Server.created_at).label("day"),
                            func.count(Server.guild_xid),
                        )
                        .filter(
                            Server.created_at >= datetime.utcnow() - timedelta(days=5),
                        )
                        .group_by("day")
                        .order_by(desc("day"))
                    )
                ).all()
            )
        ]
        return {f"servers_{i}": count for i, count in enumerate(data)}

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
                "show_spectate_link": self.show_spectate_link,
                # "channels": [channel.channel_xid for channel in self.channels],
                # "teams": [team.name for team in self.teams],
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
    server = relationship("Server", back_populates="teams", lazy="selectin")

    @classmethod
    async def points(cls, session: AsyncSession, guild_xid: int) -> dict:
        rows = (
            await session.query(Team.name, func.sum(UserPoints.points))
            .select_from(User)
            .join(UserServerSettings)
            .join(UserPoints)
            .join(Team)
            .filter(Team.guild_xid == guild_xid)
            .group_by(Team.name)
            .all()
        )
        server = (
            await session.query(Server)
            .filter(Server.guild_xid == guild_xid)
            .one_or_none()
        )
        assert server
        results = {team.name: 0 for team in server.teams}
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
    server = relationship("Server", back_populates="channels", lazy="selectin")


class AutoVerifyChannel(Base):
    __tablename__ = "auto_verify_channels"
    channel_xid = Column(BigInteger, primary_key=True, nullable=False)
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server = relationship(
        "Server", back_populates="auto_verify_channels", lazy="selectin"
    )


class UnverifiedOnlyChannel(Base):
    __tablename__ = "unverified_only_channels"
    channel_xid = Column(BigInteger, primary_key=True, nullable=False)
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server = relationship(
        "Server", back_populates="unverified_only_channels", lazy="selectin"
    )


class ChannelSettings(Base):
    __tablename__ = "channel_settings"
    channel_xid = Column(BigInteger, primary_key=True, nullable=False)
    guild_xid = Column(
        BigInteger,
        ForeignKey("servers.guild_xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cached_name = Column(String(50))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    default_size = Column(Integer, nullable=True)
    require_verification = Column(Boolean, nullable=False, server_default=false())
    cmotd = Column(String(255))
    verify_message = Column(String(255))
    tags_enabled = Column(Boolean, nullable=True)  # overrides server setting
    queue_time_enabled = Column(Boolean, nullable=True)  # overrides server setting
    server = relationship("Server", back_populates="channel_settings", lazy="selectin")


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
    games = relationship("Game", back_populates="event", uselist=True, lazy="selectin")

    @property
    def started(self) -> bool:
        return any(game.status == "started" for game in self.games)

    def __repr__(self) -> str:
        return json.dumps({"id": self.id})


users_blocks = Table(
    "users_blocks",
    Base.metadata,
    Column(
        "user_xid",
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    ),
    Column(
        "blocked_user_xid",
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    ),
    UniqueConstraint("user_xid", "blocked_user_xid", name="uix_1"),
)


class User(Base):
    __tablename__ = "users"
    xid = Column(BigInteger, primary_key=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    game_id = Column(
        Integer, ForeignKey("games.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cached_name = Column(String(50))
    power = Column(Integer, nullable=True)
    banned = Column(Boolean, nullable=False, server_default=false())
    game = relationship("Game", back_populates="users", lazy="selectin")

    blocks = relationship(
        "User",
        secondary=users_blocks,
        primaryjoin=xid == users_blocks.c.user_xid,
        secondaryjoin=xid == users_blocks.c.blocked_user_xid,
        backref="blocked_by",
        lazy="selectin",
    )

    async def blocked(self, session: AsyncSession, game: Game) -> bool:
        other_user_xids = [u.xid for u in game.users]

        query = select(users_blocks).filter(
            or_(
                and_(
                    users_blocks.c.user_xid == self.xid,
                    users_blocks.c.blocked_user_xid.in_(other_user_xids),
                ),
                and_(
                    users_blocks.c.blocked_user_xid == self.xid,
                    users_blocks.c.user_xid.in_(other_user_xids),
                ),
            )
        )

        result = await session.execute(query)
        return result.scalar() is not None

    @classmethod
    async def recent_metrics(cls, session: AsyncSession) -> dict:
        data = [
            row[1]
            for row in (
                await session.query(
                    func.date(User.created_at).label("day"),
                    func.count(User.xid),
                )
                .filter(
                    User.created_at >= datetime.utcnow() - timedelta(days=5),
                )
                .group_by("day")
                .order_by(desc("day"))
                .all()
            )
        ]
        return {f"users_{i}": count for i, count in enumerate(data)}

    @property
    def waiting(self) -> bool:
        if self.game and self.game.status in ["pending", "ready"]:
            return True
        return False

    async def points(self, session: AsyncSession, guild_xid: int) -> int:
        filters = and_(UserPoints.user_xid == self.xid, UserPoints.guild_xid == guild_xid)
        results = (
            await session.query(func.sum(UserPoints.points)).filter(filters).scalar()
        )
        return results or 0

    def to_json(self) -> dict:
        return {
            "cached_name": self.cached_name,
            "created_at": str(self.created_at),
            "game_id": self.game_id,
            "power": self.power,
            "xid": self.xid,
        }


class UserServerSettings(Base):
    __tablename__ = "user_server_settings"
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
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    # verified = Column(Boolean, nullable=True, server_default=false())
    verified = Column(Boolean, nullable=True, default=False, server_default=false())


class WatchedUser(Base):
    __tablename__ = "watched_users"
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
    note = Column(String(255))


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
        "Game", secondary=games_tags, back_populates="tags", uselist=True, lazy="selectin"
    )

    @classmethod
    async def create_many(cls, session: AsyncSession, tag_names: List[str]) -> List[Tag]:
        created_at_least_one = False
        tags = []
        for tag_name in tag_names:
            tag = await session.query(Tag).filter_by(name=tag_name).one_or_none()
            if not tag:
                created_at_least_one = True
                tag = Tag(name=tag_name)
                session.add(tag)
            tags.append(tag)
        if created_at_least_one:
            await session.commit()
        return tags


class Play(Base):
    __tablename__ = "plays"
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )


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
    note = Column(String(255))
    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_xid = Column(BigInteger)
    system = Column(
        String(30), nullable=False, server_default=text("'spelltable'"), index=True
    )
    game_power = Column(Float, nullable=True)
    voice_channel_xid = Column(BigInteger, nullable=True, index=True)
    voice_channel_invite = Column(String(255))
    users = relationship("User", back_populates="game", uselist=True, lazy="selectin")
    tags = relationship(
        "Tag", secondary=games_tags, back_populates="games", uselist=True, lazy="selectin"
    )
    server = relationship("Server", back_populates="games", lazy="selectin")
    event = relationship("Event", back_populates="games", lazy="selectin")
    reports = relationship("Report", back_populates="game", uselist=True, lazy="selectin")

    @classmethod
    async def games_per_day(cls, session: AsyncSession) -> Iterable[Tuple[datetime, int]]:
        return cast(
            Iterable[Tuple[datetime, int]],
            await session.query(
                func.date(Game.created_at).label("day"),
                func.count(Game.id),
            )
            .filter(
                and_(
                    Game.status == "started",
                    Game.created_at >= datetime.utcnow() - timedelta(days=5),
                )
            )
            .group_by("day")
            .order_by(desc("day"))
            .all(),
        )

    @classmethod
    async def games_per_day_per_channel(
        cls, session: AsyncSession, guild_xid: int
    ) -> Iterable[Tuple[datetime, int, int]]:
        filters = [
            Game.status == "started",
            Game.guild_xid == guild_xid,
        ]
        return cast(
            Iterable[Tuple[datetime, int, int]],
            await session.query(
                func.date(Game.created_at).label("day"),
                Game.channel_xid,
                func.count(Game.id),
            )
            .filter(and_(*filters))
            .group_by("day", Game.channel_xid)
            .order_by(desc("day"), Game.channel_xid)
            .all(),
        )

    @classmethod
    async def recent_metrics(cls, session: AsyncSession) -> dict:
        data = [row[1] for row in await cls.games_per_day(session)]
        return {f"games_{i}": count for i, count in enumerate(data)}

    @property
    def power(self) -> Optional[float]:
        if not self.server.power_enabled:
            return None
        values: List[int] = [user.power for user in self.users if user.power]
        if values:
            return sum(values) / len(values)
        return None

    @classmethod
    async def find_existing(
        cls,
        *,
        session: AsyncSession,
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
            Game.message_xid.isnot(None),
        ]
        having_filters = [
            func.count(distinct(games_tags.c.tag_id)) == len(required_tag_ids),
            func.count(distinct(User.xid)) <= size - seats,
        ]
        if server.power_enabled:
            if power:
                having_filters.append(between(func.avg(User.power), power - 1, power + 1))
                if power >= 7:
                    having_filters.append(func.avg(User.power) >= 7)
                else:
                    having_filters.append(func.avg(User.power) < 7)
            else:
                select_filters.append(User.power.is_(None))
        inner = (
            (
                await session.execute(
                    select(Game.id)
                    .select_from(Game)
                    .join(User, isouter=True)
                    .join(games_tags, isouter=True)
                    .filter(and_(*select_filters))
                    .group_by(Game.id)
                    .having(and_(*having_filters))
                )
            )
            .scalars()
            .all()
        )
        tag_filters = []
        for tid in required_tag_ids:
            tag_filters.append(games_tags.c.tag_id == tid)
        outer = await session.execute(
            select(Game)
            .join(games_tags, isouter=True)
            .filter(and_(Game.id.in_(inner), or_(*tag_filters)))
            .group_by(Game.id)
            .having(having_filters[0])
            .order_by(asc(Game.updated_at))
        )
        game: Optional[Game] = outer.first()[Game]
        return game

    @classmethod
    async def expired(cls, session: AsyncSession) -> List[Game]:
        return cast(
            List[Game],
            await session.execute(
                select(Game).filter(
                    and_(
                        datetime.utcnow() >= Game.expires_at,
                        Game.status == "pending",
                    )
                )
            ).all(),
        )

    def is_expired(self) -> bool:
        if (
            self.status == "pending"
            and self.expires_at
            and datetime.utcnow() >= self.expires_at
        ):
            return True
        return False

    @classmethod
    async def voiced(cls, session: AsyncSession) -> List[Game]:
        return cast(
            List[Game],
            await session.execute(
                select(Game).filter(
                    and_(
                        Game.voice_channel_xid.isnot(None),
                        datetime.utcnow() - timedelta(minutes=10) >= Game.updated_at,
                    )
                )
            ).all(),
        )

    @classmethod
    async def average_wait_times(cls, session: AsyncSession):
        # if "sqlite" in session.bind.dialect.name:  # pragma: no cover
        #     avg = func.avg(
        #         (func.julianday(Game.updated_at) - func.julianday(Game.created_at))
        #         * 1440.0
        #     )
        # else:  # pragma: no cover
        avg = (
            sql_cast(
                func.avg(
                    text("EXTRACT(EPOCH FROM(games.updated_at - games.created_at))")
                ),
                Numeric,
            )
            / 60.0
        )
        return (
            await session.query(
                Game.guild_xid,
                Game.channel_xid,
                avg,
            )
            .filter(
                and_(
                    Game.created_at >= datetime.utcnow() - timedelta(hours=1),
                    Game.status == "started",
                    Game.channel_xid.isnot(None),
                )
            )
            .group_by(Game.guild_xid, Game.channel_xid)
            .all()
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
            "note": self.note,
            "message_xid": self.message_xid,
            "voice_channel_xid": self.voice_channel_xid,
            "voice_channel_invite": self.voice_channel_invite,
            "tags": [tag.name for tag in self.tags],
            "event_id": self.event.id if self.event else None,
            "power": self.power,
        }

    def to_embed(self, dm: bool = False, wait: Optional[float] = None) -> discord.Embed:
        prefix = self.server.prefix
        show_motd = (
            True
            if self.server.motd == "both"
            else True
            if dm and self.server.motd == "private"
            else True
            if not dm and self.server.motd == "public"
            else False
        )
        show_link = True if dm else self.server.links == "public"
        if self.status == "pending":
            remaining = int(self.size) - len(cast(List[User], self.users))
            plural = "s" if remaining > 1 else ""
            title = f"**Waiting for {remaining} more player{plural} to join...**"
        else:
            title = self.message if self.message else "**Your game is ready!**"
        embed = discord.Embed(title=title)
        embed.set_thumbnail(url=THUMB_URL)

        description = ""
        if self.voice_channel_invite:
            if show_link:
                description = (
                    f"Join your voice chat now: {self.voice_channel_invite} (invite"
                    f" expires in {int(VOICE_INVITE_EXPIRE_TIME_S / 60)} minutes)\n\n"
                )
        if self.status == "pending":
            description += (
                f"To **join this game**, react with {EMOJI_JOIN_GAME}\n"
                f"If you need to drop, react with {EMOJI_DROP_GAME}\n\n"
                "_A SpellTable link will be created when all players have selectin._\n\n"
                f"Looking for more players to join you? Just run `{prefix}lfg` again.\n"
            )
        elif self.system == "spelltable":
            if show_link:
                if self.url:
                    description += (
                        "Click the link below to join your SpellTable game."
                        f"\n<{self.url}>"
                    )
                    if self.server.show_spectate_link:
                        description += (
                            "\nOr spectate on the game with the following link."
                            f"\n<{self.url}?spectate>"
                        )
                else:
                    description += (
                        "Sorry but SpellBot was unable to create a SpellTable link"
                        " for this game. Please go to"
                        " [spelltable.com](https://www.spelltable.com/) to create one.\n"
                    )
            else:
                description += (
                    "Please check your Direct Messages for your SpellTable link."
                )
        elif self.system == "mtgo":
            description += (
                "Please exchange MTGO contact information and head over there to play!"
            )
        else:  # self.system == "arena"
            description += (
                "Please exchange Arena contact information and head over there to play!"
            )
        if self.channel_xid:
            channel_settings = self.server.channel_settings_for(self.channel_xid)
            if channel_settings and channel_settings.cmotd:
                description += f"\n{channel_settings.cmotd}"
        if self.server.smotd and show_motd:
            description += f"\n{self.server.smotd}"
        embed.description = description

        if self.voice_channel_xid:
            embed.add_field(name="Voice Channel", value=f"<#{self.voice_channel_xid}>")
        tag_names = None
        if self.tags and len(cast(List[Tag], self.tags)) >= 1:
            sorted_tag_names: List[str] = sorted([tag.name for tag in self.tags])
            tag_names = ", ".join(sorted_tag_names)
            embed.add_field(name="Tags", value=tag_names)
        power = self.power
        if power and self.server.power_enabled:
            embed.add_field(name="Average Power Level", value=f"{power:.1f}")
        if wait:
            delta = timedelta(minutes=wait)
            mins = humanize.precisedelta(delta, minimum_unit="seconds", format="%0.0f")
            embed.add_field(name="Average Queue Time", value=mins)
        if self.users:
            players = ", ".join(
                sorted(
                    [
                        f"<@{user.xid}>"  # Support <@!USERID> for server nick?
                        + (
                            f" (Power: {user.power})"
                            if (user.power and self.server.power_enabled)
                            else ""
                        )
                        for user in self.users
                    ]
                )
            )
            embed.add_field(name="Players", value=players, inline=False)

        if self.note:
            embed.add_field(name="Note", value=self.note, inline=False)

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
    game = relationship("Game", back_populates="reports", lazy="selectin")


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


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    kind = Column(String(50), index=True)
    guild_xid = Column(BigInteger, index=True)
    channel_xid = Column(BigInteger, index=True)
    user_xid = Column(BigInteger, index=True)


class Data:
    """Persistent and in-memory store for user data."""

    def __init__(self, db_url: str):
        assert "postgres" in db_url, "SpellBot only supports postgresql database"

        self.db_url = db_url
        self.metadata = Base.metadata

        # init database tables
        sync_engine = create_engine(self.db_url, echo=False)
        sync_conn = sync_engine.connect()
        create_all(sync_conn, self.db_url)
        sync_conn.close()

        # setup app async connection
        self.db_url = self.db_url.replace(":", "+asyncpg:", 1)
        self.engine = create_async_engine(
            self.db_url, future=True, echo=False, connect_args={"ssl": "disable"}
        )
        self.conn = self.engine.connect()
        self.Session = sessionmaker(
            bind=self.engine, expire_on_commit=False, future=True, class_=AsyncSession
        )
