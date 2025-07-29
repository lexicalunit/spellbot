from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


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
