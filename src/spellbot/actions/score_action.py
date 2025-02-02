from __future__ import annotations

import logging

import discord

from spellbot.operations import safe_send_channel
from spellbot.settings import settings

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ScoreAction(BaseAction):
    async def execute(self, target: discord.Member | discord.User) -> None:
        assert self.interaction.guild
        assert self.interaction.guild_id is not None
        guild_name = self.interaction.guild.name
        assert hasattr(target, "id")
        target_xid = target.id
        count = await self.services.plays.count(target_xid, self.interaction.guild_id)

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"Record of games played on {guild_name}")
        link = f"{settings.API_BASE_URL}/g/{self.interaction.guild_id}/u/{target_xid}"
        embed.description = (
            f"{target.mention} has played {count} game{'s' if count != 1 else ''}"
            " on this server.\n"
            f"View more [details on spellbot.io]({link})."
        )
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def history(self) -> None:
        assert self.interaction.channel
        assert hasattr(self.interaction.channel, "name")
        channel_name = self.interaction.channel.name  # type: ignore
        channel_xid = self.interaction.channel.id

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"Recent games played in {channel_name}")
        link = f"{settings.API_BASE_URL}/g/{self.interaction.guild_id}/c/{channel_xid}"
        embed.description = f"View [game history on spellbot.io]({link})."
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def top(self, monthly: bool, ago: int) -> None:
        if not monthly:
            ago = 0  # "months ago" doesn't make sense for "all time" range

        assert self.interaction.channel
        assert hasattr(self.interaction.channel, "name")
        channel_name = self.interaction.channel.name  # type: ignore
        channel_xid = self.interaction.channel.id
        guild_xid = self.interaction.guild_id

        assert guild_xid is not None
        data = await self.services.plays.top_records(guild_xid, channel_xid, monthly, ago)

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        range_s = f"{ago} months ago" if ago else "this month" if monthly else "all time"
        embed.title = f"Top players in #{channel_name} ({range_s})"
        description = ""
        description += "Rank \xa0\xa0\xa0 Games \xa0\xa0\xa0 Player\n"
        for rank, datum in enumerate(data):
            user_xid, count = datum
            description += f"{rank + 1:\xa0>6}\xa0{count:\xa0>20}\xa0\xa0\xa0<@{user_xid}>\n"
        embed.description = description
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
