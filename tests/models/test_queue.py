from __future__ import annotations

from tests.fixtures import Factories


class TestModelQueue:
    def test_queue(self, factories: Factories) -> None:
        user = factories.user.create()
        guild = factories.guild.create()
        channel = factories.channel.create(guild_xid=guild.xid)
        game = factories.game.create(guild_xid=guild.xid, channel_xid=channel.xid)
        queue = factories.queue.create(user_xid=user.xid, game_id=game.id)

        assert queue.to_dict() == {
            "user_xid": queue.user_xid,
            "game_id": queue.game_id,
        }
