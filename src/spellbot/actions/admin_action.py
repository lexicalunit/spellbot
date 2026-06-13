from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord.embeds import Embed

from spellbot import services
from spellbot.enums import GameBracket
from spellbot.i18n import guild_locale, t, user_locale
from spellbot.operations import (
    safe_delete_message,
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_send_channel,
    safe_update_embed,
)
from spellbot.settings import settings
from spellbot.utils import generate_signed_url

from .base_action import BaseAction

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


class AdminAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)

    async def report_failure(self) -> None:
        locale = user_locale(self.interaction)
        await safe_send_channel(
            self.interaction,
            t("admin.no_game_found", locale=locale),
            ephemeral=True,
        )

    async def game_info(self, game_id: str) -> None:
        numeric_filter = filter(str.isdigit, game_id)
        numeric_string = "".join(numeric_filter)
        if not numeric_string:
            return await self.report_failure()
        game_id_int = int(numeric_string)

        found = await services.games.get(game_id_int)
        if not found:
            return await self.report_failure()

        locale = user_locale(self.interaction)
        link = f"{settings.API_BASE_URL}/game/{found.id}"

        embed = Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=t("admin.game_info_title", locale=locale, game_id=found.id))
        embed.color = settings.INFO_EMBED_COLOR

        embed.add_field(
            name=t("game.field.format", locale=locale),
            value=found.format_name,
            inline=True,
        )
        if found.bracket != GameBracket.NONE.value:
            embed.add_field(
                name=t("game.field.bracket", locale=locale),
                value=found.bracket_name,
                inline=True,
            )
        embed.add_field(
            name=t("game.field.players", locale=locale),
            value=f"{len(found.players)}/{found.seats}",
            inline=True,
        )
        if found.started_at is not None:
            started_value = f"<t:{found.started_at_timestamp}>"
        else:
            started_value = t("admin.game_info_pending", locale=locale)
        embed.add_field(
            name=t("game.field.started_at", locale=locale),
            value=started_value,
            inline=True,
        )
        embed.add_field(
            name=t("admin.game_info_details", locale=locale),
            value=t("admin.view_link", locale=locale, link=link),
            inline=False,
        )

        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
        return None

    async def setup(self) -> None:
        assert self.guild_data is not None
        locale = guild_locale(self.guild)
        guild = self.guild_data
        link = f"{settings.API_BASE_URL}/g/{guild.xid}"
        embed = Embed(title=t("admin.setup_title", locale=locale, guild=guild.name))
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.description = t("admin.setup_description", locale=locale, link=link)
        embed.color = discord.Color(settings.INFO_EMBED_COLOR)
        await safe_send_channel(self.interaction, embed=embed)

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

    async def move_user(
        self,
        guild_xid: int,
        from_user_xid: int,
        to_user_xid: int,
    ) -> None:  # pragma: no cover
        locale = user_locale(self.interaction)
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
        user_loc = user_locale(self.interaction)
        results = []
        games = await services.games.inactive_games(guild_xid)

        batch = 0
        for game in games:
            game_id = game.id
            results.append(t("admin.expire_game", locale=user_loc, game_id=game_id))
            dequeued = await services.games.delete_games([game_id])
            results.append(t("admin.expire_dequeued", locale=user_loc, count=dequeued))

            for post_data in game.posts:
                guild_xid = post_data.guild_xid
                channel_xid = post_data.channel_xid
                message_xid = post_data.message_xid

                chan = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
                if not chan:
                    results.append(
                        t("admin.expire_no_channel", locale=user_loc, channel_id=channel_xid),
                    )
                    continue

                post = safe_get_partial_message(chan, guild_xid, message_xid)
                if not post:
                    results.append(
                        t("admin.expire_no_message", locale=user_loc, message_id=message_xid),
                    )
                    continue

                channel_data = await services.channels.select(channel_xid)
                if not dequeued or (channel_data and channel_data.delete_expired):
                    results.append(
                        t("admin.expire_deleting", locale=user_loc, message_id=message_xid),
                    )
                    if not await safe_delete_message(post):
                        results.append(t("admin.expire_no_permission", locale=user_loc))
                else:
                    results.append(
                        t("admin.expire_updating", locale=user_loc, message_id=message_xid),
                    )
                    guild_loc = guild_locale(self.guild)
                    if not await safe_update_embed(
                        post,
                        content=t("admin.game_expired", locale=guild_loc),
                        embed=None,
                        view=None,
                    ):
                        results.append(t("admin.expire_no_permission", locale=user_loc))
                results.append(t("admin.expire_done", locale=user_loc))

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
                t("admin.expire_none", locale=user_loc),
                ephemeral=True,
            )

    async def user_info(self, target: discord.Member | discord.User) -> None:
        assert self.interaction.guild
        assert self.interaction.guild_id is not None
        locale = user_locale(self.interaction)
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
            value=t("admin.view_link", locale=locale, link=link),
            inline=False,
        )

        embed.set_footer(text=t("admin.user_info_footer", locale=locale, user_id=target_xid))

        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def analytics(self) -> None:
        assert self.interaction.guild
        assert self.interaction.guild_id is not None
        locale = user_locale(self.interaction)

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
