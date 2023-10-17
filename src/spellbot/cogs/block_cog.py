import logging
from typing import Optional

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
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="block",
        description="Block another user from joining your games.",
    )
    @app_commands.describe(target="The user to block")
    @tracer.wrap(name="interaction", resource="block")
    async def block(self, interaction: discord.Interaction, target: discord.Member) -> None:
        add_span_context(interaction)
        async with BlockAction.create(self.bot, interaction) as action:
            await action.block(target=target)

    @app_commands.command(
        name="unblock",
        description="Unblock a user you've previously blocked.",
    )
    @app_commands.describe(target="The user to unblock")
    @tracer.wrap(name="interaction", resource="unblock")
    async def unblock(self, interaction: discord.Interaction, target: discord.Member) -> None:
        add_span_context(interaction)
        async with BlockAction.create(self.bot, interaction) as action:
            await action.unblock(target=target)

    @app_commands.command(
        name="blocked",
        description="List all users you've blocked.",
    )
    @app_commands.describe(page="If there are multiple pages of output, which one?")
    @tracer.wrap(name="interaction", resource="blocked")
    async def blocked(self, interaction: discord.Interaction, page: Optional[int] = 1) -> None:
        add_span_context(interaction)
        async with BlockAction.create(self.bot, interaction) as action:
            page = page or 1
            await action.blocked(page=page)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(BlockCog(bot), guild=bot.settings.GUILD_OBJECT)
