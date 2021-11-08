import logging
from typing import Union

import discord
from discord_slash.context import InteractionContext

from .. import SpellBot
from ..operations import safe_send_channel
from ..settings import Settings
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class ScoreInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)

    async def execute(self, target: Union[discord.Member, discord.User]):
        assert self.ctx
        assert self.ctx.guild
        guild_name = self.ctx.guild.name
        assert hasattr(target, "id")
        target_xid = target.id  # type: ignore
        count = await self.services.plays.count(target_xid, self.ctx.guild_id)

        settings = Settings()
        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"Record of games played on {guild_name}")
        link = f"{settings.API_BASE_URL}/g/{self.ctx.guild_id}/u/{target_xid}"
        embed.description = (
            f"{target.mention} has played {count} game{'s' if count != 1 else ''}"
            " on this server.\n"
            f"View more [details on spellbot.io]({link})."
        )
        embed.color = settings.EMBED_COLOR
        await safe_send_channel(self.ctx, embed=embed, hidden=True)

    async def history(self):
        assert self.ctx
        assert self.ctx.channel
        channel_name = self.ctx.channel.name  # type: ignore
        channel_id = self.ctx.channel.id  # type: ignore

        settings = Settings()
        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"Recent games played in {channel_name}")
        link = f"{settings.API_BASE_URL}/g/{self.ctx.guild_id}/c/{channel_id}"
        embed.description = f"View [game history on spellbot.io]({link})."
        embed.color = settings.EMBED_COLOR
        await safe_send_channel(self.ctx, embed=embed, hidden=True)
