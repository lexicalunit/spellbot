from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer

from spellbot.i18n import t
from spellbot.metrics import add_span_context
from spellbot.operations import safe_defer_interaction
from spellbot.utils import is_admin
from spellbot.views import BaseView

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


class SetupView(BaseView):
    def __init__(self, bot: SpellBot, locale: str = "en") -> None:
        super().__init__(bot)

        toggle_links_button = discord.ui.Button[SetupView](
            label=t("button.toggle_links", locale=locale),
            style=discord.ButtonStyle.primary,
            custom_id="toggle_show_links",
            row=1,
        )
        toggle_links_button.callback = self.toggle_show_links
        self.add_item(toggle_links_button)

        toggle_voice_button = discord.ui.Button[SetupView](
            label=t("button.toggle_voice", locale=locale),
            style=discord.ButtonStyle.primary,
            custom_id="toggle_voice_create",
            row=1,
        )
        toggle_voice_button.callback = self.toggle_voice_create
        self.add_item(toggle_voice_button)

        toggle_bitrate_button = discord.ui.Button[SetupView](
            label=t("button.toggle_bitrate", locale=locale),
            style=discord.ButtonStyle.primary,
            custom_id="toggle_use_max_bitrate",
            row=1,
        )
        toggle_bitrate_button.callback = self.toggle_use_max_bitrate
        self.add_item(toggle_bitrate_button)

        refresh_button = discord.ui.Button[SetupView](
            label=t("button.refresh", locale=locale),
            style=discord.ButtonStyle.secondary,
            custom_id="refresh_setup",
            row=2,
        )
        refresh_button.callback = self.refresh_setup
        self.add_item(refresh_button)

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        return is_admin(interaction)

    async def toggle_show_links(self, interaction: discord.Interaction) -> None:
        from spellbot.actions.admin_action import AdminAction  # allow_inline: circular import

        with tracer.trace(name="interaction", resource="toggle_show_links"):
            await safe_defer_interaction(interaction)
            add_span_context(interaction)
            async with AdminAction.create(self.bot, interaction) as action:
                await action.toggle_show_links()

    async def toggle_voice_create(self, interaction: discord.Interaction) -> None:
        from spellbot.actions.admin_action import AdminAction  # allow_inline: circular import

        with tracer.trace(name="interaction", resource="toggle_voice_create"):
            await safe_defer_interaction(interaction)
            add_span_context(interaction)
            async with AdminAction.create(self.bot, interaction) as action:
                await action.toggle_voice_create()

    async def toggle_use_max_bitrate(self, interaction: discord.Interaction) -> None:
        from spellbot.actions.admin_action import AdminAction  # allow_inline: circular import

        with tracer.trace(name="interaction", resource="toggle_use_max_bitrate"):
            await safe_defer_interaction(interaction)
            add_span_context(interaction)
            async with AdminAction.create(self.bot, interaction) as action:
                await action.toggle_use_max_bitrate()

    async def refresh_setup(self, interaction: discord.Interaction) -> None:
        from spellbot.actions.admin_action import AdminAction  # allow_inline: circular import

        with tracer.trace(name="interaction", resource="refresh_setup"):
            await safe_defer_interaction(interaction)
            add_span_context(interaction)
            async with AdminAction.create(self.bot, interaction) as action:
                await action.refresh_setup()
