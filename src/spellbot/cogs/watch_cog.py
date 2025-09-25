from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.ext import commands

from spellbot.actions import WatchAction
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_admin, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_admin))
@for_all_callbacks(app_commands.check(is_guild))
class WatchCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="watched",
        description="View the current list of watched users with notes.",
    )
    @app_commands.describe(page="If there are multiple pages of output, which one?")
    @tracer.wrap(name="interaction", resource="watched")
    async def watched(self, interaction: discord.Interaction, page: int | None = 1) -> None:
        add_span_context(interaction)
        async with WatchAction.create(self.bot, interaction) as action:
            assert page
            assert page >= 1
            await action.watched(page=page)

    @app_commands.command(
        name="watch",
        description="Moderators should receive notifications about this user's activity.",
    )
    @app_commands.describe(target="User to watch")
    @app_commands.describe(note="A note about why this using is being watched")
    # @tracer.wrap(name="interaction", resource="watch")
    # There's a bug when combining `@tracer.wrap`, `@app_commands.describe` and discord.User.
    # See: https://github.com/Rapptz/discord.py/issues/10317.
    async def watch(
        self,
        interaction: discord.Interaction,
        target: discord.User | discord.Member | None = None,
        id: str | None = None,
        note: str | None = None,
    ) -> None:
        with tracer.trace("interaction", resource="watch"):
            add_span_context(interaction)
            async with WatchAction.create(self.bot, interaction) as action:
                await action.watch(target=target, id=id, note=note)

    @app_commands.command(
        name="unwatch",
        description="No longer receive notifications about this user's activity.",
    )
    @app_commands.describe(target="User to unwatch")
    @app_commands.describe(id="ID of a user to unwatch")
    # @tracer.wrap(name="interaction", resource="unwatch")
    # There's a bug when combining `@tracer.wrap`, `@app_commands.describe` and discord.User.
    # See: https://github.com/Rapptz/discord.py/issues/10317.
    async def unwatch(
        self,
        interaction: discord.Interaction,
        target: discord.User | discord.Member | None = None,
        id: str | None = None,
    ) -> None:
        with tracer.trace("interaction", resource="unwatch"):
            add_span_context(interaction)
            async with WatchAction.create(self.bot, interaction) as action:
                await action.unwatch(target=target, id=id)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(WatchCog(bot), guild=settings.GUILD_OBJECT)
