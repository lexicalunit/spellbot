from __future__ import annotations

import logging
from typing import Any, Optional

import discord
from discord.embeds import Embed

from .. import SpellBot
from ..models import Channel, GuildAward
from ..operations import safe_send_channel, safe_update_embed_origin
from ..services import GamesService
from ..settings import Settings
from ..utils import EMBED_DESCRIPTION_SIZE_LIMIT
from ..views import SetupView
from .base_action import BaseAction

logger = logging.getLogger(__name__)


def humanize_bool(setting: bool) -> str:
    return "✅ On" if setting else "❌ Off"


def award_line(award: dict[str, Any]) -> str:
    kind = "every" if award["repeating"] else "after"
    give_or_take = "take" if award["remove"] else "give"
    verified_only = "verified only" if award["verified_only"] else ""
    unverified_only = "unverified only" if award["unverified_only"] else ""
    verify_status = (
        f" ({verified_only}{unverified_only}) " if verified_only or unverified_only else " "
    )
    return (
        f"• **ID {award['id']}** — _{kind} {award['count']} games_ "
        f"— {give_or_take} `@{award['role']}`{verify_status}"
        f"— {award['message']}"
    )


class AdminAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction):
        super().__init__(bot, interaction)
        self.settings = Settings()

    async def _report_failure(self) -> None:
        await safe_send_channel(
            self.interaction,
            "There is no game with that ID.",
            ephemeral=True,
        )

    async def _build_channels_embeds(self) -> list[Embed]:
        guild = await self.services.guilds.to_dict()
        embeds: list[Embed] = []

        def new_embed() -> Embed:
            embed = Embed(title=f"Configuration for channels in {guild['name']}")
            embed.set_thumbnail(url=self.settings.ICO_URL)
            embed.color = discord.Color(self.settings.EMBED_COLOR)
            return embed

        def update_channel_settings(
            channel: dict[str, Any],
            channel_settings: dict[str, Any],
            col: str,
        ):
            if channel[col] != getattr(Channel, col).default.arg:
                channel_settings[col] = channel[col]

        all_default = True
        embed = new_embed()
        description = ""
        for channel in sorted(guild.get("channels", []), key=lambda g: g["xid"]):
            channel_settings: dict[str, Any] = {}
            update_channel_settings(channel, channel_settings, "default_seats")
            update_channel_settings(channel, channel_settings, "auto_verify")
            update_channel_settings(channel, channel_settings, "unverified_only")
            update_channel_settings(channel, channel_settings, "verified_only")
            update_channel_settings(channel, channel_settings, "voice_category")
            update_channel_settings(channel, channel_settings, "show_points")
            if channel_settings:
                all_default = False
                deets = ", ".join(
                    (f"`{k}`" if isinstance(v, bool) and v else f"`{k}={v}`")
                    for k, v in channel_settings.items()
                )
                next_line = f"• <#{channel['xid']}> — {deets}\n"
                if len(description) + len(next_line) >= EMBED_DESCRIPTION_SIZE_LIMIT:
                    embed.description = description
                    embeds.append(embed)
                    embed = new_embed()
                    description = ""
                description += next_line

        if all_default:
            description = (
                "**All channels on this server have a default configuration.**\n\n"
                "Use may use channel specific `/set` commands within a channel to"
                " change that channel's configuration."
            )

        embed.description = description
        embeds.append(embed)

        n = len(embeds)
        if n > 1:
            for i, embed in enumerate(embeds, start=1):
                embed.set_footer(text=f"page {i} of {n}")

        return embeds

    async def _build_awards_embeds(self) -> list[Embed]:
        guild = await self.services.guilds.to_dict()
        embeds: list[Embed] = []

        def new_embed() -> Embed:
            embed = Embed(title=f"SpellBot Player Awards for {guild['name']}")
            embed.set_thumbnail(url=self.settings.ICO_URL)
            embed.color = discord.Color(self.settings.EMBED_COLOR)
            return embed

        has_at_least_one_award = False
        embed = new_embed()
        description = ""
        for award in guild.get("awards", []):
            has_at_least_one_award = True
            next_line = f"{award_line(award)}\n"
            if len(description) + len(next_line) >= EMBED_DESCRIPTION_SIZE_LIMIT:
                embed.description = description
                embeds.append(embed)
                embed = new_embed()
                description = ""
            description += next_line

        if not has_at_least_one_award:
            description = (
                "**There are no awards configured on this server.**\n\n"
                "To add awards use the `/award add` command."
            )

        embed.description = description
        embeds.append(embed)

        n = len(embeds)
        if n > 1:
            for i, embed in enumerate(embeds, start=1):
                embed.set_footer(text=f"page {i} of {n}")

        return embeds

    async def _build_setup_embed(self) -> Embed:
        guild = await self.services.guilds.to_dict()
        embed = Embed(title=f"SpellBot Setup for {guild['name']}")
        embed.set_thumbnail(url=self.settings.ICO_URL)
        description = (
            "These are the current settings for SpellBot on this server."
            " Please use the buttons below, as well as the `/set` commands,"
            " to setup SpellBot as you wish.\n\n"
            "You may also view Awards configuration using the `/awards` command"
            " and Channels configuration using the `/channels` command."
        )

        embed.description = description[:EMBED_DESCRIPTION_SIZE_LIMIT]
        embed.add_field(
            name="MOTD",
            value=guild["motd"] or "None",
            inline=False,
        )
        embed.add_field(
            name="Public Links",
            value=humanize_bool(guild["show_links"]),
        )
        embed.add_field(
            name="Create Voice Channels",
            value=humanize_bool(guild["voice_create"]),
        )
        embed.color = discord.Color(self.settings.EMBED_COLOR)
        return embed

    async def info(self, game_id: str) -> None:
        numeric_filter = filter(str.isdigit, game_id)
        numeric_string = "".join(numeric_filter)
        if not numeric_string:
            return await self._report_failure()
        game_id_int = int(numeric_string)

        games = GamesService()
        found = await games.select(game_id_int)
        if not found:
            return await self._report_failure()

        embed = await games.to_embed(dm=True)
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def setup(self) -> None:
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_send_channel(self.interaction, embed=embed, view=view)

    async def channels(self, page: int) -> None:
        embeds = await self._build_channels_embeds()
        await safe_send_channel(self.interaction, embed=embeds[page - 1])

    async def awards(self, page: int) -> None:
        embeds = await self._build_awards_embeds()
        await safe_send_channel(self.interaction, embed=embeds[page - 1])

    async def award_add(
        self,
        count: int,
        role: str,
        message: str,
        **options: Optional[bool],
    ) -> None:
        repeating = bool(options.get("repeating", False))
        remove = bool(options.get("remove", False))
        verified_only = bool(options.get("verified_only", False))
        unverified_only = bool(options.get("unverified_only", False))

        if verified_only and unverified_only:
            await safe_send_channel(
                self.interaction,
                "Your award can't be both verified and unverifed only.",
                ephemeral=True,
            )
            return

        max_message_len = GuildAward.message.property.columns[0].type.length  # type: ignore
        if len(message) > max_message_len:
            await safe_send_channel(
                self.interaction,
                f"Your message can't be longer than {max_message_len} characters.",
                ephemeral=True,
            )
            return

        if count < 1:
            await safe_send_channel(
                self.interaction,
                "You can't create an award for zero games played.",
                ephemeral=True,
            )
            return

        award = await self.services.guilds.award_add(
            count,
            role,
            message,
            repeating=repeating,
            remove=remove,
            verified_only=verified_only,
            unverified_only=unverified_only,
        )

        embed = Embed()
        embed.set_thumbnail(url=self.settings.ICO_URL)
        embed.set_author(name="Award added!")
        line = award_line(award)
        description = f"{line}\n\nYou can view all awards with the `/set awards` command."
        embed.description = description
        embed.color = self.settings.EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def award_delete(self, guild_award_id: int) -> None:
        await self.services.guilds.award_delete(guild_award_id)
        embed = Embed()
        embed.set_thumbnail(url=self.settings.ICO_URL)
        embed.set_author(name="Award deleted!")
        description = "You can view all awards with the `/set awards` command."
        embed.description = description
        embed.color = self.settings.EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def set_motd(self, message: Optional[str] = None) -> None:
        await self.services.guilds.set_motd(message)
        await safe_send_channel(self.interaction, "Message of the day updated.", ephemeral=True)

    async def refresh_setup(self):
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_show_links(self):
        await self.services.guilds.toggle_show_links()
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_voice_create(self):
        await self.services.guilds.toggle_voice_create()
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def set_default_seats(self, seats: int):
        await self.services.channels.set_default_seats(self.interaction.channel_id, seats)
        await safe_send_channel(
            self.interaction,
            f"Default seats set to {seats} for this channel.",
            ephemeral=True,
        )

    async def set_auto_verify(self, setting: bool):
        await self.services.channels.set_auto_verify(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            f"Auto verification set to {setting} for this channel.",
            ephemeral=True,
        )

    async def set_verified_only(self, setting: bool):
        await self.services.channels.set_verified_only(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            f"Verified only set to {setting} for this channel.",
            ephemeral=True,
        )

    async def set_unverified_only(self, setting: bool):
        assert self.interaction
        await self.services.channels.set_unverified_only(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            f"Unverified only set to {setting} for this channel.",
            ephemeral=True,
        )

    async def set_channel_motd(self, message: Optional[str] = None):
        motd = await self.services.channels.set_motd(self.interaction.channel_id, message)
        await safe_send_channel(
            self.interaction,
            f"Message of the day for this channel has been set to: {motd}",
            ephemeral=True,
        )

    async def set_voice_category(self, value: str):
        name = await self.services.channels.set_voice_category(self.interaction.channel_id, value)
        await safe_send_channel(
            self.interaction,
            f"Voice category prefix for this channel has been set to: {name}",
            ephemeral=True,
        )

    async def set_delete_expired(self, value: bool):
        name = await self.services.channels.set_delete_expired(self.interaction.channel_id, value)
        await safe_send_channel(
            self.interaction,
            f"Delete expired setting for this channel has been set to: {name}",
            ephemeral=True,
        )

    async def set_show_points(self, value: bool):
        name = await self.services.channels.set_show_points(self.interaction.channel_id, value)
        await safe_send_channel(
            self.interaction,
            f"Show points setting for this channel has been set to: {name}",
            ephemeral=True,
        )
