from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelPlay:
    def test_play(self, factories: Factories) -> None:
        user = factories.user.create()
        guild = factories.guild.create()
        channel = factories.channel.create(guild_xid=guild.xid)
        game = factories.game.create(guild_xid=guild.xid, channel_xid=channel.xid)
        play = factories.play.create(user_xid=user.xid, game_id=game.id)

        assert play.to_dict() == {
            "user_xid": play.user_xid,
            "game_id": play.game_id,
            "created_at": play.created_at,
            "updated_at": play.updated_at,
            "og_guild_xid": play.og_guild_xid,
            "pin": play.pin,
            "verified_at": play.verified_at,
        }
