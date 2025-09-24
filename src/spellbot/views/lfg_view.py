from __future__ import annotations

import discord
from ddtrace.trace import tracer
from discord import ui

from spellbot.metrics import add_span_context
from spellbot.operations import safe_defer_interaction, safe_original_response

from . import BaseView


class GameView(BaseView):
    @ui.button(
        custom_id="join",
        emoji="✋",
        label="Join this game!",
        style=discord.ButtonStyle.blurple,
    )
    async def join(
        self,
        interaction: discord.Interaction,
        button: ui.Button[GameView],
    ) -> None:
        from spellbot.actions import LookingForGameAction

        assert interaction.guild is not None
        with tracer.trace(name="interaction", resource="join"):
            add_span_context(interaction)
            assert interaction.original_response
            if not await safe_defer_interaction(interaction):
                return
            async with (
                self.bot.guild_lock(interaction.guild.id),
                LookingForGameAction.create(self.bot, interaction) as action,
            ):
                original_response = await safe_original_response(interaction)
                if original_response:
                    await action.execute(message_xid=original_response.id)

    @ui.button(
        custom_id="leave",
        emoji="🚫",
        label="Leave",
        style=discord.ButtonStyle.gray,
    )
    async def leave(
        self,
        interaction: discord.Interaction,
        button: ui.Button[GameView],
    ) -> None:
        from spellbot.actions import LeaveAction

        assert interaction.guild is not None
        with tracer.trace(name="interaction", resource="leave"):
            add_span_context(interaction)
            if not await safe_defer_interaction(interaction):
                return
            async with (
                self.bot.guild_lock(interaction.guild.id),
                LeaveAction.create(self.bot, interaction) as action,
            ):
                await action.execute(origin=True)
