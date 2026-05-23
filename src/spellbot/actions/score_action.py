from __future__ import annotations

import logging

import discord

from spellbot import services
from spellbot.i18n import t, user_locale
from spellbot.operations import safe_send_channel
from spellbot.settings import settings

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ScoreAction(BaseAction):
    async def execute(self, target: discord.Member | discord.User) -> None:
        assert self.interaction.guild
        assert self.interaction.guild_id is not None
        locale = user_locale(self.interaction)
        guild_name = self.interaction.guild.name
        assert hasattr(target, "id")
        target_xid = target.id
        count = await services.plays.count(target_xid, self.interaction.guild_id)

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=t("score.record_title", locale=locale, guild=guild_name))
        link = f"{settings.API_BASE_URL}/g/{self.interaction.guild_id}/u/{target_xid}"
        games_key = "score.games_one" if count == 1 else "score.games_many"
        embed.description = t(
            "score.record_description",
            locale=locale,
            mention=target.mention,
            games=t(games_key, locale=locale, count=count),
            link=link,
        )
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def history(self) -> None:
        assert self.interaction.channel
        assert hasattr(self.interaction.channel, "name")
        locale = user_locale(self.interaction)
        channel_name = self.interaction.channel.name  # type: ignore
        channel_xid = self.interaction.channel.id

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=t("score.history_title", locale=locale, channel=channel_name))
        link = f"{settings.API_BASE_URL}/g/{self.interaction.guild_id}/c/{channel_xid}"
        embed.description = t("score.history_description", locale=locale, link=link)
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def top(self, monthly: bool, ago: int) -> None:
        if not monthly:
            ago = 0  # "months ago" doesn't make sense for "all time" range

        assert self.interaction.channel
        assert hasattr(self.interaction.channel, "name")
        locale = user_locale(self.interaction)
        channel_name = self.interaction.channel.name  # type: ignore
        channel_xid = self.interaction.channel.id
        guild_xid = self.interaction.guild_id

        assert guild_xid is not None
        data = await services.plays.top_records(guild_xid, channel_xid, monthly, ago)

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        if ago:
            range_s = t("score.range_ago", locale=locale, months=ago)
        elif monthly:
            range_s = t("score.range_this_month", locale=locale)
        else:
            range_s = t("score.range_all_time", locale=locale)
        embed.title = t("score.top_title", locale=locale, channel=channel_name, range=range_s)
        description = ""
        description += t("score.top_header", locale=locale) + "\n"
        for rank, datum in enumerate(data):
            user_xid, count = datum
            description += f"{rank + 1:\xa0>6}\xa0{count:\xa0>20}\xa0\xa0\xa0<@{user_xid}>\n"
        embed.description = description
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
