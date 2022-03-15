from __future__ import annotations

import discord

from .. import SpellBot
from ..utils import handle_view_errors


class BaseView(discord.ui.View):
    def __init__(self, bot: SpellBot):
        super().__init__(timeout=None)
        self.bot = bot
        self.on_error = handle_view_errors
