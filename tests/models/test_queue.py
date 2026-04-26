from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from spellbot.data import QueueData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelQueue:
    def test_queue_to_data(self, factories: Factories) -> None:
        user = factories.user.create()
        guild = factories.guild.create()
        channel = factories.channel.create(guild_xid=guild.xid)
        game = factories.game.create(guild_xid=guild.xid, channel_xid=channel.xid)
        queue = factories.queue.create(user_xid=user.xid, game_id=game.id)

        queue_data = queue.to_data()
        assert isinstance(queue_data, QueueData)
        assert asdict(queue_data) == {
            "user_xid": queue.user_xid,
            "game_id": queue.game_id,
            "og_guild_xid": queue.og_guild_xid,
        }
