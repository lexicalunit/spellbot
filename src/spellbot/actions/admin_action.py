from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.embeds import Embed

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Channel, ChannelDict, GuildAward, GuildAwardDict
from spellbot.operations import (
    safe_fetch_text_channel,
    safe_send_channel,
    safe_update_embed_origin,
)
from spellbot.settings import settings
from spellbot.utils import EMBED_DESCRIPTION_SIZE_LIMIT
from spellbot.views import SetupView

from .base_action import BaseAction

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


def humanize_bool(setting: bool) -> str:
    return "✅ On" if setting else "❌ Off"


def award_line(award: GuildAwardDict) -> str:
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
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)

    async def _report_failure(self) -> None:
        await safe_send_channel(
            self.interaction,
            "There is no game with that ID.",
            ephemeral=True,
        )

    async def _build_channels_embeds(self) -> list[Embed]:  # noqa: C901
        guild = await self.services.guilds.to_dict()
        embeds: list[Embed] = []

        def new_embed() -> Embed:
            embed = Embed(title=f"Configuration for channels in {guild['name']}")
            embed.set_thumbnail(url=settings.ICO_URL)
            embed.color = discord.Color(settings.INFO_EMBED_COLOR)
            return embed

        def update_channel_settings(
            channel: ChannelDict,
            channel_settings: dict[str, Any],
            col: str,
        ) -> None:
            is_enum = col in ("default_format", "default_service")
            value = channel[col].value if is_enum else channel[col]
            if value != getattr(Channel, col).default.arg:
                channel_settings[col] = str(channel[col]) if is_enum else value

        all_default = True
        embed = new_embed()
        description = ""
        for channel in sorted(guild.get("channels", []), key=lambda g: g["xid"]):
            discord_channel = await safe_fetch_text_channel(self.bot, guild["xid"], channel["xid"])
            if not discord_channel:
                await self.services.channels.forget(channel["xid"])
                continue

            channel_settings: dict[str, Any] = {}
            update_channel_settings(channel, channel_settings, "default_seats")
            update_channel_settings(channel, channel_settings, "default_format")
            update_channel_settings(channel, channel_settings, "default_service")
            update_channel_settings(channel, channel_settings, "auto_verify")
            update_channel_settings(channel, channel_settings, "unverified_only")
            update_channel_settings(channel, channel_settings, "verified_only")
            update_channel_settings(channel, channel_settings, "voice_category")
            update_channel_settings(channel, channel_settings, "voice_invite")
            if channel_settings:
                all_default = False
                deets = ", ".join(
                    (f"`{k}`" if isinstance(v, bool) and v else f"`{k}={v}`")
                    for k, v in channel_settings.items()
                )
                next_line = f"• <#{channel['xid']}> ({channel['xid']}) — {deets}\n"
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
            embed.set_thumbnail(url=settings.ICO_URL)
            embed.color = discord.Color(settings.INFO_EMBED_COLOR)
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
        embed.set_thumbnail(url=settings.ICO_URL)
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
        embed.add_field(
            name="Use Max Bitrate",
            value=humanize_bool(guild["use_max_bitrate"]),
        )
        embed.color = discord.Color(settings.INFO_EMBED_COLOR)
        return embed

    async def forget_channel(self, channel_str: str) -> None:
        try:
            channel_xid = int(channel_str)
        except ValueError:
            await safe_send_channel(self.interaction, "Invalid ID.", ephemeral=True)
            return

        await self.services.channels.forget(channel_xid)
        await safe_send_channel(self.interaction, "Done.", ephemeral=True)

    async def info(self, game_id: str) -> None:
        numeric_filter = filter(str.isdigit, game_id)
        numeric_string = "".join(numeric_filter)
        if not numeric_string:
            return await self._report_failure()
        game_id_int = int(numeric_string)

        found = await self.services.games.select(game_id_int)
        if not found:
            return await self._report_failure()

        embed = await self.services.games.to_embed(guild=self.guild, dm=True)
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
        return None

    async def setup(self) -> None:
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_send_channel(self.interaction, embed=embed, view=view)

    async def setup_mythic_track(self) -> None:
        assert self.guild is not None
        enabled = await self.services.guilds.setup_mythic_track()
        embed = Embed(title=f"Mythic Track Setup for {self.guild.name}")
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.color = discord.Color(settings.INFO_EMBED_COLOR)
        if enabled:
            GUIDE = "https://www.mythictrack.com/spellbot"
            embed.description = (
                "✅ Mythic Track has been turned **on** for this server!\n\n"
                "To continue setup, please "
                f"[connect your Discord account to Mythic Track]({GUIDE}).\n\n"
                "While this feature is turned on, SpellBot will generate PIN codes for "
                "players to enter into Mythic Track so that their games can be tracked."
            )
        else:
            embed.description = (
                "❌ Mythic Track has been turned **off** for this server. Rerun this command "
                "to toggle it back on. Note that turning this feature off does _not_ remove "
                "any existing Mythic Track data."
            )
        await safe_send_channel(self.interaction, embed=embed)

    async def channels(self, page: int) -> None:
        embeds = await self._build_channels_embeds()
        try:
            await safe_send_channel(self.interaction, embed=embeds[page - 1])
        except IndexError:
            await safe_send_channel(self.interaction, "Invalid page.", ephemeral=True)

    async def awards(self, page: int) -> None:
        embeds = await self._build_awards_embeds()
        try:
            await safe_send_channel(self.interaction, embed=embeds[page - 1])
        except IndexError:
            await safe_send_channel(self.interaction, "Invalid page.", ephemeral=True)

    async def award_add(
        self,
        count: int,
        role: str,
        message: str,
        **options: bool | None,
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
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name="Award added!")
        line = award_line(award)
        description = f"{line}\n\nYou can view all awards with the `/awards` command."
        embed.description = description
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def award_delete(self, guild_award_id: int) -> None:
        await self.services.guilds.award_delete(guild_award_id)
        embed = Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name="Award deleted!")
        description = "You can view all awards with the `/awards` command."
        embed.description = description
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def set_suggest_vc_category(self, category: str | None) -> None:
        guild = await self.services.guilds.to_dict()
        if guild["voice_create"]:
            await safe_send_channel(
                self.interaction,
                (
                    "Voice channel creation is enabled for this server. "
                    "There's no need to suggest existing voice channels. "
                    "New channels will be created automatically."
                ),
                ephemeral=True,
            )
            return

        await self.services.guilds.set_suggest_vc_category(category)
        if category:
            msg = f'Suggested voice channels category prefix set to "{category}".'
        else:
            msg = "Suggested voice channels turned off."
        await safe_send_channel(self.interaction, msg, ephemeral=True)

    async def set_motd(self, message: str | None = None) -> None:
        await self.services.guilds.set_motd(message)
        await safe_send_channel(self.interaction, "Message of the day updated.", ephemeral=True)

    async def refresh_setup(self) -> None:
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_show_links(self) -> None:
        await self.services.guilds.toggle_show_links()
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_voice_create(self) -> None:
        await self.services.guilds.toggle_voice_create()
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_use_max_bitrate(self) -> None:
        await self.services.guilds.toggle_use_max_bitrate()
        embed = await self._build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def set_default_seats(self, seats: int) -> None:
        assert self.interaction.channel_id is not None
        await self.services.channels.set_default_seats(self.interaction.channel_id, seats)
        await safe_send_channel(
            self.interaction,
            f"Default seats set to {seats} for this channel.",
            ephemeral=True,
        )

    async def set_default_format(self, format: int) -> None:
        assert self.interaction.channel_id is not None
        await self.services.channels.set_default_format(self.interaction.channel_id, format)
        await safe_send_channel(
            self.interaction,
            f"Default format set to {GameFormat(format)} for this channel.",
            ephemeral=True,
        )

    async def set_default_bracket(self, bracket: int) -> None:
        assert self.interaction.channel_id is not None
        await self.services.channels.set_default_bracket(self.interaction.channel_id, bracket)
        await safe_send_channel(
            self.interaction,
            f"Default bracket set to {GameBracket(bracket)} for this channel.",
            ephemeral=True,
        )

    async def set_default_service(self, service: int) -> None:
        assert self.interaction.channel_id is not None
        await self.services.channels.set_default_service(self.interaction.channel_id, service)
        await safe_send_channel(
            self.interaction,
            f"Default service set to {GameService(service)} for this channel.",
            ephemeral=True,
        )

    async def set_auto_verify(self, setting: bool) -> None:
        assert self.interaction.channel_id is not None
        await self.services.channels.set_auto_verify(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            f"Auto verification set to {setting} for this channel.",
            ephemeral=True,
        )

    async def set_verified_only(self, setting: bool) -> None:
        assert self.interaction.channel_id is not None
        await self.services.channels.set_verified_only(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            f"Verified only set to {setting} for this channel.",
            ephemeral=True,
        )

    async def set_unverified_only(self, setting: bool) -> None:
        assert self.interaction.channel_id is not None
        await self.services.channels.set_unverified_only(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            f"Unverified only set to {setting} for this channel.",
            ephemeral=True,
        )

    async def set_channel_motd(self, message: str | None = None) -> None:
        assert self.interaction.channel_id is not None
        setting = await self.services.channels.set_motd(self.interaction.channel_id, message)
        await safe_send_channel(
            self.interaction,
            f"Message of the day for this channel has been set to: {setting}",
            ephemeral=True,
        )

    async def set_channel_extra(self, message: str | None = None) -> None:
        assert self.interaction.channel_id is not None
        setting = await self.services.channels.set_extra(self.interaction.channel_id, message)
        await safe_send_channel(
            self.interaction,
            f"Extra message for this channel has been set to: {setting}",
            ephemeral=True,
        )

    async def set_voice_category(self, value: str) -> None:
        assert self.interaction.channel_id is not None
        setting = await self.services.channels.set_voice_category(
            self.interaction.channel_id,
            value,
        )
        await safe_send_channel(
            self.interaction,
            f"Voice category prefix for this channel has been set to: {setting}",
            ephemeral=True,
        )

    async def set_delete_expired(self, value: bool) -> None:
        assert self.interaction.channel_id is not None
        setting = await self.services.channels.set_delete_expired(
            self.interaction.channel_id,
            value,
        )
        await safe_send_channel(
            self.interaction,
            f"Delete expired setting for this channel has been set to: {setting}",
            ephemeral=True,
        )

    async def set_blind_games(self, value: bool) -> None:
        assert self.interaction.channel_id is not None
        setting = await self.services.channels.set_blind_games(self.interaction.channel_id, value)
        await safe_send_channel(
            self.interaction,
            f"Hidden player names for this channel has been set to: {setting}",
            ephemeral=True,
        )

    async def set_voice_invite(self, value: bool) -> None:
        assert self.interaction.channel_id is not None
        setting = await self.services.channels.set_voice_invite(self.interaction.channel_id, value)
        await safe_send_channel(
            self.interaction,
            f"Voice invite setting for this channel has been set to: {setting}",
            ephemeral=True,
        )

    async def move_user(
        self,
        guild_xid: int,
        from_user_xid: int,
        to_user_xid: int,
    ) -> None:  # pragma: no cover
        if error := await self.services.users.move_user(guild_xid, from_user_xid, to_user_xid):
            await safe_send_channel(self.interaction, f"Error: {error}", ephemeral=True)
            return
        await safe_send_channel(
            self.interaction,
            f"User {from_user_xid} has been moved to {to_user_xid}",
            ephemeral=True,
        )
