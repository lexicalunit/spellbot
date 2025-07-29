from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelGame:
    def test_post_to_dict(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        post = factories.post.create(guild=guild, channel=channel, game=game)

        assert post.to_dict() == {
            "created_at": post.created_at,
            "updated_at": post.updated_at,
            "game_id": post.game_id,
            "guild_xid": post.guild_xid,
            "channel_xid": post.channel_xid,
            "message_xid": post.message_xid,
            "jump_link": post.jump_link,
        }
