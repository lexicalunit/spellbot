# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging

from ddtrace.trace import tracer

from spellbot import services
from spellbot.i18n import t, user_locale
from spellbot.operations import safe_original_response, safe_send_channel
from spellbot.views import GameView

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class LeaveAction(BaseAction):
    @tracer.wrap()
    async def handle_click(self) -> None:
        assert self.interaction.channel is not None
        assert self.user_data is not None
        channel_xid = self.interaction.channel.id
        if not await services.users.current_game_id(self.user_data, channel_xid):
            return

        original_response = await safe_original_response(self.interaction)
        origin_message_xid = original_response.id if original_response else None
        for game_data in await services.users.leave_game(self.user_data, channel_xid):
            await self.refresh_game_posts(
                game_data,
                delete_if_empty=True,
                origin_message_xid=origin_message_xid,
            )

    @tracer.wrap()
    async def handle_command(self) -> None:
        assert self.interaction.channel is not None
        assert self.user_data is not None
        channel_xid = self.interaction.channel.id
        if await services.users.current_game_id(self.user_data, channel_xid):
            for game_data in await services.users.leave_game(self.user_data, channel_xid):
                await self.refresh_game_posts(game_data, delete_if_empty=True)

        await safe_send_channel(
            self.interaction,
            t("leave.removed_channel", locale=user_locale(self.interaction)),
            ephemeral=True,
        )

    @tracer.wrap()
    async def execute(self, origin: bool = False) -> None:
        """Leave a game in the channel or the game clicked on by the user."""
        if origin:
            return await self.handle_click()
        return await self.handle_command()

    @tracer.wrap()
    async def execute_all(self) -> None:
        """Leave ALL games in ALL channels for this user."""
        for game_id in await services.games.dequeue_players([self.interaction.user.id]):
            game_data = await services.games.get(game_id)
            assert game_data is not None  # the game was just dequeued from, so it exists
            await self.refresh_game_posts(
                game_data,
                delete_if_empty=True,
                view=GameView(bot=self.bot, locale=game_data.locale),
            )

        await safe_send_channel(
            self.interaction,
            t("leave.removed_all", locale=user_locale(self.interaction)),
            ephemeral=True,
        )
