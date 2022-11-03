from __future__ import annotations

import logging

import discord
from ddtrace import tracer

from ..metrics import add_span_context
from ..utils import is_admin
from ..views import BaseView

logger = logging.getLogger(__name__)


class SetupView(BaseView):
    async def interaction_check(  # pylint: disable=arguments-differ
        self,
        interaction: discord.Interaction,
    ) -> bool:
        return is_admin(interaction)

    @discord.ui.button(
        label="Toggle Public Links",
        style=discord.ButtonStyle.primary,
        custom_id="toggle_show_links",
        row=1,
    )
    async def toggle_show_links(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[SetupView],
    ) -> None:
        from ..actions.admin_action import AdminAction

        with tracer.trace(name="interaction", resource="toggle_show_links"):
            await interaction.response.defer()
            add_span_context(interaction)
            async with AdminAction.create(self.bot, interaction) as action:
                await action.toggle_show_links()

    @discord.ui.button(
        label="Toggle Create Voice Channels",
        style=discord.ButtonStyle.primary,
        custom_id="toggle_voice_create",
        row=1,
    )
    async def toggle_voice_create(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[SetupView],
    ) -> None:
        from ..actions.admin_action import AdminAction

        with tracer.trace(name="interaction", resource="toggle_voice_create"):
            await interaction.response.defer()
            add_span_context(interaction)
            async with AdminAction.create(self.bot, interaction) as action:
                await action.toggle_voice_create()

    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.secondary,
        custom_id="refresh_setup",
        row=2,
    )
    async def refresh_setup(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[SetupView],
    ) -> None:
        from ..actions.admin_action import AdminAction

        with tracer.trace(name="interaction", resource="refresh_setup"):
            await interaction.response.defer()
            add_span_context(interaction)
            async with AdminAction.create(self.bot, interaction) as action:
                await action.refresh_setup()
