from __future__ import annotations

from tests.fixtures import Factories


class TestModelWatch:
    def test_watch(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        watch = factories.watch.create(
            note="note",
            user_xid=user.xid,
            guild_xid=guild.xid,
        )

        assert watch.to_dict() == {
            "guild_xid": watch.guild_xid,
            "user_xid": watch.user_xid,
            "note": watch.note,
        }
