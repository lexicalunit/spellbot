from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, TypedDict, cast

import discord
from dateutil import tz
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false, text

from spellbot.enums import GameFormat, GameService
from spellbot.settings import settings

from . import Base, now

if TYPE_CHECKING:
    from . import Channel, Guild, Post, PostDict, User  # noqa: F401


class GameStatus(Enum):
    PENDING = auto()
    STARTED = auto()


class GameDict(TypedDict):
    id: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    deleted_at: datetime | None
    guild_xid: int
    channel_xid: int
    posts: list[PostDict]
    voice_xid: int | None
    voice_invite_link: str | None
    seats: int
    status: int
    format: int
    service: int
    spelltable_link: str | None
    spectate_link: str | None
    jump_links: dict[int, str]
    confirmed: bool
    requires_confirmation: bool
    password: str | None


@dataclass
class GameLinkDetails:
    link: str | None = None
    password: str | None = None


class Game(Base):
    """Represents a pending or started SpellTable game."""

    __tablename__ = "games"

    id = Column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The SpellBot game reference ID",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this games was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
        index=True,
        doc="UTC timestamp when this games was last updated",
    )
    started_at = Column(
        DateTime,
        nullable=True,
        doc="UTC timestamp when this games was started",
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this games was deleted",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel_xid: int = cast(
        int,
        Column(
            BigInteger,
            ForeignKey("channels.xid", ondelete="CASCADE"),
            index=True,
            nullable=False,
            doc="The external Discord ID of the associated channel",
        ),
    )
    voice_xid = Column(
        BigInteger,
        index=True,
        nullable=True,
        doc="The external Discord ID of an associated voice channel",
    )
    seats: int = cast(
        int,
        Column(
            Integer,
            index=True,
            nullable=False,
            doc="The number of seats (open or occupied) available at this game",
        ),
    )
    status: int = cast(
        int,
        Column(
            Integer(),
            default=GameStatus.PENDING.value,
            server_default=text(str(GameStatus.PENDING.value)),
            index=True,
            nullable=False,
            doc="Pending or started status of this game",
        ),
    )
    format: int = cast(
        int,
        Column(
            Integer(),
            default=GameFormat.COMMANDER.value,
            server_default=text(str(GameFormat.COMMANDER.value)),
            index=True,
            nullable=False,
            doc="The Magic: The Gathering format for this game",
        ),
    )
    service: int = cast(
        int,
        Column(
            Integer(),
            default=GameService.SPELLTABLE.value,
            server_default=text(str(GameService.SPELLTABLE.value)),
            index=True,
            nullable=False,
            doc="The service that will be used to create this game",
        ),
    )
    spelltable_link = Column(String(255), doc="The generated SpellTable link for this game")
    password = Column(String(255), nullable=True, doc="The password for this game")
    voice_invite_link = Column(String(255), doc="The voice channel invite link for this game")
    requires_confirmation = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for requiring confirmation on points reporting",
    )

    posts = relationship(
        "Post",
        back_populates="game",
        uselist=True,
        doc="The posts associated with this game",
    )
    guild = relationship(
        "Guild",
        back_populates="games",
        doc="The guild this game was created in",
    )
    channel = relationship(
        "Channel",
        back_populates="games",
        doc="The channel this game was created in",
    )

    @property
    def players(self) -> list[User]:
        from spellbot.database import DatabaseSession

        from . import User

        return DatabaseSession.query(User).filter(User.xid.in_(self.player_xids)).all()

    @property
    def player_xids(self) -> list[int]:
        from spellbot.database import DatabaseSession

        from . import Play, Queue

        if self.started_at is None:
            rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == self.id)
        else:
            rows = DatabaseSession.query(Play.user_xid).filter(Play.game_id == self.id)
        return [int(row[0]) for row in rows]

    @property
    def started_at_timestamp(self) -> int:
        assert self.started_at is not None
        return int(cast(datetime, self.started_at).replace(tzinfo=tz.UTC).timestamp())

    @property
    def updated_at_timestamp(self) -> int:
        assert self.updated_at is not None
        return int(cast(datetime, self.updated_at).replace(tzinfo=tz.UTC).timestamp())

    def show_links(self, dm: bool = False) -> bool:
        return True if dm else self.guild.show_links

    @property
    def embed_title(self) -> str:
        if self.status == GameStatus.STARTED.value:
            return "**Your game is ready!**"
        remaining = int(cast(int, self.seats)) - len(self.players)
        plural = "s" if remaining > 1 else ""
        return f"**Waiting for {remaining} more player{plural} to join...**"

    def embed_description(self, dm: bool = False) -> str:  # noqa: C901,PLR0912
        description = ""
        if self.guild.notice:
            description += f"{self.guild.notice}\n\n"
        if self.status == GameStatus.PENDING.value:
            if self.service == GameService.SPELLTABLE.value:
                description += "_A SpellTable link will be created when all players have joined._"
            elif self.service == GameService.TABLE_STREAM.value:
                description += "_A Table Stream link will be created when all players have joined._"
            elif self.service == GameService.NOT_ANY.value:
                description += "_Please contact the players in your game to organize this game._"
            else:
                description += f"_Please use {GameService(self.service)} for this game._"
        else:
            if self.show_links(dm):
                if self.spelltable_link:
                    description += (
                        f"[Join your {GameService(self.service)} game now!]({self.spelltable_link})"
                    )
                    if self.service == GameService.SPELLTABLE.value:
                        description += f" (or [spectate this game]({self.spectate_link}))"
                elif self.service == GameService.SPELLTABLE.value:
                    description += (
                        "Sorry but SpellBot was unable to create a SpellTable link"
                        " for this game. Please go to [SpellTable]"
                        "(https://spelltable.wizards.com/) to create one."
                    )
                elif self.service == GameService.TABLE_STREAM.value:
                    description += (
                        "Sorry but SpellBot was unable to create a Table Stream link"
                        " for this game. Please go to [Table Stream]"
                        "(https://table-stream.com/) to create one."
                    )
                elif self.service != GameService.NOT_ANY.value:
                    description += f"Please use {GameService(self.service)} to play this game."
                else:
                    description += "Contact the other players in your game to organize this match."
                if self.password:
                    description += f"\n\nPassword: `{self.password}`"
                if self.voice_xid:
                    description += f"\n\nJoin your voice chat now: <#{self.voice_xid}>"
                if self.voice_invite_link:
                    description += f"\nOr use this voice channel invite: {self.voice_invite_link}"
            else:
                description += "Please check your Direct Messages for your game details."
            if dm:
                jump_link = next(iter(self.jump_links.values()))
                description += (
                    "\n\nYou can also [jump to the original game post]"
                    f"({jump_link}) in <#{self.channel_xid}>."
                )
            elif self.channel.show_points:
                description += "\n\nWhen your game is over use the drop down to report your points."
        placeholders = self.placeholders
        if self.guild.motd:
            description += f"\n\n{self.apply_placeholders(placeholders, self.guild.motd)}"
        if self.channel.motd:
            description += f"\n\n{self.apply_placeholders(placeholders, self.channel.motd)}"
        return description

    @property
    def placeholders(self) -> dict[str, str]:
        game_start = f"<t:{self.started_at_timestamp}>" if self.started_at else "pending"
        placeholders = {
            "game_id": str(self.id),
            "game_format": self.format_name,
            "game_start": game_start,
        }
        for i, player in enumerate(self.players):
            placeholders[f"player_name_{i+1}"] = cast(str, player.name)
        return placeholders

    def apply_placeholders(self, placeholders: dict[str, str], text: str) -> str:
        for k, v in placeholders.items():
            text = text.replace(f"${{{k}}}", v)
        return text

    @property
    def embed_players(self) -> str:
        player_parts: list[tuple[str, int, str, str]] = []
        for player in self.players:
            points_str = ""
            if self.status == GameStatus.STARTED.value:
                points = player.points(cast(int, self.id))
                if points is not None and points[0] is not None:
                    points_value: int = points[0]
                    points_confirmed: bool = points[1]
                    plural_str = "s" if points_value > 1 or points_value == 0 else ""
                    if self.requires_confirmation:
                        if points_value == 3:
                            value_str = "WIN"
                        elif 1 <= points_value <= 2:
                            value_str = "TIE"
                        else:
                            value_str = "LOSS"
                    else:
                        value_str = f"{points_value} point{plural_str}"
                    confirmed_str = (
                        "✅ "
                        if points_confirmed
                        else "❌ "
                        if self.channel.require_confirmation
                        else ""
                    )
                    points_str = f"\n**ﾠ⮑ {confirmed_str}{value_str}**"

            elo = player.elo(self.guild_xid, self.channel_xid)
            elo_str = f"**ELO {elo}** - " if elo else ""
            player_parts.append((elo_str, player.xid, player.name, points_str))

        player_strs: list[str] = [
            f"• {parts[0]}<@{parts[1]}> ({parts[2]}){parts[3]}" for parts in sorted(player_parts)
        ]
        return "\n".join(player_strs)

    @property
    def embed_footer(self) -> str:
        return f"SpellBot Game ID: #SB{self.id}"

    @property
    def spectate_link(self) -> str | None:
        return f"{self.spelltable_link}?spectate=true" if self.spelltable_link else None

    @property
    def jump_links(self) -> dict[int, str]:
        return {post.guild_xid: post.jump_link for post in self.posts or []}

    @property
    def format_name(self) -> str:
        return str(GameFormat(self.format))

    @property
    def confirmed(self) -> bool:
        from spellbot.database import DatabaseSession

        from . import Play, User

        player_count = DatabaseSession.query(User).filter(User.xid.in_(self.player_xids)).count()
        confirmed_count = (
            DatabaseSession.query(Play)
            .filter(
                Play.game_id == self.id,
                ~Play.confirmed_at.is_(None),
            )
            .count()
        )
        return player_count == confirmed_count

    def to_embed(self, dm: bool = False) -> discord.Embed:
        embed = discord.Embed(title=self.embed_title)
        embed.set_thumbnail(
            url=settings.QUEER_THUMB_URL if settings.queer(self.guild_xid) else settings.THUMB_URL
        )
        embed.description = self.embed_description(dm)
        if self.players:
            embed.add_field(name="Players", value=self.embed_players, inline=False)
        embed.add_field(name="Format", value=self.format_name)
        if self.started_at:
            embed.add_field(name="Started at", value=f"<t:{self.started_at_timestamp}>")
        else:
            embed.add_field(name="Updated at", value=f"<t:{self.updated_at_timestamp}>")
        if self.service != GameService.SPELLTABLE.value:
            embed.add_field(
                name="Service",
                value=str(GameService(self.service)),
                inline=False,
            )
        if self.players:
            embed.color = (
                discord.Color(settings.STARTED_EMBED_COLOR)
                if self.started_at
                else discord.Color(settings.PENDING_EMBED_COLOR)
            )
        else:
            embed.color = discord.Color(settings.EMPTY_EMBED_COLOR)
        embed.add_field(
            name="Support SpellBot",
            value=(
                f"Become [a monthly patron]({settings.SUBSCRIBE_LINK}) or "
                f"give a [one-off tip]({settings.DONATE_LINK})."
            ),
            inline=False,
        )
        embed.set_footer(text=self.embed_footer)
        return embed

    def to_dict(self) -> GameDict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "deleted_at": self.deleted_at,
            "guild_xid": self.guild_xid,
            "channel_xid": self.channel_xid,
            "posts": [post.to_dict() for post in self.posts],
            "voice_xid": self.voice_xid,
            "voice_invite_link": self.voice_invite_link,
            "seats": self.seats,
            "status": self.status,
            "format": self.format,
            "service": self.service,
            "spelltable_link": self.spelltable_link,
            "spectate_link": self.spectate_link,
            "jump_links": self.jump_links,
            "confirmed": self.confirmed,
            "requires_confirmation": self.channel.require_confirmation,
            "password": self.password,
        }
