import logging

import discord
from ddtrace import tracer
from discord import app_commands
from discord.ext import commands

from spellbot import SpellBot
from spellbot.actions.record_action import RecordAction
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class RecordCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(name="loss", description="Record a loss for your last game.")
    @tracer.wrap(name="interaction", resource="loss")
    async def loss(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with RecordAction.create(self.bot, interaction) as action:
            await action.loss()

    @app_commands.command(name="win", description="Record a win for your last game.")
    @tracer.wrap(name="interaction", resource="win")
    async def win(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with RecordAction.create(self.bot, interaction) as action:
            await action.win()

    @app_commands.command(name="tie", description="Record a tie for your last game.")
    @tracer.wrap(name="interaction", resource="tie")
    async def tie(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with RecordAction.create(self.bot, interaction) as action:
            await action.tie()

    @app_commands.command(name="confirm", description="Confirm your last game.")
    @tracer.wrap(name="interaction", resource="confirm")
    async def confirm(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with RecordAction.create(self.bot, interaction) as action:
            await action.confirm()

    @app_commands.command(name="check", description="Check your last game.")
    @tracer.wrap(name="interaction", resource="check")
    async def check(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with RecordAction.create(self.bot, interaction) as action:
            await action.check()

    @app_commands.command(name="elo", description="Check your current ELO.")
    @tracer.wrap(name="interaction", resource="elo")
    async def elo(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with RecordAction.create(self.bot, interaction) as action:
            await action.elo()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(RecordCog(bot), guild=settings.GUILD_OBJECT)
