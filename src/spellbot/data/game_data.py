from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import discord
from dateutil import tz
from ddtrace.trace import tracer

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import GameStatus
from spellbot.settings import settings

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.data import ChannelData, GuildData, PostData, UserData
    from spellbot.operations import VoiceChannelSuggestion

HR = "**˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙**"


@dataclass
class GameData:
    id: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    deleted_at: datetime | None
    guild_xid: int
    guild: GuildData
    channel_xid: int
    channel: ChannelData
    voice_xid: int | None
    voice_invite_link: str | None
    seats: int
    status: int
    format: int
    bracket: int
    service: int
    game_link: str | None
    password: str | None
    rules: str | None
    blind: bool
    players: list[UserData] = field(default_factory=list)
    posts: list[PostData] = field(default_factory=list)
    player_pins: dict[int, str | None] = field(default_factory=dict)

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
    def started_at_timestamp(self) -> int:
        assert self.started_at is not None
        return int(cast("datetime", self.started_at).replace(tzinfo=tz.UTC).timestamp())

    @property
    def updated_at_timestamp(self) -> int:
        assert self.updated_at is not None
        return int(cast("datetime", self.updated_at).replace(tzinfo=tz.UTC).timestamp())

    @property
    def format_name(self) -> str:
        return str(GameFormat(self.format))

    @property
    def embed_title(self) -> str:
        if self.status == GameStatus.STARTED.value:
            return "**Your game is ready!**"
        remaining = int(cast("int", self.seats)) - len(self.players)
        plural = "s" if remaining > 1 else ""
        return f"**Waiting for {remaining} more player{plural} to join...**"

    @property
    def jump_links(self) -> dict[int, str]:
        return {post.guild_xid: post.jump_link for post in self.posts}

    @property
    def bracket_name(self) -> str:
        return str(GameBracket(self.bracket))

    @property
    def bracket_icon(self) -> str | None:
        return GameBracket(self.bracket).icon

    @property
    def bracket_title(self) -> str:
        name = self.bracket_name[8:]
        if icon := self.bracket_icon:
            return f"{icon} {name}"
        return name

    @property
    def fully_seated(self) -> bool:
        return len(self.players) == self.seats

    @tracer.wrap()
    def embed_description(
        self,
        *,
        guild: discord.Guild | None,
        dm: bool = False,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
        emojis: list[discord.Emoji] | list[discord.PartialEmoji | discord.Emoji] | None = None,
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
        parts.append(self.embed_description_link_info(effective_service, dm, rematch, emojis))
        parts.extend(self.embed_description_extras(dm, suggested_vc))
        parts.extend(self.embed_motd())
        return "\n\n".join(parts)

    @tracer.wrap()
    def to_embed(
        self,
        *,
        guild: discord.Guild | None,
        dm: bool = False,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
        emojis: list[discord.Emoji] | list[discord.PartialEmoji | discord.Emoji] | None = None,
        supporters: set[int] | None = None,
    ) -> discord.Embed:
        emojis = emojis or []
        title = "**Rematch Game!**" if rematch else self.embed_title
        embed = discord.Embed(title=title)
        embed.set_thumbnail(url=settings.thumb(self.guild_xid))
        embed.description = self.embed_description(
            guild=guild,
            dm=dm,
            suggested_vc=suggested_vc,
            rematch=rematch,
            emojis=emojis,
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
            players_value = self.embed_players(emojis, supporters)
            embed.add_field(name="Players", value=players_value, inline=False)
        embed.add_field(name="Format", value=self.format_name)
        if self.bracket != GameBracket.NONE.value:
            embed.add_field(name="Bracket", value=self.bracket_title)
        timestamp_field = (
            ("Started at", f"<t:{self.started_at_timestamp}>")
            if self.started_at
            else ("Updated at", f"<t:{self.updated_at_timestamp}>")
        )
        embed.add_field(name=timestamp_field[0], value=timestamp_field[1])
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

    def show_links(self, dm: bool = False) -> bool:
        return True if dm else self.guild.show_links

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
        emojis: list[discord.Emoji] | list[discord.PartialEmoji | discord.Emoji] | None = None,
    ) -> str:
        if self.status != GameStatus.STARTED.value:
            if "{emoji}" in effective_service.pending_msg:
                emoji_str = ""
                if emojis:
                    emoji_name = effective_service.name.lower().replace("-", "_").replace(" ", "_")
                    if emoji := next((e for e in emojis if e.name == emoji_name), None):
                        emoji_str = f"{emoji} "
                return effective_service.pending_msg.format(emoji=emoji_str)
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

    def embed_players(
        self,
        emojis: list[discord.Emoji] | list[discord.PartialEmoji | discord.Emoji] | None = None,
        supporters: set[int] | None = None,
    ) -> str:
        emojis = emojis or []
        supporters = supporters or set()

        supporter_emoji = next((e for e in emojis if e.name == "spellbot_supporter"), None)
        owner_emoji = next((e for e in emojis if e.name == "spellbot_creator"), None)

        def emoji(xid: int) -> str:
            if supporter_emoji and xid in supporters:
                return f"{supporter_emoji} "
            if owner_emoji and settings.OWNER_XID and xid == settings.OWNER_XID:
                return f"{owner_emoji} "
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
        return f"SpellBot Game ID: #SB{self.id} — Service: {GameService(self.service)}"


@dataclass
class GameLinkDetails:
    link: str | None = None
    password: str | None = None
