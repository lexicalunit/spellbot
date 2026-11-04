# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from spellbot.actions import PlaygroupAction
from spellbot.operations import safe_defer_interaction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild, traced_interaction

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from spellbot import SpellBot


@for_all_callbacks(app_commands.check(is_guild))
class PlaygroupCog(commands.Cog):
    playgroup = app_commands.Group(name="playgroup", description="Playgroup Live commands")

    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @playgroup.command(
        name="link",
        description="Link your Discord account to your Playgroup Live account.",
    )
    @app_commands.checks.cooldown(1, 60)
    @traced_interaction("playgroup_link")
    async def link(self, interaction: discord.Interaction) -> None:
        if not await safe_defer_interaction(interaction, ephemeral=True):
            return
        async with PlaygroupAction.create(self.bot, interaction) as action:
            await action.link()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(PlaygroupCog(bot), guild=settings.GUILD_OBJECT)
