# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from ddtrace.trace import tracer
from discord import ui

from spellbot.i18n import t
from spellbot.metrics import add_span_context
from spellbot.operations import safe_defer_interaction, safe_original_response

from . import BaseView

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from spellbot import SpellBot


class GameButton(ui.Button["GameView"]):
    """A button that forwards clicks to the given handler."""

    def __init__(
        self,
        handler: Callable[[discord.Interaction[Any]], Awaitable[None]],
        *,
        custom_id: str,
        emoji: str,
        label: str,
        style: discord.ButtonStyle,
    ) -> None:
        super().__init__(custom_id=custom_id, emoji=emoji, label=label, style=style)
        self.handler = handler

    async def callback(self, interaction: discord.Interaction[Any]) -> None:
        await self.handler(interaction)


class GameView(BaseView):
    def __init__(self, bot: SpellBot, locale: str = "en") -> None:
        super().__init__(bot)

        join_button = GameButton(
            self.join,
            custom_id="join",
            emoji="✋",
            label=t("button.join", locale=locale),
            style=discord.ButtonStyle.blurple,
        )
        self.add_item(join_button)

        leave_button = GameButton(
            self.leave,
            custom_id="leave",
            emoji="🚫",
            label=t("button.leave", locale=locale),
            style=discord.ButtonStyle.gray,
        )
        self.add_item(leave_button)

    async def join(self, interaction: discord.Interaction[Any]) -> None:
        from spellbot.actions import LookingForGameAction  # allow_inline: circular import

        assert interaction.guild is not None
        with tracer.trace(name="interaction", resource="join"):
            add_span_context(interaction)
            if not await safe_defer_interaction(interaction):
                return
            async with (
                self.bot.guild_lock(interaction.guild.id),
                LookingForGameAction.create(self.bot, interaction) as action,
            ):
                original_response = await safe_original_response(interaction)
                if original_response:
                    await action.execute(message_xid=original_response.id)

    async def leave(self, interaction: discord.Interaction[Any]) -> None:
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
