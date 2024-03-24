from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ddtrace import tracer

from spellbot.operations import safe_send_channel

from .base_action import BaseAction

if TYPE_CHECKING:
    import discord

    from spellbot import SpellBot

logger = logging.getLogger(__name__)


class RecordAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)

    @tracer.wrap()
    async def process(self, user_xid: int, points: int) -> None:
        game = await self.services.games.select_last_ranked_game(user_xid)
        if game is None:
            await safe_send_channel(self.interaction, "no game found", ephemeral=True)
            return
        await self.services.games.add_points(user_xid, points)
        # TODO: Show ephemeral display showing current reported points
        await safe_send_channel(
            self.interaction,
            f"set points on game {game['id']} to {points}",
            ephemeral=True,
        )

    @tracer.wrap()
    async def loss(self) -> None:
        await self.process(self.interaction.user.id, 0)

    @tracer.wrap()
    async def win(self) -> None:
        await self.process(self.interaction.user.id, 3)

    @tracer.wrap()
    async def tie(self) -> None:
        await self.process(self.interaction.user.id, 1)

    @tracer.wrap()
    async def confirm(self) -> None:
        user_xid = self.interaction.user.id
        game = await self.services.games.select_last_ranked_game(user_xid)
        if game is None:
            await safe_send_channel(self.interaction, "no game found", ephemeral=True)
            return
        # TODO: Check that all users have reported points
        await self.services.games.confirm_points(user_xid)
        await safe_send_channel(
            self.interaction,
            f"confirm points on game {game['id']}",
            ephemeral=True,
        )

    @tracer.wrap()
    async def check(self) -> None:
        user_xid = self.interaction.user.id
        game = await self.services.games.select_last_ranked_game(user_xid)
        if game is None:
            await safe_send_channel(self.interaction, "no game found", ephemeral=True)
            return
        # TODO: Show ephemeral display showing current reported points
        await safe_send_channel(
            self.interaction,
            f"checking on game {game['id']}",
            ephemeral=True,
        )
