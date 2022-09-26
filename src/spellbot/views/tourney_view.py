from __future__ import annotations

from typing import Optional

import discord
from ddtrace import tracer
from discord import ui

from spellbot.models.game import GameFormat
from spellbot.operations import safe_channel_reply, safe_send_channel

from ..client import SpellBot
from ..metrics import add_span_context
from . import BaseView


class TourneyView(BaseView):
    def __init__(
        self,
        bot: SpellBot,
    ):
        super().__init__(bot)
        self.add_item(FormatSelect(self.bot))

    @ui.button(
        custom_id="signup",
        emoji="✋",
        label="Sign up for this tourney!",
        style=discord.ButtonStyle.blurple,
    )
    async def signup(
        self,
        interaction: discord.Interaction,
        button: ui.Button["TourneyView"],
    ) -> None:
        from ..actions import ToruneyAction

        assert interaction.channel_id is not None
        with tracer.trace(name="interaction", resource="drop"):  # type: ignore
            add_span_context(interaction)
            await interaction.response.defer()
            async with self.bot.channel_lock(interaction.channel_id):
                async with ToruneyAction.create(self.bot, interaction) as action:
                    await action.signup()

    @ui.button(
        custom_id="drop",
        emoji="🚫",
        label="Drop",
        style=discord.ButtonStyle.gray,
    )
    async def drop(
        self,
        interaction: discord.Interaction,
        button: ui.Button["TourneyView"],
    ) -> None:
        from ..actions import ToruneyAction

        assert interaction.channel_id is not None
        with tracer.trace(name="interaction", resource="drop"):  # type: ignore
            add_span_context(interaction)
            await interaction.response.defer()
            async with self.bot.channel_lock(interaction.channel_id):
                async with ToruneyAction.create(self.bot, interaction) as action:
                    await action.drop()


class FormatSelect(ui.Select[TourneyView]):
    def __init__(self, bot: SpellBot):
        self.bot = bot
        super().__init__(
            custom_id="format",
            placeholder=f"Format: {GameFormat.COMMANDER}",
            options=[
                discord.SelectOption(label=f"Format: {format}", value=f"{format.value}")
                for format in GameFormat
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        from ..actions import ToruneyAction

        assert interaction.channel_id is not None
        with tracer.trace(name="interaction", resource="drop"):  # type: ignore
            add_span_context(interaction)
            await interaction.response.defer()
            assert interaction.original_response
            async with self.bot.channel_lock(interaction.channel_id):
                async with ToruneyAction.create(self.bot, interaction) as action:
                    format_id = int(self.values[0])
                    format = GameFormat(format_id)
                    original_response = await interaction.original_response()
                    message_xid = original_response.id
                    await action.set_format(message_xid, format)
