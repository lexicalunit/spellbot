from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
import httpx
from ddtrace.trace import tracer
from discord import app_commands
from discord.ext import commands

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.integrations.playgroup_live import TIMEOUT_S, lookup_playgroup_user
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild

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
    @tracer.wrap(name="interaction", resource="playgroup_link")
    async def link(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        await interaction.response.defer(ephemeral=True)

        async with db_session_manager():
            user_data = await services.users.get(interaction.user.id)

            if user_data and user_data.playgroup_user_id is not None:
                await interaction.followup.send(
                    "Your Discord account is already linked to Playgroup Live!",
                    ephemeral=True,
                )
                return

            timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
            async with httpx.AsyncClient(timeout=timeout) as client:
                playgroup_user_id, username = await lookup_playgroup_user(
                    client,
                    interaction.user.id,
                )

            if playgroup_user_id is not None:
                await services.users.set_playgroup_user_id(
                    interaction.user.id,
                    playgroup_user_id,
                )
                await interaction.followup.send(
                    f"Linked! Welcome, **{username}**. "
                    "Your Playgroup Live games will now be attributed to your account.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "No Playgroup account found for your Discord. "
                    "Go to <https://playgroup.gg/profiles> and click **Link Discord**, "
                    "then run `/playgroup link` again to confirm.",
                    ephemeral=True,
                )


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(PlaygroupCog(bot), guild=settings.GUILD_OBJECT)
