from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import delete

from spellbot.data import UserData
from spellbot.database import DatabaseSession
from spellbot.models import GameStatus, Post

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestModelUser:
    async def test_user(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game1 = factories.game.create(guild=guild, channel=channel)
        user1 = factories.user.create()
        user2 = factories.user.create(game=game1)
        game2 = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            guild=guild,
            channel=channel,
        )
        player1 = factories.user.create(game=game2)
        player2 = factories.user.create(game=game2)
        factories.play.create(user_xid=player1.xid, game_id=game2.id)
        factories.play.create(user_xid=player2.xid, game_id=game2.id)

        user1_data = user1.to_data()
        assert isinstance(user1_data, UserData)
        assert asdict(user1_data) == {
            "xid": user1.xid,
            "created_at": user1.created_at,
            "updated_at": user1.updated_at,
            "name": user1.name,
            "banned": user1.banned,
            "is_admin": user1.is_admin,
            "playgroup_user_id": None,
            "locale": "en",
        }

        user2_data = user2.to_data()
        assert isinstance(user2_data, UserData)
        assert asdict(user2_data) == {
            "xid": user2.xid,
            "created_at": user2.created_at,
            "updated_at": user2.updated_at,
            "name": user2.name,
            "banned": user2.banned,
            "is_admin": user2.is_admin,
            "playgroup_user_id": None,
            "locale": "en",
        }

    async def test_pending_games(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        assert await user.pending_games() == 1

    async def test_pending_games_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)
        assert await user.pending_games() == 0


@pytest.mark.asyncio
class TestModelUserGame:
    async def test_happy_path(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        result = await user.game(channel.xid)
        assert result is not None
        assert result.id == game.id

    async def test_no_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        user = factories.user.create()
        assert await user.game(channel.xid) is None

    async def test_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)
        assert await user.game(channel.xid) is None


@pytest.mark.asyncio
class TestModelUserWaiting:
    async def test_happy_path(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        result = await user.waiting(channel.xid)
        assert result is not None
        assert result.id == game.id

    async def test_no_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        user = factories.user.create()
        assert await user.waiting(channel.xid) is None

    async def test_no_pending_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            status=GameStatus.STARTED.value,
        )
        user = factories.user.create(game=game)
        factories.queue.create(user_xid=user.xid, game_id=game.id)
        assert await user.waiting(channel.xid) is None

    async def test_game_is_deleted(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)
        assert await user.waiting(channel.xid) is None

    async def test_game_is_deleted_defensive(self, factories: Factories) -> None:
        """Test the defensive deleted_at check when game() bypasses SQL filter."""
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        mock_game = MagicMock()
        mock_game.status = GameStatus.PENDING.value
        mock_game.deleted_at = datetime(2021, 11, 1, tzinfo=UTC)
        user.game = AsyncMock(return_value=mock_game)
        assert await user.waiting(channel.xid) is None

    async def test_no_post(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        await DatabaseSession.execute(delete(Post))
        assert await user.waiting(channel.xid) is None
