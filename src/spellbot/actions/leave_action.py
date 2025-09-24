from __future__ import annotations

import logging

from ddtrace.trace import tracer

from spellbot.operations import (
    safe_delete_message,
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_original_response,
    safe_send_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.views import GameView

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

        player_count = len(await self.services.games.player_xids())
        do_delete_game = player_count == 0

        for post in posts:
            guild_xid = post["guild_xid"]
            channel_xid = post["channel_xid"]
            message_xid = post["message_xid"]

            original_response = await safe_original_response(self.interaction)
            if original_response and message_xid and original_response.id == message_xid:
                if do_delete_game:
                    assert self.interaction.message is not None
                    await safe_delete_message(self.interaction.message)
                else:
                    embed = await self.services.games.to_embed(guild=self.guild)
                    await safe_update_embed_origin(self.interaction, embed=embed)
                continue

            channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
            if channel is None:
                continue

            message = safe_get_partial_message(channel, guild_xid, message_xid)
            if message is None:
                continue

            if do_delete_game:
                await safe_delete_message(message)
            else:
                embed = await self.services.games.to_embed(guild=self.guild)
                await safe_update_embed(message, embed=embed)

        if do_delete_game:
            await self.services.games.delete_games([game_data["id"]])

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
        player_count = len(await self.services.games.player_xids())
        do_delete_game = player_count == 0
        for post in game_data.get("posts", []):
            chan_xid = post["channel_xid"]
            guild_xid = post["guild_xid"]
            message_xid = post["message_xid"]

            if not (channel := await safe_fetch_text_channel(self.bot, guild_xid, chan_xid)):
                continue
            if not (message := safe_get_partial_message(channel, guild_xid, message_xid)):
                continue

            if do_delete_game:
                await safe_delete_message(message)
            else:
                embed = await self.services.games.to_embed(guild=self.guild)
                await safe_update_embed(message, embed=embed)

        if do_delete_game:
            await self.services.games.delete_games([game_data["id"]])

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
            player_count = len(await self.services.games.player_xids())
            do_delete_game = player_count == 0

            for post in data.get("posts", []):
                guild_xid = post["guild_xid"]
                channel_xid = post["channel_xid"]
                channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
                if channel:
                    message = safe_get_partial_message(channel, guild_xid, message_xid)
                    if message:
                        if do_delete_game:
                            await safe_delete_message(message)
                        else:
                            embed = await self.services.games.to_embed(guild=self.guild)
                            await safe_update_embed(
                                message,
                                embed=embed,
                                view=GameView(bot=self.bot),
                            )

            if do_delete_game:
                await self.services.games.delete_games([data["id"]])

        await safe_send_channel(
            self.interaction,
            "You were removed from all pending games.",
            ephemeral=True,
        )
