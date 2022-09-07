import logging

import discord
from ddtrace import tracer
from discord import app_commands
from discord.ext import commands

from .. import SpellBot
from ..actions import BlockAction
from ..metrics import add_span_context
from ..utils import for_all_callbacks, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class BlockCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @app_commands.command(
        name="block",
        description="Block another user from joining your games.",
    )
    @app_commands.describe(target="The user to block")
    @tracer.wrap(name="interaction", resource="block")
    async def block(self, interaction: discord.Interaction, target: discord.Member):
        add_span_context(interaction)
        async with BlockAction.create(self.bot, interaction) as action:
            await action.block(target=target)

    @app_commands.command(
        name="unblock",
        description="Unblock a user you've previously blocked.",
    )
    @app_commands.describe(target="The user to unblock")
    @tracer.wrap(name="interaction", resource="unblock")
    async def unblock(self, interaction: discord.Interaction, target: discord.Member):
        add_span_context(interaction)
        async with BlockAction.create(self.bot, interaction) as action:
            await action.unblock(target=target)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(BlockCog(bot), guild=bot.settings.GUILD_OBJECT)
