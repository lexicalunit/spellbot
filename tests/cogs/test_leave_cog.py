from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest
import pytest_asyncio

from spellbot.actions import leave_action
from spellbot.cogs import LeaveGameCog
from spellbot.database import DatabaseSession
from spellbot.models import Queue
from spellbot.views.lfg_view import GameView
from tests.mixins import InteractionMixin
from tests.mocks import mock_operations

if TYPE_CHECKING:
    import discord

    from spellbot.client import SpellBot
    from spellbot.models import Game, User

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> LeaveGameCog:
    return LeaveGameCog(bot)


@pytest.mark.asyncio
class TestCogLeaveGame(InteractionMixin):
    async def test_leave(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
    ) -> None:
        p2 = self.factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_called_once()
            safe_update_embed_call = leave_action.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": self.settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{self.guild.motd}\n\n{self.channel.motd}"
                ),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{self.game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_leave_then_delete(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()
            leave_action.safe_delete_message.assert_called_once_with(message)

    async def test_leave_all(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
    ) -> None:
        p2 = self.factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_all)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_called_once()
            safe_update_embed_call = leave_action.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": self.settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{self.guild.motd}\n\n{self.channel.motd}"
                ),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{self.game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_leave_all_then_delete(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_all)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()
            leave_action.safe_delete_message.assert_called_once_with(message)

    async def test_leave_all_when_no_games(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        user: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_all)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_all_when_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = None
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_all)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_all_when_get_message_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = None

            await self.run(cog.leave_all)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_when_no_message_xid(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
    ) -> None:
        self.game.message_xid = None
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.channel
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_not_in_game(self, cog: LeaveGameCog, user: User) -> None:
        with mock_operations(leave_action):
            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_no_channel(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = None

            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_no_message(self, cog: LeaveGameCog, player: User) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.channel
            leave_action.safe_get_partial_message.return_value = None

            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_button(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
    ) -> None:
        p2 = self.factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = message
            view = GameView(self.bot)

            await view.leave.callback(self.interaction)

            leave_action.safe_update_embed_origin.assert_called_once()
            safe_update_embed_origin_call = leave_action.safe_update_embed_origin.call_args_list[0]
            assert safe_update_embed_origin_call.kwargs["embed"].to_dict() == {
                "color": self.settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{self.guild.motd}\n\n{self.channel.motd}"
                ),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{self.game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_leave_button_then_delete(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = message
            view = GameView(self.bot)

            await view.leave.callback(self.interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_delete_message.assert_called_once_with(self.interaction.message)

    async def test_leave_button_when_no_game(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        user: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = message
            view = GameView(self.bot)

            await view.leave.callback(self.interaction)

            leave_action.safe_update_embed_origin.assert_not_called()

    async def test_leave_button_when_message_missing(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = None
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = message
            view = GameView(self.bot)

            await view.leave.callback(self.interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_delete_message.assert_called_once_with(message)

    async def test_leave_button_when_message_missing_and_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = None
            leave_action.safe_fetch_text_channel.return_value = None
            leave_action.safe_get_partial_message.return_value = message
            view = GameView(self.bot)

            await view.leave.callback(self.interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_button_when_message_missing_and_get_message_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = None
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = None
            view = GameView(self.bot)

            await view.leave.callback(self.interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_update_embed.assert_not_called()
