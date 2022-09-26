from __future__ import annotations

import logging
from typing import Any

import discord

from .. import SpellBot
from ..models import GameFormat
from ..operations import safe_followup_channel, safe_send_channel
from ..settings import Settings
from ..views import TourneyView
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ToruneyAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction):
        super().__init__(bot, interaction)
        self.settings = Settings()

    async def create_tourney(
        self,
        name: str,
        format: GameFormat,
        description: str,
    ) -> None:
        await self.services.tourneys.create(
            guild_xid=self.interaction.guild_id,
            channel_xid=self.interaction.channel_id,
            name=name,
            description=description,
            format=format.value,
        )
        embed = await self.services.tourneys.to_embed()
        view = TourneyView(self.bot)
        post = await safe_send_channel(self.interaction, embed=embed, view=view)
        assert post
        await self.services.tourneys.set_message_xid(post.id)

    async def signup(self) -> None:
        await safe_followup_channel(self.interaction, "signup")

    async def drop(self) -> None:
        await safe_followup_channel(self.interaction, "drop")

    async def set_format(self, message_xid: int, format: GameFormat) -> None:
        await safe_followup_channel(self.interaction, f"({message_xid})format: {format}")
