from __future__ import annotations

import logging
from typing import Union

import discord

from ..operations import safe_send_channel
from ..settings import Settings
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ScoreAction(BaseAction):
    async def execute(self, target: Union[discord.Member, discord.User]):
        assert self.interaction.guild
        guild_name = self.interaction.guild.name
        assert hasattr(target, "id")
        target_xid = target.id
        count = await self.services.plays.count(target_xid, self.interaction.guild_id)

        settings = Settings()
        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"Record of games played on {guild_name}")
        link = f"{settings.API_BASE_URL}/g/{self.interaction.guild_id}/u/{target_xid}"
        embed.description = (
            f"{target.mention} has played {count} game{'s' if count != 1 else ''}"
            " on this server.\n"
            f"View more [details on spellbot.io]({link})."
        )
        embed.color = settings.EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    async def history(self):
        assert self.interaction.channel
        assert hasattr(self.interaction.channel, "name")
        channel_name = self.interaction.channel.name  # type: ignore
        channel_id = self.interaction.channel.id

        settings = Settings()
        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"Recent games played in {channel_name}")
        link = f"{settings.API_BASE_URL}/g/{self.interaction.guild_id}/c/{channel_id}"
        embed.description = f"View [game history on spellbot.io]({link})."
        embed.color = settings.EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
