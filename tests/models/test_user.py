from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot.database import DatabaseSession
from spellbot.models import GameStatus, Post

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelUser:
    def test_user(self, factories: Factories) -> None:
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

        assert user1.to_dict() == {
            "xid": user1.xid,
            "created_at": user1.created_at,
            "updated_at": user1.updated_at,
            "name": user1.name,
            "banned": user1.banned,
        }
        assert user2.to_dict() == {
            "xid": user2.xid,
            "created_at": user2.created_at,
            "updated_at": user2.updated_at,
            "name": user2.name,
            "banned": user2.banned,
        }

    def test_pending_games(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        assert user.pending_games() == 1


class TestModelUserWaiting:
    def test_happy_path(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        assert user.waiting(channel.xid)

    def test_no_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        user = factories.user.create()
        assert not user.waiting(channel.xid)

    def test_no_pending_game(self, factories: Factories) -> None:
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
        assert not user.waiting(channel.xid)

    def test_game_is_deleted(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)
        assert not user.waiting(channel.xid)

    def test_no_post(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        DatabaseSession.query(Post).delete(synchronize_session=False)
        assert not user.waiting(channel.xid)
