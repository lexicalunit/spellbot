from __future__ import annotations

import logging

from ddtrace import tracer

from spellbot.operations import (
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_original_response,
    safe_send_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.views import PendingGameView

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class LeaveAction(BaseAction):
    @tracer.wrap()
    async def _handle_click(self) -> None:
        assert self.interaction.channel is not None
        channel_xid = self.interaction.channel.id
        if not (game_id := await self.services.users.current_game_id(channel_xid)):
            return

        success = await self.services.games.select(game_id)
        assert success  # given that the game_id was found, above, this should never fail

        await self.services.users.leave_game(channel_xid)

        game_data = await self.services.games.to_dict()
        posts = game_data.get("posts")
        for post in posts:
            guild_xid = post["guild_xid"]
            channel_xid = post["channel_xid"]
            message_xid = post["message_xid"]

            original_response = await safe_original_response(self.interaction)
            if original_response and message_xid and original_response.id == message_xid:
                embed = await self.services.games.to_embed()
                await safe_update_embed_origin(self.interaction, embed=embed)
                continue

            channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
            if channel is None:
                continue

            message = safe_get_partial_message(channel, guild_xid, message_xid)
            if message is None:
                continue

            embed = await self.services.games.to_embed()
            await safe_update_embed(message, embed=embed)

    @tracer.wrap()
    async def _handle_command(self) -> None:
        assert self.interaction.channel is not None
        channel_xid = self.interaction.channel.id
        if not (game_id := await self.services.users.current_game_id(channel_xid)):
            await safe_send_channel(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )
            return

        found = await self.services.games.select(game_id)
        assert found

        await self.services.users.leave_game(channel_xid)

        game_data = await self.services.games.to_dict()
        for post in game_data.get("posts", []):
            chan_xid = post["channel_xid"]
            guild_xid = post["guild_xid"]
            message_xid = post["message_xid"]

            if not (channel := await safe_fetch_text_channel(self.bot, guild_xid, chan_xid)):
                continue
            if not (message := safe_get_partial_message(channel, guild_xid, message_xid)):
                continue

            embed = await self.services.games.to_embed()
            await safe_update_embed(message, embed=embed)

        await safe_send_channel(
            self.interaction,
            "You were removed from any pending games in this channel.",
            ephemeral=True,
        )

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
            assert data is not None  # This should never happen

            for post in data.get("posts", []):
                guild_xid = post["guild_xid"]
                channel_xid = post["channel_xid"]
                channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
                if channel:
                    message = safe_get_partial_message(channel, guild_xid, message_xid)
                    if message:
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
