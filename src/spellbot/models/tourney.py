from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import discord
from dateutil import tz
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text

from ..models import GameFormat, GameStatus
from ..settings import Settings
from . import Base, now

if TYPE_CHECKING:  # pragma: no cover
    from . import Channel, Game, Guild, User  # noqa


class Tourney(Base):
    """Represents a pending or started tourney."""

    __tablename__ = "tourneys"

    id = Column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The SpellBot tourney reference ID",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this tourney was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
        doc="UTC timestamp when this tourney was last updated",
    )
    started_at = Column(
        DateTime,
        nullable=True,
        doc="UTC timestamp when this tourney was started",
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this tourney was deleted",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel_xid = Column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )
    message_xid = Column(
        BigInteger,
        index=True,
        nullable=True,
        doc="The external Discord ID of the messsage where this tourney's embed is found",
    )
    status = Column(
        Integer(),
        default=GameStatus.PENDING.value,
        server_default=text(str(GameStatus.PENDING.value)),
        index=True,
        nullable=False,
        doc="Pending or started status of this tourney",
    )
    format = Column(
        Integer(),
        default=GameFormat.COMMANDER.value,
        server_default=text(str(GameFormat.COMMANDER.value)),
        index=True,
        nullable=False,
        doc="The Magic: The Gathering format for this tourney",
    )
    name = Column(
        String(100),
        default="",
        server_default="",
        nullable=False,
        doc="The name of this tourney",
    )
    description = Column(
        String(100),
        default="",
        server_default="",
        nullable=False,
        doc="The description of this tourney",
    )
    round = Column(
        Integer(),
        nullable=True,
        doc="The current round for this tourney if it has started",
    )

    guild = relationship(
        "Guild",
        back_populates="tourneys",
        doc="The guild this tourney was created in",
    )
    channel = relationship(
        "Channel",
        back_populates="tourneys",
        doc="The channel this tourney was created in",
    )
    games = relationship(
        "Game",
        back_populates="tourney",
        uselist=True,
        doc="Games in this tourney",
    )

    @property
    def started_at_timestamp(self) -> int:
        assert self.started_at is not None
        return int(self.started_at.replace(tzinfo=tz.UTC).timestamp())

    @property
    def embed_players(self) -> str:
        player_strs: list[str] = []
        for player in self.players:
            # TODO: Sum up all the points for all the games in this tourney
            # points_str = ""
            # if self.status == GameStatus.STARTED.value:
            #     points = player.points(self.id)
            #     if points:
            #         points_str = f" ({points} point{'s' if points > 1 else ''})"
            # player_strs.append(f"<@{player.xid}>{points_str}")
            player_strs.append(f"<@{player.xid}>")
        return ", ".join(sorted(player_strs))

    @property
    def embed_footer(self) -> str:
        return f"SpellBot Tourney ID: #T{self.id}"

    @property
    def jump_link(self) -> str:
        guild = self.guild_xid
        channel = self.channel_xid
        message = self.message_xid
        return f"https://discordapp.com/channels/{guild}/{channel}/{message}"

    @property
    def format_name(self) -> str:
        return GameFormat(self.format).name.replace("_", " ").title()

    def to_embed(self, dm: bool = False) -> discord.Embed:
        settings = Settings(self.guild_xid)
        embed = discord.Embed(title=self.name)
        embed.set_thumbnail(url=settings.THUMB_URL)
        embed.description = self.description
        # TODO: Show players
        # if self.players:
        #     embed.add_field(name="Players", value=self.embed_players, inline=False)
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
            "status": self.status,
            "format": self.format,
            "name": self.name,
            "description": self.description,
            "round": self.round,
            "jump_link": self.jump_link,
        }
