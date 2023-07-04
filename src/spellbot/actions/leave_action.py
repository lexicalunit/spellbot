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
from ..views import PendingGameView
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class LeaveAction(BaseAction):
    @tracer.wrap()
    async def _handle_click(self) -> None:
        assert self.interaction.channel is not None
        channel_xid = self.interaction.channel.id
        if not (game_id := await self.services.users.current_game_id(channel_xid)):
            return

        if not await self.services.games.select(game_id):
            return

        await self.services.users.leave_game(channel_xid)

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
            "You were removed from any pending games in this channel.",
        )

    async def _removed(self, channel_xid: int) -> None:
        # Note: Ok to use safe_send_channel() so long as this is not an origin context!
        await safe_send_channel(
            self.interaction,
            "You were removed from any pending games in this channel.",
            ephemeral=True,
        )

    @tracer.wrap()
    async def _handle_command(self) -> None:
        assert self.interaction.channel is not None
        channel_xid = self.interaction.channel.id
        if not (game_id := await self.services.users.current_game_id(channel_xid)):
            return await self._removed(channel_xid)

        found = await self.services.games.select(game_id)
        assert found

        await self.services.users.leave_game(channel_xid)

        game_data = await self.services.games.to_dict()
        chan_xid = game_data["channel_xid"]
        guild_xid = game_data["guild_xid"]

        if not (channel := await safe_fetch_text_channel(self.bot, guild_xid, chan_xid)):
            return await self._removed(channel_xid)
        if not (message_xid := game_data["message_xid"]):
            return await self._removed(channel_xid)
        if not (message := safe_get_partial_message(channel, guild_xid, message_xid)):
            return await self._removed(channel_xid)

        embed = await self.services.games.to_embed()
        await safe_update_embed(message, embed=embed)
        await self._removed(channel_xid)

    @tracer.wrap()
    async def execute(self, origin: bool = False) -> None:
        """Leave a game in the channel or the game clicked on by the user."""
        if origin:
            return await self._handle_click()
        return await self._handle_command()

    @tracer.wrap()
    async def execute_all(self) -> None:
        """Leave ALL games in ALL channels for this user."""
        game_ids = await self.services.games.dequeue_players([self.interaction.user.id])
        message_xids = await self.services.games.message_xids(game_ids)
        for message_xid in message_xids:
            data = await self.services.games.select_by_message_xid(message_xid)
            if not data:
                continue

            channel_xid = data["channel_xid"]
            guild_xid = data["guild_xid"]
            if channel := await safe_fetch_text_channel(self.bot, guild_xid, channel_xid):
                if message := safe_get_partial_message(
                    channel,
                    guild_xid,
                    message_xid,
                ):
                    embed = await self.services.games.to_embed()
                    await safe_update_embed(
                        message,
                        embed=embed,
                        view=PendingGameView(bot=self.bot),
                    )
        await safe_send_channel(
            self.interaction,
            "You were removed from all pending games.",
            ephemeral=True,
        )
