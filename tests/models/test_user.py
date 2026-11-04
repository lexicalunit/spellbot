# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete

from spellbot.data import UserData
from spellbot.database import DatabaseSession
from spellbot.models import GameStatus, Post
from spellbot.services.users import current_game, is_waiting, pending_games

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

        user1_data = UserData.from_model(user1)
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

        user2_data = UserData.from_model(user2)
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
        assert await pending_games(UserData.from_model(user)) == 1

    async def test_pending_games_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)
        assert await pending_games(UserData.from_model(user)) == 0


@pytest.mark.asyncio
class TestModelUserGame:
    async def test_happy_path(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        result = await current_game(user.xid, channel.xid)
        assert result is not None
        assert result.id == game.id

    async def test_no_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        user = factories.user.create()
        assert await current_game(user.xid, channel.xid) is None

    async def test_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)
        assert await current_game(user.xid, channel.xid) is None


@pytest.mark.asyncio
class TestModelUserWaiting:
    async def test_happy_path(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        result = await is_waiting(UserData.from_model(user), channel.xid)
        assert result is not None
        assert result.id == game.id

    async def test_no_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        user = factories.user.create()
        assert await is_waiting(UserData.from_model(user), channel.xid) is None

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
        assert await is_waiting(UserData.from_model(user), channel.xid) is None

    async def test_game_is_deleted(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)
        assert await is_waiting(UserData.from_model(user), channel.xid) is None

    async def test_no_post(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        await DatabaseSession.execute(delete(Post))
        assert await is_waiting(UserData.from_model(user), channel.xid) is None
