import logging
from typing import Union

import discord
from ddtrace import tracer
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashCommandOptionType

from .. import SpellBot
from ..interactions import VerifyInteraction
from ..metrics import add_span_context
from ..utils import for_all_callbacks, is_admin

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.check(is_admin))
@for_all_callbacks(commands.guild_only())
class VerifyCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(
        name="verify",
        description="Verify a user.",
        options=[
            {
                "name": "target",
                "required": True,
                "description": "User to verify",
                "type": SlashCommandOptionType.USER.value,
            },
        ],
    )
    @tracer.wrap(name="interaction", resource="verify")
    async def verify(
        self,
        ctx: SlashContext,
        target: Union[discord.User, discord.Member],
    ):
        add_span_context(ctx)
        async with VerifyInteraction.create(self.bot, ctx) as interaction:
            await interaction.verify(target=target)

    @cog_ext.cog_slash(
        name="unverify",
        description="Unverify a user.",
        options=[
            {
                "name": "target",
                "required": True,
                "description": "User to unverify",
                "type": SlashCommandOptionType.USER.value,
            },
        ],
    )
    @tracer.wrap(name="interaction", resource="unverify")
    async def unverify(
        self,
        ctx: SlashContext,
        target: Union[discord.User, discord.Member],
    ):
        add_span_context(ctx)
        async with VerifyInteraction.create(self.bot, ctx) as interaction:
            await interaction.unverify(target=target)


def setup(bot: SpellBot):
    bot.add_cog(VerifyCog(bot))
