# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

from spellbot.utils import handle_view_errors

if TYPE_CHECKING:
    from discord.ui import Item

    from spellbot import SpellBot


class BaseView(discord.ui.View):
    def __init__(self, bot: SpellBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    async def on_error(
        self,
        interaction: discord.Interaction[Any],
        error: Exception,
        item: Item[Any],
        /,
    ) -> None:  # pragma: no cover
        await handle_view_errors(interaction, error, item)
