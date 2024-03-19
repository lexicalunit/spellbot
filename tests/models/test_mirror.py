from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.fixtures import Factories


class TestModelMirror:
    def test_mirror(self, factories: Factories) -> None:
        from_guild = factories.guild.create()
        from_channel = factories.channel.create(guild=from_guild)
        to_guild = factories.guild.create()
        to_channel = factories.channel.create(guild=to_guild)
        mirror = factories.mirror.create(
            from_guild_xid=from_guild.xid,
            from_channel_xid=from_channel.xid,
            to_guild_xid=to_guild.xid,
            to_channel_xid=to_channel.xid,
        )

        assert mirror.to_dict() == {
            "created_at": mirror.created_at,
            "updated_at": mirror.updated_at,
            "from_guild_xid": mirror.from_guild_xid,
            "from_channel_xid": mirror.from_channel_xid,
            "to_guild_xid": mirror.to_guild_xid,
            "to_channel_xid": mirror.to_channel_xid,
        }
