from __future__ import annotations

import logging
from typing import Any, cast

from ddtrace import tracer

from ..operations import (
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_original_response,
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

        if not await self.services.games.select(game_id):
            return

        await self.services.users.leave_game()

        game_data = await self.services.games.to_dict()
        message_xid = game_data.get("message_xid")

        original_response = await safe_original_response(self.interaction)
        if original_response and message_xid and original_response.id == message_xid:
            embed = await self.services.games.to_embed()
            await safe_update_embed_origin(self.interaction, embed=embed)
            return

        # We couldn't get the original response, so let's fallback to fetching
        # the channel message associated with the game and updating it.
        if not self.interaction.channel or not self.interaction.guild or not message_xid:
            return

        message = safe_get_partial_message(
            cast(Any, self.interaction.channel),
            self.interaction.guild.id,
            message_xid,
        )
        if message is None:
            return

        embed = await self.services.games.to_embed()
        await safe_update_embed(message, embed=embed)
        await safe_send_user(
            self.interaction.user,
            "You have been removed from any games you were signed up for.",
        )

    async def _removed(self) -> None:
        # Note: Ok to use safe_send_channel() so long as this is not an origin context!
        await safe_send_channel(
            self.interaction,
            "You have been removed from any games you were signed up for.",
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
