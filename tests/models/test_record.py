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
        record = factories.record.create(guild=guild, channel=channel, user=user)

        assert record.to_dict() == {
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "guild_xid": record.guild_xid,
            "channel_xid": record.channel_xid,
            "user_xid": record.user_xid,
            "elo": record.elo,
        }
