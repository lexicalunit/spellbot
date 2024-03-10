from __future__ import annotations

from typing import TYPE_CHECKING

from spellbot.models import GameStatus

if TYPE_CHECKING:
    from tests.fixtures import Factories


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
        play1 = factories.play.create(user_xid=player1.xid, game_id=game2.id, points=5)
        play2 = factories.play.create(user_xid=player2.xid, game_id=game2.id, points=1)

        assert user1.points(1) is None
        assert not user1.waiting(channel.xid)
        assert user1.to_dict() == {
            "xid": user1.xid,
            "created_at": user1.created_at,
            "updated_at": user1.updated_at,
            "name": user1.name,
            "banned": user1.banned,
        }
        assert user2.waiting(channel.xid)
        assert user2.to_dict() == {
            "xid": user2.xid,
            "created_at": user2.created_at,
            "updated_at": user2.updated_at,
            "name": user2.name,
            "banned": user2.banned,
        }
        assert player1.points(game2.id) == (play1.points, False)
        assert player2.points(game2.id) == (play2.points, False)
