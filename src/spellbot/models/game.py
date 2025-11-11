from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, auto
from functools import partial
from typing import TYPE_CHECKING, TypedDict, cast

import discord
from dateutil import tz
from ddtrace.trace import tracer
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false, text

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.settings import settings

from . import Base, now

if TYPE_CHECKING:
    from spellbot.operations import VoiceChannelSuggestion

    from . import Channel, Guild, Post, PostDict, User  # noqa: F401

HR = "**˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙**"


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
    bracket: int
    service: int
    game_link: str | None
    jump_links: dict[int, str]
    password: str | None
    rules: str | None
    blind: bool


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
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this games was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
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
        "int",
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
        "int",
        Column(
            Integer,
            index=True,
            nullable=False,
            doc="The number of seats (open or occupied) available at this game",
        ),
    )
    status: int = cast(
        "int",
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
        "int",
        Column(
            Integer(),
            default=GameFormat.COMMANDER.value,
            server_default=text(str(GameFormat.COMMANDER.value)),
            index=True,
            nullable=False,
            doc="The Magic: The Gathering format for this game",
        ),
    )
    bracket: int = cast(
        "int",
        Column(
            Integer(),
            default=GameBracket.NONE.value,
            server_default=text(str(GameBracket.NONE.value)),
            index=True,
            nullable=False,
            doc="The commander bracket for this game",
        ),
    )
    service: int = cast(
        "int",
        Column(
            Integer(),
            default=GameService.SPELLTABLE.value,
            server_default=text(str(GameService.SPELLTABLE.value)),
            index=True,
            nullable=False,
            doc="The service that will be used to create this game",
        ),
    )
    game_link = Column(String(255), doc="The generated link for this game")
    password = Column(String(255), nullable=True, doc="The password for this game")
    voice_invite_link = Column(String(255), doc="The voice channel invite link for this game")
    rules = Column(String(255), nullable=True, index=True, doc="Additional rules for this game")
    blind = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for blind games",
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
    def player_pins(self) -> dict[int, str | None]:
        from spellbot.database import DatabaseSession

        from . import Play

        plays = DatabaseSession.query(Play).filter(Play.game_id == self.id)
        return {
            play.user_xid: play.pin if self.guild.enable_mythic_track else None for play in plays
        }

    @property
    def player_names(self) -> dict[int, str | None]:
        from spellbot.database import DatabaseSession

        from . import Play, User

        rows = (
            DatabaseSession.query(Play.user_xid, User.name)
            .join(User, User.xid == Play.user_xid)
            .filter(Play.game_id == self.id)
        )
        return {row[0]: row[1] for row in rows}

    @property
    def started_at_timestamp(self) -> int:
        assert self.started_at is not None
        return int(cast("datetime", self.started_at).replace(tzinfo=tz.UTC).timestamp())

    @property
    def updated_at_timestamp(self) -> int:
        assert self.updated_at is not None
        return int(cast("datetime", self.updated_at).replace(tzinfo=tz.UTC).timestamp())

    def show_links(self, dm: bool = False) -> bool:
        return True if dm else self.guild.show_links

    @property
    def embed_title(self) -> str:
        if self.status == GameStatus.STARTED.value:
            return "**Your game is ready!**"
        remaining = int(cast("int", self.seats)) - len(self.players)
        plural = "s" if remaining > 1 else ""
        return f"**Waiting for {remaining} more player{plural} to join...**"

    def embed_motd(self) -> list[str]:
        placeholders = self.placeholders
        parts: list[str] = []
        if self.guild.motd:
            parts.append(f"{self.apply_placeholders(placeholders, self.guild.motd)}")
        if self.channel.motd:
            parts.append(f"{self.apply_placeholders(placeholders, self.channel.motd)}")
        return parts

    def embed_description_link_info(
        self,
        effective_service: GameService,
        dm: bool,
        rematch: bool,
    ) -> str:
        if self.status != GameStatus.STARTED.value:
            return effective_service.pending_msg
        if not self.show_links(dm):
            return "Please check your Direct Messages for your game details."
        if rematch:
            return (
                "This is a rematch of a previous game. "
                "Please continue using the same game lobby and voice channel."
            )
        if self.game_link:
            return f"# [Join your {effective_service} game now!]({self.game_link})"
        if effective_service.fallback_url:
            return (
                "Sorry but SpellBot was unable to create a link"
                f" for this game. Please go to [{effective_service}]"
                f"({effective_service.fallback_url}) to create one."
            )
        if effective_service.value != GameService.NOT_ANY.value:
            return f"Please use {effective_service} to play this game."
        return "Contact the other players in your game to organize this match."

    def embed_description_extras(
        self,
        dm: bool,
        suggested_vc: VoiceChannelSuggestion | None,
    ) -> list[str]:
        if self.status != GameStatus.STARTED.value:
            return []
        parts: list[str] = []
        if self.show_links(dm):
            if self.password:
                parts.append(f"Password: `{self.password}`")
            if self.voice_xid:
                parts.append(f"## Join your voice chat now: <#{self.voice_xid}>")
            if self.voice_invite_link:
                parts.append(f"Or use this voice channel invite: {self.voice_invite_link}")
            if suggested_vc:
                if suggested_vc.already_picked is not None:
                    parts.append(
                        "## Your pod is already using a voice channel, "
                        f"join them now: <#{suggested_vc.already_picked}>!\n{HR}",
                    )
                elif suggested_vc.random_empty is not None:
                    parts.append(
                        "## Please consider using this available voice channel: "
                        f"<#{suggested_vc.random_empty}>.\n{HR}",
                    )
        if dm:
            jump_link = next(iter(self.jump_links.values()))
            parts.append(
                "You can also [jump to the original game post]"
                f"({jump_link}) in <#{self.channel_xid}>.",
            )
        return parts

    @tracer.wrap()
    def embed_description(
        self,
        *,
        guild: discord.Guild | None,
        dm: bool = False,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
    ) -> str:
        if span := tracer.current_span():  # pragma: no cover
            span.set_tags(
                {
                    "game_id": str(self.id),
                    "dm": str(dm),
                    "already_picked": str(suggested_vc.already_picked if suggested_vc else None),
                    "random_empty": str(suggested_vc.random_empty if suggested_vc else None),
                },
            )

        effective_service = GameService(int(self.service))
        parts: list[str] = []
        if self.guild.notice:
            parts.append(f"{self.guild.notice}")
        parts.append(self.embed_description_link_info(effective_service, dm, rematch))
        parts.extend(self.embed_description_extras(dm, suggested_vc))
        parts.extend(self.embed_motd())
        return "\n\n".join(parts)

    @property
    def placeholders(self) -> dict[str, str]:
        game_start = f"<t:{self.started_at_timestamp}>" if self.started_at else "pending"
        placeholders = {
            "game_id": str(self.id),
            "game_format": self.format_name,
            "game_bracket": f"Bracket {self.bracket_name}",
            "game_start": game_start,
        }
        for i, player in enumerate(self.players):
            placeholders[f"player_name_{i + 1}"] = cast("str", player.name)
        return placeholders

    def apply_placeholders(self, placeholders: dict[str, str], text: str) -> str:
        for k, v in placeholders.items():
            text = text.replace(f"${{{k}}}", v)
        return text

    @property
    def embed_players(self) -> str:
        def emoji(xid: int) -> str:
            return ""

        player_parts: list[tuple[int, str, str]] = [
            (
                player.xid,
                player.name,
                emoji(player.xid),
            )
            for player in self.players
        ]
        player_strs: list[str] = [
            f"• {parts[2]}<@{parts[0]}> ({parts[1]})" for parts in sorted(player_parts)
        ]
        return "\n".join(player_strs)

    @property
    def embed_footer(self) -> str:
        return f"SpellBot Game ID: #SB{self.id}"

    @property
    def jump_links(self) -> dict[int, str]:
        return {post.guild_xid: post.jump_link for post in self.posts or []}

    @property
    def format_name(self) -> str:
        return str(GameFormat(self.format))

    @property
    def bracket_name(self) -> str:
        return str(GameBracket(self.bracket))

    @property
    def bracket_icon(self) -> str | None:
        icon = GameBracket(self.bracket).icon
        return icon if icon else None

    @property
    def bracket_title(self) -> str:
        name = self.bracket_name[8:]
        if icon := self.bracket_icon:
            return f"{icon} {name}"
        return name

    def to_embed(
        self,
        *,
        guild: discord.Guild | None = None,
        dm: bool = False,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
    ) -> discord.Embed:
        title = "**Rematch Game!**" if rematch else self.embed_title
        embed = discord.Embed(title=title)
        embed.set_thumbnail(url=settings.thumb(self.guild_xid))
        embed.description = self.embed_description(
            guild=guild,
            dm=dm,
            suggested_vc=suggested_vc,
            rematch=rematch,
        )
        if self.rules:
            embed.add_field(name="⚠️ Additional Rules:", value=self.rules, inline=False)
        if self.blind and not dm:
            joined = len(self.players)
            plural = "s" if joined != 1 else ""
            verb = "is" if joined == 1 else "are"
            embed.add_field(
                name="Players",
                value=f"**{joined} player name{plural} {verb} hidden**",
                inline=False,
            )
        elif self.players:
            embed.add_field(name="Players", value=self.embed_players, inline=False)
        embed.add_field(name="Format", value=self.format_name)
        if self.bracket != GameBracket.NONE.value:
            embed.add_field(name="Bracket", value=self.bracket_title)
        timestamp_field = (
            ("Started at", f"<t:{self.started_at_timestamp}>")
            if self.started_at
            else ("Updated at", f"<t:{self.updated_at_timestamp}>")
        )
        embed.add_field(name=timestamp_field[0], value=timestamp_field[1])
        if self.service != GameService.SPELLTABLE.value and not rematch:
            embed.add_field(name="Service", value=str(GameService(self.service)), inline=False)
        if self.players:
            embed.color = (
                discord.Color(settings.STARTED_EMBED_COLOR)
                if self.started_at
                else discord.Color(settings.PENDING_EMBED_COLOR)
            )
        else:
            embed.color = discord.Color(settings.EMPTY_EMBED_COLOR)
        if suggested_vc and (vc_xid := suggested_vc.get()):
            embed.add_field(name="🔊 Suggested Voice Channel", value=f"<#{vc_xid}>", inline=False)
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
            "bracket": self.bracket,
            "service": self.service,
            "game_link": self.game_link,
            "jump_links": self.jump_links,
            "password": self.password,
            "rules": self.rules,
            "blind": self.blind,
        }


MAX_RULES_LENGTH: int = Game.rules.property.columns[0].type.length  # type: ignore
