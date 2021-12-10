import logging
from typing import Optional, Union

import discord
from ddtrace import tracer
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashCommandOptionType

from .. import SpellBot
from ..interactions import WatchInteraction
from ..utils import for_all_callbacks, is_admin

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.check(is_admin))
@for_all_callbacks(commands.guild_only())
class WatchCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(
        name="watched",
        description="View the current list of watched users with notes.",
    )
    @tracer.wrap()
    async def watched(self, ctx: SlashContext):
        async with WatchInteraction.create(self.bot, ctx) as interaction:
            await interaction.watched()

    @cog_ext.cog_slash(
        name="watch",
        description="Moderators should receive notifications about this user's activity.",
        options=[
            {
                "name": "target",
                "required": True,
                "description": "User to watch",
                "type": SlashCommandOptionType.USER.value,
            },
            {
                "name": "note",
                "required": False,
                "description": "A note about why this using is being watched",
                "type": SlashCommandOptionType.STRING.value,
            },
        ],
    )
    @tracer.wrap()
    async def watch(
        self,
        ctx: SlashContext,
        target: Union[discord.User, discord.Member],
        note: Optional[str] = None,
    ):
        async with WatchInteraction.create(self.bot, ctx) as interaction:
            await interaction.watch(target=target, note=note)

    @cog_ext.cog_slash(
        name="unwatch",
        description="No longer receive notifications about this user's activity.",
        options=[
            {
                "name": "target",
                "required": True,
                "description": "User to unwatch",
                "type": SlashCommandOptionType.USER.value,
            },
        ],
    )
    @tracer.wrap()
    async def unwatch(
        self,
        ctx: SlashContext,
        target: Union[discord.User, discord.Member],
    ):
        async with WatchInteraction.create(self.bot, ctx) as interaction:
            await interaction.unwatch(target=target)


def setup(bot: SpellBot):
    bot.add_cog(WatchCog(bot))
