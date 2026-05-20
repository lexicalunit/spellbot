from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import ui

from spellbot.i18n import t
from spellbot.metrics import add_span_context
from spellbot.operations import safe_defer_interaction, safe_original_response

from . import BaseView

if TYPE_CHECKING:
    from spellbot import SpellBot


class GameView(BaseView):
    def __init__(self, bot: SpellBot, locale: str = "en") -> None:
        super().__init__(bot)

        join_button = ui.Button[GameView](
            custom_id="join",
            emoji="✋",
            label=t("button.join", locale=locale),
            style=discord.ButtonStyle.blurple,
        )
        join_button.callback = self.join
        self.add_item(join_button)

        leave_button = ui.Button[GameView](
            custom_id="leave",
            emoji="🚫",
            label=t("button.leave", locale=locale),
            style=discord.ButtonStyle.gray,
        )
        leave_button.callback = self.leave
        self.add_item(leave_button)

    async def join(self, interaction: discord.Interaction) -> None:
        from spellbot.actions import LookingForGameAction  # allow_inline: circular import

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

    async def leave(self, interaction: discord.Interaction) -> None:
        from spellbot.actions import LeaveAction  # allow_inline: circular import

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
