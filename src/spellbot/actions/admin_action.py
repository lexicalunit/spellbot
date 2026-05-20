from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.embeds import Embed

from spellbot import services
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.i18n import guild_locale, t
from spellbot.models import Channel, GuildAward
from spellbot.operations import (
    safe_delete_message,
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_send_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.settings import settings
from spellbot.utils import EMBED_DESCRIPTION_SIZE_LIMIT, generate_signed_url
from spellbot.views import SetupView

from .base_action import BaseAction

if TYPE_CHECKING:
    from spellbot import SpellBot
    from spellbot.data import ChannelData, GuildAwardData

logger = logging.getLogger(__name__)


def humanize_bool(setting: bool, locale: str = "en") -> str:
    return t("admin.on", locale=locale) if setting else t("admin.off", locale=locale)


def award_line(award: GuildAwardData, locale: str = "en") -> str:
    give_or_take = (
        t("award.action_take", locale=locale)
        if award.remove
        else t("award.action_give", locale=locale)
    )
    verified_only = t("award.verified_only", locale=locale) if award.verified_only else ""
    unverified_only = t("award.unverified_only", locale=locale) if award.unverified_only else ""
    verify_status = (
        f" ({verified_only}{unverified_only}) " if verified_only or unverified_only else " "
    )
    key = "award.line_every" if award.repeating else "award.line_after"
    return t(
        key,
        locale=locale,
        id=award.id,
        count=award.count,
        action=give_or_take,
        role=award.role,
        verify_status=verify_status,
        message=award.message,
    )


class AdminAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)

    async def report_failure(self) -> None:
        locale = guild_locale(self.guild)
        await safe_send_channel(
            self.interaction,
            t("admin.no_game_found", locale=locale),
            ephemeral=True,
        )

    async def build_channels_embeds(self) -> list[Embed]:  # noqa: C901
        assert self.guild_data is not None
        locale = guild_locale(self.guild)
        guild = self.guild_data
        embeds: list[Embed] = []

        def new_embed() -> Embed:
            embed = Embed(title=t("admin.channels_title", locale=locale, guild=guild.name))
            embed.set_thumbnail(url=settings.ICO_URL)
            embed.color = discord.Color(settings.INFO_EMBED_COLOR)
            return embed

        def update_channel_settings(
            channel: ChannelData,
            channel_settings: dict[str, Any],
            col: str,
        ) -> None:
            is_enum = col in ("default_format", "default_service")
            value = getattr(channel, col).value if is_enum else getattr(channel, col)
            if value != getattr(Channel, col).default.arg:
                channel_settings[col] = str(getattr(channel, col)) if is_enum else value

        all_default = True
        embed = new_embed()
        description = ""
        for channel in sorted(guild.channels, key=lambda c: c.xid):
            discord_channel = await safe_fetch_text_channel(self.bot, guild.xid, channel.xid)
            if not discord_channel:
                await services.channels.forget(channel.xid)
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
                details = ", ".join(
                    (f"`{k}`" if isinstance(v, bool) and v else f"`{k}={v}`")
                    for k, v in channel_settings.items()
                )
                next_line = f"• <#{channel.xid}> ({channel.xid}) — {details}\n"
                if len(description) + len(next_line) >= EMBED_DESCRIPTION_SIZE_LIMIT:
                    embed.description = description
                    embeds.append(embed)
                    embed = new_embed()
                    description = ""
                description += next_line

        if all_default:
            description = t("admin.channels_default", locale=locale)

        embed.description = description
        embeds.append(embed)

        n = len(embeds)
        if n > 1:
            for i, embed in enumerate(embeds, start=1):
                embed.set_footer(text=t("admin.page", locale=locale, current=i, total=n))

        return embeds

    async def build_awards_embeds(self) -> list[Embed]:
        assert self.guild_data is not None
        locale = guild_locale(self.guild)
        guild = self.guild_data
        embeds: list[Embed] = []

        def new_embed() -> Embed:
            embed = Embed(title=t("admin.awards_title", locale=locale, guild=guild.name))
            embed.set_thumbnail(url=settings.ICO_URL)
            embed.color = discord.Color(settings.INFO_EMBED_COLOR)
            return embed

        has_at_least_one_award = False
        embed = new_embed()
        description = ""
        for award in guild.awards:
            has_at_least_one_award = True
            next_line = f"{award_line(award, locale)}\n"
            if len(description) + len(next_line) >= EMBED_DESCRIPTION_SIZE_LIMIT:
                embed.description = description
                embeds.append(embed)
                embed = new_embed()
                description = ""
            description += next_line

        if not has_at_least_one_award:
            description = t("admin.awards_empty", locale=locale)

        embed.description = description
        embeds.append(embed)

        n = len(embeds)
        if n > 1:
            for i, embed in enumerate(embeds, start=1):
                embed.set_footer(text=t("admin.page", locale=locale, current=i, total=n))

        return embeds

    async def build_setup_embed(self) -> Embed:
        assert self.guild_data is not None
        locale = guild_locale(self.guild)
        guild = self.guild_data
        embed = Embed(title=t("admin.setup_title", locale=locale, guild=guild.name))
        embed.set_thumbnail(url=settings.ICO_URL)
        description = t("admin.setup_description", locale=locale)

        embed.description = description[:EMBED_DESCRIPTION_SIZE_LIMIT]
        embed.add_field(
            name=t("admin.field_motd", locale=locale),
            value=guild.motd or t("admin.field_none", locale=locale),
            inline=False,
        )
        embed.add_field(
            name=t("admin.field_public_links", locale=locale),
            value=humanize_bool(guild.show_links, locale),
        )
        embed.add_field(
            name=t("admin.field_voice_create", locale=locale),
            value=humanize_bool(guild.voice_create, locale),
        )
        embed.add_field(
            name=t("admin.field_max_bitrate", locale=locale),
            value=humanize_bool(guild.use_max_bitrate, locale),
        )
        embed.color = discord.Color(settings.INFO_EMBED_COLOR)
        return embed

    async def forget_channel(self, channel_str: str) -> None:
        locale = guild_locale(self.guild)
        try:
            channel_xid = int(channel_str)
        except ValueError:
            await safe_send_channel(
                self.interaction,
                t("admin.invalid_id", locale=locale),
                ephemeral=True,
            )
            return

        await services.channels.forget(channel_xid)
        await safe_send_channel(self.interaction, t("admin.done", locale=locale), ephemeral=True)

    async def info(self, game_id: str) -> None:
        numeric_filter = filter(str.isdigit, game_id)
        numeric_string = "".join(numeric_filter)
        if not numeric_string:
            return await self.report_failure()
        game_id_int = int(numeric_string)

        found = await services.games.get(game_id_int)
        if not found:
            return await self.report_failure()

        embed = found.to_embed(
            guild=self.guild,
            dm=True,
            emojis=self.bot.emojis_cache,
            supporters=self.bot.supporters,
        )
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
        return None

    async def setup(self) -> None:
        embed = await self.build_setup_embed()
        view = SetupView(self.bot)
        await safe_send_channel(self.interaction, embed=embed, view=view)

    async def setup_mythic_track(self) -> None:
        assert self.guild is not None
        assert self.guild_data is not None
        locale = guild_locale(self.guild)
        self.guild_data = await services.guilds.setup_mythic_track(self.guild_data)
        embed = Embed(title=t("admin.mythic_track_title", locale=locale, guild=self.guild.name))
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.color = discord.Color(settings.INFO_EMBED_COLOR)
        GUIDE = "https://www.mythictrack.com/spellbot"
        if self.guild_data.enable_mythic_track:
            embed.description = t("admin.mythic_track_on", locale=locale, guide=GUIDE)
        else:
            embed.description = t("admin.mythic_track_off", locale=locale)
        await safe_send_channel(self.interaction, embed=embed)

    async def channels(self, page: int) -> None:
        locale = guild_locale(self.guild)
        embeds = await self.build_channels_embeds()
        try:
            await safe_send_channel(self.interaction, embed=embeds[page - 1])
        except IndexError:
            await safe_send_channel(
                self.interaction,
                t("admin.invalid_page", locale=locale),
                ephemeral=True,
            )

    async def awards(self, page: int) -> None:
        locale = guild_locale(self.guild)
        embeds = await self.build_awards_embeds()
        try:
            await safe_send_channel(self.interaction, embed=embeds[page - 1])
        except IndexError:
            await safe_send_channel(
                self.interaction,
                t("admin.invalid_page", locale=locale),
                ephemeral=True,
            )

    async def award_add(
        self,
        count: int,
        role: str,
        message: str,
        **options: bool | None,
    ) -> None:
        locale = guild_locale(self.guild)
        repeating = bool(options.get("repeating", False))
        remove = bool(options.get("remove", False))
        verified_only = bool(options.get("verified_only", False))
        unverified_only = bool(options.get("unverified_only", False))

        if verified_only and unverified_only:
            await safe_send_channel(
                self.interaction,
                t("admin.award_add_conflict", locale=locale),
                ephemeral=True,
            )
            return

        max_message_len = GuildAward.message.property.columns[0].type.length
        if len(message) > max_message_len:
            await safe_send_channel(
                self.interaction,
                t("admin.award_message_too_long", locale=locale, max_length=max_message_len),
                ephemeral=True,
            )
            return

        if count < 1:
            await safe_send_channel(
                self.interaction,
                t("admin.award_zero_games", locale=locale),
                ephemeral=True,
            )
            return

        assert self.guild_data is not None
        award = await services.guilds.award_add(
            self.guild_data.xid,
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
        embed.set_author(name=t("admin.award_added", locale=locale))
        line = award_line(award, locale)
        description = f"{line}\n\n{t('admin.award_added_view', locale=locale)}"
        embed.description = description
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def award_delete(self, guild_award_id: int) -> None:
        locale = guild_locale(self.guild)
        await services.guilds.award_delete(guild_award_id)
        embed = Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=t("admin.award_deleted", locale=locale))
        description = t("admin.award_added_view", locale=locale)
        embed.description = description
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def set_suggest_vc_category(self, category: str | None) -> None:
        assert self.guild_data is not None
        locale = guild_locale(self.guild)
        if self.guild_data.voice_create:
            await safe_send_channel(
                self.interaction,
                t("admin.voice_create_on", locale=locale),
                ephemeral=True,
            )
            return

        self.guild_data = await services.guilds.set_suggest_vc_category(
            self.guild_data,
            category,
        )
        if category:
            msg = t("admin.suggest_vc_set", locale=locale, category=category)
        else:
            msg = t("admin.suggest_vc_off", locale=locale)
        await safe_send_channel(self.interaction, msg, ephemeral=True)

    async def set_motd(self, message: str | None = None) -> None:
        assert self.guild_data
        locale = guild_locale(self.guild)
        await services.guilds.set_motd(self.guild_data, message)
        await safe_send_channel(
            self.interaction,
            t("admin.motd_updated", locale=locale),
            ephemeral=True,
        )

    async def refresh_setup(self) -> None:
        embed = await self.build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_show_links(self) -> None:
        assert self.guild_data is not None
        self.guild_data = await services.guilds.toggle_show_links(self.guild_data)
        embed = await self.build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_voice_create(self) -> None:
        assert self.guild_data is not None
        self.guild_data = await services.guilds.toggle_voice_create(self.guild_data)
        embed = await self.build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def toggle_use_max_bitrate(self) -> None:
        assert self.guild_data is not None
        self.guild_data = await services.guilds.toggle_use_max_bitrate(self.guild_data)
        embed = await self.build_setup_embed()
        view = SetupView(self.bot)
        await safe_update_embed_origin(self.interaction, embed=embed, view=view)

    async def set_default_seats(self, seats: int) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        await services.channels.set_default_seats(self.interaction.channel_id, seats)
        await safe_send_channel(
            self.interaction,
            t("admin.default_seats_set", locale=locale, seats=seats),
            ephemeral=True,
        )

    async def set_default_format(self, format: int) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        await services.channels.set_default_format(self.interaction.channel_id, format)
        await safe_send_channel(
            self.interaction,
            t("admin.default_format_set", locale=locale, format=str(GameFormat(format))),
            ephemeral=True,
        )

    async def set_default_bracket(self, bracket: int) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        await services.channels.set_default_bracket(self.interaction.channel_id, bracket)
        await safe_send_channel(
            self.interaction,
            t("admin.default_bracket_set", locale=locale, bracket=str(GameBracket(bracket))),
            ephemeral=True,
        )

    async def set_default_service(self, service: int) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        await services.channels.set_default_service(self.interaction.channel_id, service)
        await safe_send_channel(
            self.interaction,
            t("admin.default_service_set", locale=locale, service=str(GameService(service))),
            ephemeral=True,
        )

    async def set_auto_verify(self, setting: bool) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        await services.channels.set_auto_verify(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            t("admin.auto_verify_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_verified_only(self, setting: bool) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        await services.channels.set_verified_only(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            t("admin.verified_only_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_unverified_only(self, setting: bool) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        await services.channels.set_unverified_only(self.interaction.channel_id, setting)
        await safe_send_channel(
            self.interaction,
            t("admin.unverified_only_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_channel_motd(self, message: str | None = None) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        setting = await services.channels.set_motd(self.interaction.channel_id, message)
        await safe_send_channel(
            self.interaction,
            t("admin.channel_motd_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_channel_extra(self, message: str | None = None) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        setting = await services.channels.set_extra(self.interaction.channel_id, message)
        await safe_send_channel(
            self.interaction,
            t("admin.channel_extra_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_voice_category(self, value: str) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        setting = await services.channels.set_voice_category(
            self.interaction.channel_id,
            value,
        )
        await safe_send_channel(
            self.interaction,
            t("admin.voice_category_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_delete_expired(self, value: bool) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        setting = await services.channels.set_delete_expired(
            self.interaction.channel_id,
            value,
        )
        await safe_send_channel(
            self.interaction,
            t("admin.delete_expired_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_blind_games(self, value: bool) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        setting = await services.channels.set_blind_games(self.interaction.channel_id, value)
        await safe_send_channel(
            self.interaction,
            t("admin.blind_games_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def set_voice_invite(self, value: bool) -> None:
        assert self.interaction.channel_id is not None
        locale = guild_locale(self.guild)
        setting = await services.channels.set_voice_invite(self.interaction.channel_id, value)
        await safe_send_channel(
            self.interaction,
            t("admin.voice_invite_set", locale=locale, setting=setting),
            ephemeral=True,
        )

    async def move_user(
        self,
        guild_xid: int,
        from_user_xid: int,
        to_user_xid: int,
    ) -> None:  # pragma: no cover
        locale = guild_locale(self.guild)
        if error := await services.users.move_user(guild_xid, from_user_xid, to_user_xid):
            await safe_send_channel(
                self.interaction,
                t("admin.user_move_error", locale=locale, error=error),
                ephemeral=True,
            )
            return
        await safe_send_channel(
            self.interaction,
            t("admin.user_moved", locale=locale, from_user=from_user_xid, to_user=to_user_xid),
            ephemeral=True,
        )

    async def expire_games(self, guild_xid: int) -> None:
        locale = guild_locale(self.guild)
        results = []
        games = await services.games.inactive_games(guild_xid)

        batch = 0
        for game in games:
            game_id = game.id
            results.append(t("admin.expire_game", locale=locale, game_id=game_id))
            dequeued = await services.games.delete_games([game_id])
            results.append(t("admin.expire_dequeued", locale=locale, count=dequeued))

            for post_data in game.posts:
                guild_xid = post_data.guild_xid
                channel_xid = post_data.channel_xid
                message_xid = post_data.message_xid

                chan = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
                if not chan:
                    results.append(
                        t("admin.expire_no_channel", locale=locale, channel_id=channel_xid),
                    )
                    continue

                post = safe_get_partial_message(chan, guild_xid, message_xid)
                if not post:
                    results.append(
                        t("admin.expire_no_message", locale=locale, message_id=message_xid),
                    )
                    continue

                channel_data = await services.channels.select(channel_xid)
                if not dequeued or (channel_data and channel_data.delete_expired):
                    results.append(
                        t("admin.expire_deleting", locale=locale, message_id=message_xid),
                    )
                    if not await safe_delete_message(post):
                        results.append(t("admin.expire_no_permission", locale=locale))
                else:
                    results.append(
                        t("admin.expire_updating", locale=locale, message_id=message_xid),
                    )
                    if not await safe_update_embed(
                        post,
                        content=t("admin.game_expired", locale=locale),
                        embed=None,
                        view=None,
                    ):
                        results.append(t("admin.expire_no_permission", locale=locale))
                results.append(t("admin.expire_done", locale=locale))

            batch += 1
            if batch >= 5:  # pragma: no cover
                await asyncio.sleep(5)
                batch = 0
            else:
                await asyncio.sleep(1)

        message = "\n".join(results)
        if message:
            await safe_send_channel(self.interaction, f"```\n{message}\n```", ephemeral=True)
        else:
            await safe_send_channel(
                self.interaction,
                t("admin.expire_none", locale=locale),
                ephemeral=True,
            )

    async def user_info(self, target: discord.Member | discord.User) -> None:
        assert self.interaction.guild
        assert self.interaction.guild_id is not None
        locale = guild_locale(self.guild)
        guild_name = self.interaction.guild.name
        target_xid = target.id

        # Fetch all user stats
        games_count = await services.users.games_played_count(
            target_xid,
            self.interaction.guild_id,
        )
        blocked_by_count = await services.users.blocked_by_count(target_xid)
        watch_note = await services.users.is_watched(target_xid, self.interaction.guild_id)
        verified_status = await services.users.is_verified(
            target_xid,
            self.interaction.guild_id,
        )
        first_play, last_play = await services.users.play_date_range(
            target_xid,
            self.interaction.guild_id,
        )

        embed = Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=t("admin.user_info_title", locale=locale, name=target.display_name))
        embed.color = settings.INFO_EMBED_COLOR

        link = f"{settings.API_BASE_URL}/g/{self.interaction.guild_id}/u/{target_xid}"
        games_key = (
            "admin.user_info_games_one" if games_count == 1 else "admin.user_info_games_many"
        )
        games_text = t(games_key, locale=locale, count=games_count, guild=guild_name)
        embed.add_field(
            name=t("admin.user_info_games", locale=locale),
            value=games_text,
            inline=True,
        )

        blocked_key = (
            "admin.user_info_blocked_one"
            if blocked_by_count == 1
            else "admin.user_info_blocked_many"
        )
        block_text = t(blocked_key, locale=locale, count=blocked_by_count)
        embed.add_field(
            name=t("admin.user_info_block_status", locale=locale),
            value=block_text,
            inline=True,
        )

        if verified_status is None:
            verified_text = t("admin.user_info_verified_not_set", locale=locale)
        elif verified_status:
            verified_text = t("admin.user_info_verified_yes", locale=locale)
        else:
            verified_text = t("admin.user_info_verified_no", locale=locale)
        embed.add_field(
            name=t("admin.user_info_verified", locale=locale),
            value=verified_text,
            inline=True,
        )

        if watch_note is not None:
            watch_text = (
                t("admin.user_info_watched_with_note", locale=locale, note=watch_note)
                if watch_note
                else t("admin.user_info_watched", locale=locale)
            )
        else:
            watch_text = t("admin.user_info_not_watched", locale=locale)
        embed.add_field(
            name=t("admin.user_info_watch_status", locale=locale),
            value=watch_text,
            inline=True,
        )

        if first_play and last_play:
            first_str = first_play.strftime("%Y-%m-%d")
            last_str = last_play.strftime("%Y-%m-%d")
            range_text = first_str if first_str == last_str else f"{first_str} to {last_str}"
        else:
            range_text = t("admin.user_info_no_games", locale=locale)
        embed.add_field(
            name=t("admin.user_info_play_range", locale=locale),
            value=range_text,
            inline=True,
        )

        embed.add_field(
            name=t("admin.user_info_game_history", locale=locale),
            value=t("admin.user_info_view_link", locale=locale, link=link),
            inline=False,
        )

        embed.set_footer(text=t("admin.user_info_footer", locale=locale, user_id=target_xid))

        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def analytics(self) -> None:
        assert self.interaction.guild
        assert self.interaction.guild_id is not None
        locale = guild_locale(self.guild)

        EXPIRE_TIME = 15  # minutes
        url = generate_signed_url(
            guild_xid=self.interaction.guild_id,
            expires_in_minutes=EXPIRE_TIME,
        )

        embed = Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(
            name=t("admin.analytics_title", locale=locale, guild=self.interaction.guild.name),
        )
        embed.description = t(
            "admin.analytics_description",
            locale=locale,
            url=url,
            minutes=EXPIRE_TIME,
        )
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
