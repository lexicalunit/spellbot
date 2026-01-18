from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest
import pytest_asyncio

from spellbot.actions import leave_action
from spellbot.cogs import LeaveGameCog
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, Guild, Queue, User
from spellbot.views.lfg_view import GameView
from tests.fixtures import Factories, run_command
from tests.mocks import mock_operations

if TYPE_CHECKING:
    import discord
    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.settings import Settings

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> LeaveGameCog:
    return LeaveGameCog(bot)


@pytest.mark.asyncio
class TestCogLeaveGame:
    async def test_leave(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await run_command(cog.leave_command, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_called_once()
            safe_update_embed_call = leave_action.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{guild.motd}\n\n{channel.motd}"
                ),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: SpellTable"},
                "thumbnail": {"url": settings.THUMB_URL},
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
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await run_command(cog.leave_command, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
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
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_called_once()
            safe_update_embed_call = leave_action.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{guild.motd}\n\n{channel.motd}"
                ),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: SpellTable"},
                "thumbnail": {"url": settings.THUMB_URL},
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
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
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
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_all_when_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = None
            leave_action.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_all_when_get_message_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = None

            await run_command(cog.leave_all, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_when_no_message_xid(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        channel: Channel,
    ) -> None:
        game.message_xid = None
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = channel
            leave_action.safe_get_partial_message.return_value = message

            await run_command(cog.leave_command, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_not_in_game(
        self,
        cog: LeaveGameCog,
        user: User,
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action):
            await run_command(cog.leave_command, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_no_channel(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = None

            await run_command(cog.leave_command, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_no_message(
        self,
        cog: LeaveGameCog,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        channel: Channel,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = channel
            leave_action.safe_get_partial_message.return_value = None

            await run_command(cog.leave_command, interaction)

            leave_action.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_button(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
        bot: SpellBot,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_called_once()
            safe_update_embed_origin_call = leave_action.safe_update_embed_origin.call_args_list[0]
            assert safe_update_embed_origin_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{guild.motd}\n\n{channel.motd}"
                ),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: SpellTable"},
                "thumbnail": {"url": settings.THUMB_URL},
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
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_delete_message.assert_called_once_with(interaction.message)

    async def test_leave_button_with_other_players(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
        bot: SpellBot,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_called_once_with(
                interaction,
                embed=ANY,
            )
            safe_update_embed_origin_call = leave_action.safe_update_embed_origin.call_args_list[0]
            assert safe_update_embed_origin_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{guild.motd}\n\n{channel.motd}"
                ),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: SpellTable"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

            leave_action.safe_delete_message.assert_not_called()

    async def test_leave_button_when_no_game(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        user: User,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_not_called()

    async def test_leave_button_when_message_missing(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = None
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = message
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_delete_message.assert_called_once_with(message)

    async def test_leave_button_when_message_missing_with_other_players(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        """Test leave button when original response doesn't match but other players remain."""
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        DatabaseSession.commit()

        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = None
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = message
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_update_embed.assert_called_once()
            leave_action.safe_delete_message.assert_not_called()

    async def test_leave_button_when_message_missing_and_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = None
            leave_action.safe_fetch_text_channel.return_value = None
            leave_action.safe_get_partial_message.return_value = message
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_button_when_message_missing_and_get_message_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action):
            leave_action.safe_original_response.return_value = None
            leave_action.safe_fetch_text_channel.return_value = interaction.channel
            leave_action.safe_get_partial_message.return_value = None
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_update_embed.assert_not_called()

    async def test_leave_button_when_defer_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.views.lfg_view.safe_defer_interaction",
            return_value=False,
        )
        with mock_operations(leave_action):
            view = GameView(bot)

            await view.leave.callback(interaction)

            leave_action.safe_update_embed_origin.assert_not_called()
            leave_action.safe_delete_message.assert_not_called()
