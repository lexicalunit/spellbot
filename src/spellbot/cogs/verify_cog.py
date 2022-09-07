import logging
from typing import Union

import discord
from ddtrace import tracer
from discord import app_commands
from discord.ext import commands

from .. import SpellBot
from ..actions import VerifyAction
from ..metrics import add_span_context
from ..utils import for_all_callbacks, is_admin, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_admin))
@for_all_callbacks(app_commands.check(is_guild))
class VerifyCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @app_commands.command(name="verify", description="Verify a user.")
    @app_commands.describe(target="User to verify")
    @tracer.wrap(name="interaction", resource="verify")
    async def verify(
        self,
        interaction: discord.Interaction,
        target: Union[discord.User, discord.Member],
    ) -> None:
        add_span_context(interaction)
        async with VerifyAction.create(self.bot, interaction) as action:
            await action.verify(target=target)

    @app_commands.command(name="unverify", description="Unverify a user.")
    @app_commands.describe(target="User to unverify")
    @tracer.wrap(name="interaction", resource="unverify")
    async def unverify(
        self,
        interaction: discord.Interaction,
        target: Union[discord.User, discord.Member],
    ) -> None:
        add_span_context(interaction)
        async with VerifyAction.create(self.bot, interaction) as action:
            await action.unverify(target=target)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(VerifyCog(bot), guild=bot.settings.GUILD_OBJECT)
