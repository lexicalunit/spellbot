from __future__ import annotations

from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional, cast

import discord
from dateutil import tz
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text

from ..enums import GameFormat
from ..settings import Settings
from . import Base, now

if TYPE_CHECKING:  # pragma: no cover
    from . import Channel, Guild, User  # noqa


class GameStatus(Enum):
    PENDING = auto()
    STARTED = auto()


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
    message_xid = Column(
        BigInteger,
        index=True,
        nullable=True,
        doc="The external Discord ID of the messsage where this game's embed is found",
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
    spelltable_link = Column(
        String(255),
        doc="The generated SpellTable link for this game",
    )
    voice_invite_link = Column(
        String(255),
        doc="The generate voice channel invite link for this game",
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
        from ..database import DatabaseSession
        from . import User

        return DatabaseSession.query(User).filter(User.xid.in_(self.player_xids)).all()

    @property
    def player_xids(self) -> list[int]:
        from ..database import DatabaseSession
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

    def show_links(self, dm: bool = False) -> bool:
        return True if dm else self.guild.show_links

    @property
    def embed_title(self) -> str:
        if self.status == GameStatus.STARTED.value:
            return "**Your game is ready!**"
        remaining = int(cast(int, self.seats)) - len(self.players)
        plural = "s" if remaining > 1 else ""
        return f"**Waiting for {remaining} more player{plural} to join...**"

    def embed_description(self, dm: bool = False) -> str:
        description = ""
        if self.status == GameStatus.PENDING.value:
            description += "_A SpellTable link will be created when all players have joined._"
        else:
            if self.show_links(dm):
                if self.spelltable_link:
                    description += (
                        f"[Join your SpellTable game now!]({self.spelltable_link})"
                        f" (or [spectate this game]({self.spectate_link}))"
                    )
                else:
                    description += (
                        "Sorry but SpellBot was unable to create a SpellTable link"
                        " for this game. Please go to [SpellTable]"
                        "(https://spelltable.wizards.com/) to create one."
                    )
                if self.voice_xid:
                    description += f"\n\nJoin your voice chat now: <#{self.voice_xid}>"
            else:
                description += "Please check your Direct Messages for your SpellTable link."
            if dm:
                description += (
                    "\n\nYou can also [jump to the original game post]"
                    f"({self.jump_link}) in <#{self.channel_xid}>."
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
        if self.started_at:
            game_start = f"<t:{self.started_at_timestamp}>"
        else:
            game_start = "pending"
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
        player_strs: list[str] = []
        for player in self.players:
            points_str = ""
            if self.status == GameStatus.STARTED.value:
                points = player.points(cast(int, self.id))
                if points:
                    points_str = f" ({points} point{'s' if points > 1 else ''})"

            power_level_str = ""
            if self.status == GameStatus.PENDING.value:
                config = player.config(cast(int, self.guild_xid)) or {}
                power_level = config.get("power_level", None)
                if power_level:
                    power_level_str = f" (power level: {power_level})"

            player_strs.append(f"<@{player.xid}>{power_level_str}{points_str}")
        return ", ".join(sorted(player_strs))

    @property
    def embed_footer(self) -> str:
        return f"SpellBot Game ID: #SB{self.id}"

    @property
    def spectate_link(self) -> Optional[str]:
        return f"{self.spelltable_link}?spectate=true" if self.spelltable_link else None

    @property
    def jump_link(self) -> str:
        guild = self.guild_xid
        channel = self.channel_xid
        message = self.message_xid
        return f"https://discordapp.com/channels/{guild}/{channel}/{message}"

    @property
    def format_name(self) -> str:
        format = GameFormat(self.format)  # type: ignore
        return format.name.replace("_", " ").title()

    def to_embed(self, dm: bool = False) -> discord.Embed:
        settings = Settings(self.guild_xid)  # type: ignore
        embed = discord.Embed(title=self.embed_title)
        embed.set_thumbnail(url=settings.THUMB_URL)
        embed.description = self.embed_description(dm)
        if self.players:
            embed.add_field(name="Players", value=self.embed_players, inline=False)
        embed.add_field(name="Format", value=self.format_name)
        if self.started_at:
            embed.add_field(name="Started at", value=f"<t:{self.started_at_timestamp}>")
        embed.set_footer(text=self.embed_footer)
        embed.color = discord.Color(settings.EMBED_COLOR)
        return embed

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "deleted_at": self.deleted_at,
            "guild_xid": self.guild_xid,
            "channel_xid": self.channel_xid,
            "message_xid": self.message_xid,
            "voice_xid": self.voice_xid,
            "seats": self.seats,
            "status": self.status,
            "format": self.format,
            "spelltable_link": self.spelltable_link,
            "spectate_link": self.spectate_link,
            "jump_link": self.jump_link,
        }
