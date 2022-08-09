from __future__ import annotations

import logging

from ddtrace import tracer

from ..operations import (
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_send_channel,
    safe_send_user,
    safe_update_embed,
    safe_update_embed_origin,
)
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class LeaveAction(BaseAction):
    @tracer.wrap()
    async def _handle_click(self) -> None:
        if not (game_id := await self.services.users.current_game_id()):
            return

        found = await self.services.games.select(game_id)
        assert found

        game_data = await self.services.games.to_dict()
        if not (message_xid := game_data["message_xid"]):
            return

        original_response = await self.interaction.original_response()
        if original_response.id != message_xid:
            return await safe_send_user(
                self.interaction.user,
                "You're not in that game. Use the /leave command to leave a game.",
            )

        await self.services.users.leave_game()
        embed = await self.services.games.to_embed()
        await safe_update_embed_origin(self.interaction, embed=embed)

    async def _removed(self) -> None:
        # Note: Ok to use safe_send_channel() so long as this is not an origin context!
        await safe_send_channel(
            self.interaction,
            "You have been removed from any games your were signed up for.",
            ephemeral=True,
        )

    @tracer.wrap()
    async def _handle_command(self) -> None:
        if not (game_id := await self.services.users.current_game_id()):
            return await self._removed()

        found = await self.services.games.select(game_id)
        assert found

        await self.services.users.leave_game()

        game_data = await self.services.games.to_dict()
        chan_xid = game_data["channel_xid"]
        guild_xid = game_data["guild_xid"]

        if not (channel := await safe_fetch_text_channel(self.bot, guild_xid, chan_xid)):
            return await self._removed()
        if not (message_xid := game_data["message_xid"]):
            return await self._removed()
        if not (message := safe_get_partial_message(channel, guild_xid, message_xid)):
            return await self._removed()

        embed = await self.services.games.to_embed()
        await safe_update_embed(message, embed=embed)
        await self._removed()

    @tracer.wrap()
    async def execute(self, origin: bool = False) -> None:
        if origin:
            return await self._handle_click()
        return await self._handle_command()
