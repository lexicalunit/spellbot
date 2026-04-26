from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from spellbot.data import GameData

logger = logging.getLogger(__name__)


class LeaveAction(BaseAction):
    @tracer.wrap()
    async def handle_click(self) -> None:
        assert self.interaction.channel is not None
        assert self.user_data is not None
        channel_xid = self.interaction.channel.id
        if not (game_id := await self.services.users.current_game_id(self.user_data, channel_xid)):
            return

        success = await self.services.games.get(game_id)
        assert success  # given that the game_id was found, above, this should never fail

        left_games: list[GameData] = await self.services.users.leave_game(
            self.user_data,
            channel_xid,
        )
        for game_data in left_games:
            posts = game_data.posts

            player_count = len(game_data.players)
            do_delete_game = player_count == 0

            for post in posts:
                guild_xid = post.guild_xid
                channel_xid = post.channel_xid
                message_xid = post.message_xid

                original_response = await safe_original_response(self.interaction)
                if original_response and message_xid and original_response.id == message_xid:
                    if do_delete_game:
                        assert self.interaction.message is not None
                        await safe_delete_message(self.interaction.message)
                    else:
                        embed = game_data.to_embed(
                            guild=self.guild,
                            emojis=self.bot.emojis_cache,
                            supporters=self.bot.supporters,
                        )
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
                    embed = game_data.to_embed(
                        guild=self.guild,
                        emojis=self.bot.emojis_cache,
                        supporters=self.bot.supporters,
                    )
                    await safe_update_embed(message, embed=embed)

            if do_delete_game:
                await self.services.games.delete_games([game_data.id])

    @tracer.wrap()
    async def handle_command(self) -> None:
        assert self.interaction.channel is not None
        assert self.user_data is not None
        channel_xid = self.interaction.channel.id
        if not (game_id := await self.services.users.current_game_id(self.user_data, channel_xid)):
            await safe_send_channel(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )
            return

        found = await self.services.games.get(game_id)
        assert found

        left_games = await self.services.users.leave_game(self.user_data, channel_xid)
        for game_data in left_games:
            player_count = len(game_data.players)
            do_delete_game = player_count == 0

            for post in game_data.posts:
                chan_xid = post.channel_xid
                guild_xid = post.guild_xid
                message_xid = post.message_xid

                if not (channel := await safe_fetch_text_channel(self.bot, guild_xid, chan_xid)):
                    continue
                if not (message := safe_get_partial_message(channel, guild_xid, message_xid)):
                    continue

                if do_delete_game:
                    await safe_delete_message(message)
                else:
                    embed = game_data.to_embed(
                        guild=self.guild,
                        emojis=self.bot.emojis_cache,
                        supporters=self.bot.supporters,
                    )
                    await safe_update_embed(message, embed=embed)

            if do_delete_game:
                await self.services.games.delete_games([game_data.id])

        await safe_send_channel(
            self.interaction,
            "You were removed from any pending games in this channel.",
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
        game_ids = await self.services.games.dequeue_players([self.interaction.user.id])
        message_xids = await self.services.games.message_xids(game_ids)

        for message_xid in message_xids:
            game_data = await self.services.games.get_by_message_xid(message_xid)
            assert game_data is not None  # This should never happen
            player_count = len(game_data.players)
            do_delete_game = player_count == 0

            for post in game_data.posts:
                guild_xid = post.guild_xid
                channel_xid = post.channel_xid
                channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
                if channel:
                    message = safe_get_partial_message(channel, guild_xid, message_xid)
                    if message:
                        if do_delete_game:
                            await safe_delete_message(message)
                        else:
                            embed = game_data.to_embed(
                                guild=self.guild,
                                emojis=self.bot.emojis_cache,
                                supporters=self.bot.supporters,
                            )
                            await safe_update_embed(
                                message,
                                embed=embed,
                                view=GameView(bot=self.bot),
                            )

            if do_delete_game:
                await self.services.games.delete_games([game_data.id])

        await safe_send_channel(
            self.interaction,
            "You were removed from all pending games.",
            ephemeral=True,
        )
