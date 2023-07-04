from __future__ import annotations

import discord
from ddtrace import tracer
from discord import ui

from ..client import SpellBot
from ..metrics import add_span_context
from ..operations import safe_defer_interaction, safe_original_response
from . import BaseView


class PendingGameView(BaseView):
    @ui.button(
        custom_id="join",
        emoji="✋",
        label="Join this game!",
        style=discord.ButtonStyle.blurple,
    )
    async def join(
        self,
        interaction: discord.Interaction,
        button: ui.Button["PendingGameView"],
    ) -> None:
        from ..actions import LookingForGameAction

        assert interaction.guild is not None
        with tracer.trace(name="interaction", resource="join"):  # type: ignore
            add_span_context(interaction)
            assert interaction.original_response
            await safe_defer_interaction(interaction)
            async with self.bot.guild_lock(interaction.guild.id):
                async with LookingForGameAction.create(self.bot, interaction) as action:
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
        button: ui.Button["PendingGameView"],
    ) -> None:
        from ..actions import LeaveAction

        assert interaction.guild is not None
        with tracer.trace(name="interaction", resource="leave"):  # type: ignore
            add_span_context(interaction)
            await safe_defer_interaction(interaction)
            async with self.bot.guild_lock(interaction.guild.id):
                async with LeaveAction.create(self.bot, interaction) as action:
                    await action.execute(origin=True)


class StartedGameView(BaseView):
    def __init__(self, bot: SpellBot) -> None:
        super().__init__(bot)
        self.add_item(StartedGameSelect(self.bot))


class StartedGameSelect(ui.Select[StartedGameView]):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot
        super().__init__(
            custom_id="points",
            placeholder="How many points do you have to report?",
            options=[
                discord.SelectOption(label="No points", value="0", emoji="0️⃣"),
                discord.SelectOption(label="One point", value="1", emoji="1️⃣"),
                discord.SelectOption(label="Two points", value="2", emoji="2️⃣"),
                discord.SelectOption(label="Three points", value="3", emoji="3️⃣"),
                discord.SelectOption(label="Four points", value="4", emoji="4️⃣"),
                discord.SelectOption(label="Five points", value="5", emoji="5️⃣"),
                discord.SelectOption(label="Six points", value="6", emoji="6️⃣"),
                discord.SelectOption(label="Seven points", value="7", emoji="7️⃣"),
                discord.SelectOption(label="Eight points", value="8", emoji="8️⃣"),
                discord.SelectOption(label="Nine points", value="9", emoji="9️⃣"),
                discord.SelectOption(label="Ten points", value="10", emoji="🔟"),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        from ..actions import LookingForGameAction

        with tracer.trace(name="interaction", resource="points"):  # type: ignore
            add_span_context(interaction)
            await safe_defer_interaction(interaction)
            assert interaction.original_response
            points = int(self.values[0])
            async with LookingForGameAction.create(self.bot, interaction) as action:
                original_response = await safe_original_response(interaction)
                if original_response:
                    await action.add_points(original_response, points)
