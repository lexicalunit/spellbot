from __future__ import annotations

import discord
import pytest
import pytest_asyncio
from spellbot.actions import leave_action
from spellbot.client import SpellBot
from spellbot.cogs import LeaveGameCog
from spellbot.database import DatabaseSession
from spellbot.models import User

from tests.mixins import InteractionMixin
from tests.mocks import mock_operations


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> LeaveGameCog:
    return LeaveGameCog(bot)


@pytest.mark.asyncio
class TestCogLeaveGame(InteractionMixin):
    async def test_leave(self, cog: LeaveGameCog, message: discord.Message, player: User) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.interaction.channel
            leave_action.safe_get_partial_message.return_value = message

            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You have been removed from any games your were signed up for.",
                ephemeral=True,
            )
            leave_action.safe_update_embed.assert_called_once()
            safe_update_embed_call = leave_action.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": self.settings.EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{self.guild.motd}\n\n{self.channel.motd}"
                ),
                "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
                "footer": {"text": f"SpellBot Game ID: #SB{self.game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 4 more players to join...**",
                "type": "rich",
            }

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
                "You have been removed from any games your were signed up for.",
                ephemeral=True,
            )

    async def test_leave_when_not_in_game(self, cog: LeaveGameCog, user: User) -> None:
        with mock_operations(leave_action):
            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You have been removed from any games your were signed up for.",
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
                "You have been removed from any games your were signed up for.",
                ephemeral=True,
            )

    async def test_leave_when_no_message(self, cog: LeaveGameCog, player: User) -> None:
        with mock_operations(leave_action):
            leave_action.safe_fetch_text_channel.return_value = self.channel
            leave_action.safe_get_partial_message.return_value = None

            await self.run(cog.leave_command)

            leave_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "You have been removed from any games your were signed up for.",
                ephemeral=True,
            )
