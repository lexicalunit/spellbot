from __future__ import annotations

import logging

import discord

from spellbot.operations import safe_send_channel
from spellbot.settings import settings
from spellbot.utils import generate_signed_url

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class AnalyticsAction(BaseAction):
    async def execute(self) -> None:
        assert self.interaction.guild
        assert self.interaction.guild_id is not None

        url = generate_signed_url(self.interaction.guild_id)

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"Server Analytics for {self.interaction.guild.name}")
        embed.description = (
            f"View your server's analytics dashboard:\n"
            f"📊 [Open Analytics]({url})\n\n"
            f"_This link expires in 10 minutes._"
        )
        embed.color = settings.INFO_EMBED_COLOR
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
