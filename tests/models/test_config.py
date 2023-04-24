from __future__ import annotations

from tests.fixtures import Factories


class TestModelConfig:
    def test_config(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        config = factories.config.create(guild_xid=guild.xid, user_xid=user.xid)

        assert config.to_dict() == {
            "guild_xid": config.guild_xid,
            "user_xid": config.user_xid,
            "power_level": config.power_level,
        }
