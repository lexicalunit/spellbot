from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import discord
from dateutil import tz
from ddtrace.trace import tracer

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.i18n import t
from spellbot.models import GameStatus
from spellbot.settings import settings

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.data import ChannelData, GuildData, PostData, UserData
    from spellbot.operations import VoiceChannelSuggestion

HR = "**˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙**"


# Helper to select singular or plural translation key
def _plural(
    count: int,
    singular_key: str,
    plural_key: str,
    locale: str,
    **kwargs: str | int,
) -> str:
    key = singular_key if count == 1 else plural_key
    return t(key, locale=locale, count=count, **kwargs)


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
    locale: str = "en"

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
        locale = self.locale
        if self.status == GameStatus.STARTED.value:
            return t("game.title.ready", locale=locale)
        remaining = int(cast("int", self.seats)) - len(self.players)
        return _plural(
            remaining,
            "game.title.waiting_one",
            "game.title.waiting_many",
            locale,
        )

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
        locale = self.locale
        emojis = emojis or []
        title = t("game.title.rematch", locale=locale) if rematch else self.embed_title
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
            embed.add_field(
                name=t("game.field.rules", locale=locale),
                value=self.rules,
                inline=False,
            )
        if self.blind and not dm:
            joined = len(self.players)
            embed.add_field(
                name=t("game.field.players", locale=locale),
                value=_plural(
                    joined,
                    "game.field.players_hidden_one",
                    "game.field.players_hidden_many",
                    locale,
                ),
                inline=False,
            )
        elif self.players:
            players_value = self.embed_players(emojis, supporters)
            embed.add_field(
                name=t("game.field.players", locale=locale),
                value=players_value,
                inline=False,
            )
        embed.add_field(name=t("game.field.format", locale=locale), value=self.format_name)
        if self.bracket != GameBracket.NONE.value:
            embed.add_field(name=t("game.field.bracket", locale=locale), value=self.bracket_title)
        timestamp_field = (
            (t("game.field.started_at", locale=locale), f"<t:{self.started_at_timestamp}>")
            if self.started_at
            else (t("game.field.updated_at", locale=locale), f"<t:{self.updated_at_timestamp}>")
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
            embed.add_field(
                name=t("game.field.voice_channel", locale=locale),
                value=f"<#{vc_xid}>",
                inline=False,
            )
        embed.add_field(
            name=t("game.field.support", locale=locale),
            value=t(
                "game.field.support_text",
                locale=locale,
                subscribe=settings.SUBSCRIBE_LINK,
                donate=settings.DONATE_LINK,
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
        locale = self.locale
        if self.status != GameStatus.STARTED.value:
            return effective_service.get_pending_msg(locale, emojis)
        if not self.show_links(dm):
            return t("game.description.check_dm", locale=locale)
        if rematch:
            return t("game.description.rematch_info", locale=locale)
        if self.game_link:
            return t(
                "game.description.join_link",
                locale=locale,
                service=str(effective_service),
                link=self.game_link,
            )
        if effective_service.fallback_url:
            return t(
                "game.description.link_error",
                locale=locale,
                service=str(effective_service),
                url=effective_service.fallback_url,
            )
        if effective_service.value != GameService.NOT_ANY.value:
            return t(
                "game.description.use_service",
                locale=locale,
                service=str(effective_service),
            )
        return t("game.description.contact_players", locale=locale)

    def embed_description_extras(
        self,
        dm: bool,
        suggested_vc: VoiceChannelSuggestion | None,
    ) -> list[str]:
        locale = self.locale
        if self.status != GameStatus.STARTED.value:
            return []
        parts: list[str] = []
        if self.show_links(dm):
            if self.password:
                parts.append(t("game.description.password", locale=locale, password=self.password))
            if self.voice_xid:
                parts.append(
                    t("game.description.voice_chat", locale=locale, channel_id=self.voice_xid),
                )
            if self.voice_invite_link:
                parts.append(
                    t(
                        "game.description.voice_invite",
                        locale=locale,
                        invite=self.voice_invite_link,
                    ),
                )
            if suggested_vc:
                if suggested_vc.already_picked is not None:
                    parts.append(
                        t(
                            "game.description.voice_already_picked",
                            locale=locale,
                            channel_id=suggested_vc.already_picked,
                        )
                        + f"\n{HR}",
                    )
                elif suggested_vc.random_empty is not None:
                    parts.append(
                        t(
                            "game.description.voice_available",
                            locale=locale,
                            channel_id=suggested_vc.random_empty,
                        )
                        + f"\n{HR}",
                    )
        if dm:
            jump_link = next(iter(self.jump_links.values()))
            parts.append(
                t(
                    "game.description.jump_to_post",
                    locale=locale,
                    link=jump_link,
                    channel_id=self.channel_xid,
                ),
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
        return t(
            "game.footer",
            locale=self.locale,
            game_id=self.id,
            service=str(GameService(self.service)),
        )


@dataclass
class GameLinkDetails:
    link: str | None = None
    password: str | None = None
