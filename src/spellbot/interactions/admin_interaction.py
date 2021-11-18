import logging
from typing import Optional, cast

import discord
import discord_slash.utils.manage_components as comp
from discord.embeds import Embed
from discord_slash.context import ComponentContext, InteractionContext
from discord_slash.model import ButtonStyle
from pygicord import Config, Paginator

from .. import SpellBot
from ..models import Channel
from ..operations import safe_send_channel, safe_update_embed_origin
from ..services import GamesService
from ..settings import Settings
from ..utils import EMBED_DESCRIPTION_SIZE_LIMIT, log_warning
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


def humanize_bool(setting: bool) -> str:
    return "✅ On" if setting else "❌ Off"


class AdminInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)
        self.settings = Settings()

    async def _report_failure(self):
        assert self.ctx
        await safe_send_channel(self.ctx, "There is no game with that ID.", hidden=True)

    async def _build_channels_embeds(self) -> list[Embed]:
        guild = await self.services.guilds.to_dict()
        embeds: list[Embed] = []

        def new_embed() -> Embed:
            embed = Embed(title=f"Configuration for channels in {guild['name']}")
            embed.set_thumbnail(url=self.settings.ICO_URL)
            embed.color = discord.Color(self.settings.EMBED_COLOR)
            return embed

        def update_channel_settings(channel, channel_settings, col):
            if channel[col] != getattr(Channel, col).default.arg:
                channel_settings[col] = channel[col]

        all_default = True
        embed = new_embed()
        description = ""
        for channel in guild.get("channels", []):
            channel_settings: dict = {}
            update_channel_settings(channel, channel_settings, "default_seats")
            update_channel_settings(channel, channel_settings, "auto_verify")
            update_channel_settings(channel, channel_settings, "unverified_only")
            update_channel_settings(channel, channel_settings, "verified_only")
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
            kind = "every" if award["repeating"] else "after"
            next_line = (
                f"• **ID {award['id']}** — "
                f"_{kind} {award['count']} games_"
                f" — `@{award['role']}`"
                f" — {award['message']}\n"
            )
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
            name="Show Points on Games",
            value=humanize_bool(guild["show_points"]),
        )
        embed.add_field(
            name="Create Voice Channels",
            value=humanize_bool(guild["voice_create"]),
        )
        embed.color = discord.Color(self.settings.EMBED_COLOR)
        return embed

    async def build_setup_components(self):
        components = []
        buttons = [
            comp.create_button(
                style=ButtonStyle.primary,
                label="Toggle Public Links",
                custom_id="toggle_show_links",
            ),
            comp.create_button(
                style=ButtonStyle.primary,
                label="Toggle Show Points",
                custom_id="toggle_show_points",
            ),
            comp.create_button(
                style=ButtonStyle.primary,
                label="Toggle Create Voice Channels",
                custom_id="toggle_voice_create",
            ),
        ]
        action_row = comp.create_actionrow(*buttons)
        components.append(action_row)

        buttons = [
            comp.create_button(
                style=ButtonStyle.secondary,
                label="Refresh",
                custom_id="refresh_setup",
            ),
        ]
        action_row = comp.create_actionrow(*buttons)
        components.append(action_row)
        return components

    async def info(self, game_id: str):
        assert self.ctx

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
        await safe_send_channel(self.ctx, embed=embed, hidden=True)

    async def setup(self):
        assert self.ctx
        embed = await self._build_setup_embed()
        components = await self.build_setup_components()
        await safe_send_channel(self.ctx, embed=embed, components=components)

    async def channels(self):
        assert self.ctx
        embeds = await self._build_channels_embeds()
        if len(embeds) > 1:
            paginator = Paginator(pages=embeds, config=Config.MINIMAL)
            try:
                await paginator.start(self.ctx)  # type: ignore
            except Exception as e:
                log_warning("pagination error: %(err)s", err=e, exec_info=True)
        else:
            await safe_send_channel(self.ctx, embed=embeds[0])

    async def awards(self):
        assert self.ctx
        embeds = await self._build_awards_embeds()
        if len(embeds) > 1:
            paginator = Paginator(pages=embeds, config=Config.MINIMAL)
            try:
                await paginator.start(self.ctx)  # type: ignore
            except Exception as e:
                log_warning("pagination error: %(err)s", err=e, exec_info=True)
        else:
            await safe_send_channel(self.ctx, embed=embeds[0])

    async def award_add(
        self,
        count: int,
        role: str,
        message: str,
        repeating: Optional[bool] = False,
    ):
        assert self.ctx
        if count < 1:
            return await safe_send_channel(
                self.ctx,
                "You can't create an award for zero games played.",
                hidden=True,
            )
        if await self.services.guilds.has_award_with_count(count):
            return await safe_send_channel(
                self.ctx,
                "There's already an award for players who reach that many games.",
                hidden=True,
            )
        await self.services.guilds.award_add(count, role, message, repeating)
        embed = Embed()
        embed.set_thumbnail(url=self.settings.ICO_URL)
        embed.set_author(name="Award added!")
        description = (
            f"• _{'every' if repeating else 'after'} {count} games_ — `@{role}`"
            f" — {message}\n\nYou can view all awards with the `/set awards` command."
        )
        embed.description = description
        embed.color = self.settings.EMBED_COLOR
        await safe_send_channel(self.ctx, embed=embed, hidden=True)

    async def award_delete(self, guild_award_id: int):
        assert self.ctx
        await self.services.guilds.award_delete(guild_award_id)
        embed = Embed()
        embed.set_thumbnail(url=self.settings.ICO_URL)
        embed.set_author(name="Award deleted!")
        description = "You can view all awards with the `/set awards` command."
        embed.description = description
        embed.color = self.settings.EMBED_COLOR
        await safe_send_channel(self.ctx, embed=embed, hidden=True)

    async def set_motd(self, message: Optional[str] = None):
        assert self.ctx
        await self.services.guilds.set_motd(message)
        await safe_send_channel(self.ctx, "Message of the day updated.", hidden=True)

    async def refresh_setup(self):
        embed = await self._build_setup_embed()
        components = await self.build_setup_components()
        ctx = cast(ComponentContext, self.ctx)
        await safe_update_embed_origin(ctx, embed=embed, components=components)

    async def toggle_show_links(self):
        await self.services.guilds.toggle_show_links()
        embed = await self._build_setup_embed()
        components = await self.build_setup_components()
        ctx = cast(ComponentContext, self.ctx)
        await safe_update_embed_origin(ctx, embed=embed, components=components)

    async def toggle_show_points(self):
        await self.services.guilds.toggle_show_points()
        embed = await self._build_setup_embed()
        components = await self.build_setup_components()
        ctx = cast(ComponentContext, self.ctx)
        await safe_update_embed_origin(ctx, embed=embed, components=components)

    async def toggle_voice_create(self):
        await self.services.guilds.toggle_voice_create()
        embed = await self._build_setup_embed()
        components = await self.build_setup_components()
        ctx = cast(ComponentContext, self.ctx)
        await safe_update_embed_origin(ctx, embed=embed, components=components)

    async def set_default_seats(self, seats: int):
        assert self.ctx
        await self.services.channels.set_default_seats(self.ctx.channel_id, seats)
        await safe_send_channel(
            self.ctx,
            f"Default seats set to {seats} for this channel.",
            hidden=True,
        )

    async def set_auto_verify(self, setting: bool):
        assert self.ctx
        await self.services.channels.set_auto_verify(self.ctx.channel_id, setting)
        await safe_send_channel(
            self.ctx,
            f"Auto verification set to {setting} for this channel.",
            hidden=True,
        )

    async def set_verified_only(self, setting: bool):
        assert self.ctx
        await self.services.channels.set_verified_only(self.ctx.channel_id, setting)
        await safe_send_channel(
            self.ctx,
            f"Verified only set to {setting} for this channel.",
            hidden=True,
        )

    async def set_unverified_only(self, setting: bool):
        assert self.ctx
        await self.services.channels.set_unverified_only(self.ctx.channel_id, setting)
        await safe_send_channel(
            self.ctx,
            f"Unverified only set to {setting} for this channel.",
            hidden=True,
        )

    async def set_channel_motd(self, message: Optional[str] = None):
        assert self.ctx
        motd = await self.services.channels.set_motd(self.ctx.channel_id, message)
        await safe_send_channel(
            self.ctx,
            f"Message of the day for this channel has been set to: {motd}",
            hidden=True,
        )
