from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
import pytz
from spellbot.actions import admin_action
from spellbot.cogs import ModCog
from spellbot.database import DatabaseSession
from spellbot.models import GameStatus, Play

from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object, mock_operations

if TYPE_CHECKING:
    from spellbot.client import SpellBot


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> ModCog:
    return ModCog(bot)


@pytest.mark.asyncio()
class TestCogModSetPoints(InteractionMixin):
    async def test_happy_path(self, cog: ModCog) -> None:
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        game = self.factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
        )
        user1 = self.factories.user.create(game=game)
        user2 = self.factories.user.create(game=game)
        player1 = mock_discord_object(user1)
        player2 = mock_discord_object(user2)
        points = 3

        with mock_operations(admin_action, users=[player1, player2]):
            await self.run(cog.mod_set_points, game_id=game.id, player=player1, points=points)
            admin_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                f"Points for <@{player1.id}> for game SB{game.id} set to {points}.",
                ephemeral=True,
            )
            admin_action.safe_update_embed.assert_called_once()

        play1 = DatabaseSession.query(Play).filter_by(game_id=game.id, user_xid=user1.xid).one()
        play2 = DatabaseSession.query(Play).filter_by(game_id=game.id, user_xid=user2.xid).one()
        assert play1.points == points
        assert play2.points is None

    async def test_missing_game(self, cog: ModCog) -> None:
        user = self.factories.user.create()
        player = mock_discord_object(user)

        with mock_operations(admin_action, users=[player]):
            await self.run(cog.mod_set_points, game_id=404, player=player, points=1)
            admin_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "There is no game with that ID.",
                ephemeral=True,
            )

    async def test_missing_player(self, cog: ModCog) -> None:
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        game = self.factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
        )
        user = self.factories.user.create()
        player = mock_discord_object(user)

        with mock_operations(admin_action, users=[player]):
            await self.run(cog.mod_set_points, game_id=game.id, player=player, points=1)
            admin_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                f"User <@{user.xid}> did not play in game SB{game.id}.",
                ephemeral=True,
            )

    async def test_channel_fetch_error(self, cog: ModCog) -> None:
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        game = self.factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
        )
        user1 = self.factories.user.create(game=game)
        user2 = self.factories.user.create(game=game)
        player1 = mock_discord_object(user1)
        player2 = mock_discord_object(user2)
        points = 3

        with mock_operations(admin_action, users=[player1, player2]):
            admin_action.safe_fetch_text_channel.return_value = None
            await self.run(cog.mod_set_points, game_id=game.id, player=player1, points=points)
            admin_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                f"Points for <@{player1.id}> for game SB{game.id} set to {points}.",
                ephemeral=True,
            )
            admin_action.safe_update_embed.assert_not_called()

        play1 = DatabaseSession.query(Play).filter_by(game_id=game.id, user_xid=user1.xid).one()
        play2 = DatabaseSession.query(Play).filter_by(game_id=game.id, user_xid=user2.xid).one()
        assert play1.points == points
        assert play2.points is None

    async def test_message_fetch_error(self, cog: ModCog) -> None:
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        game = self.factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
        )
        user1 = self.factories.user.create(game=game)
        user2 = self.factories.user.create(game=game)
        player1 = mock_discord_object(user1)
        player2 = mock_discord_object(user2)
        points = 3

        with mock_operations(admin_action, users=[player1, player2]):
            admin_action.safe_get_partial_message.return_value = None
            await self.run(cog.mod_set_points, game_id=game.id, player=player1, points=points)
            admin_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                f"Points for <@{player1.id}> for game SB{game.id} set to {points}.",
                ephemeral=True,
            )
            admin_action.safe_update_embed.assert_not_called()

        play1 = DatabaseSession.query(Play).filter_by(game_id=game.id, user_xid=user1.xid).one()
        play2 = DatabaseSession.query(Play).filter_by(game_id=game.id, user_xid=user2.xid).one()
        assert play1.points == points
        assert play2.points is None
