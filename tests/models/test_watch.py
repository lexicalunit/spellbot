from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from spellbot.data import WatchData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelWatch:
    def test_watch_to_data(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        watch = factories.watch.create(
            note="note",
            user_xid=user.xid,
            guild_xid=guild.xid,
        )

        watch_data = watch.to_data()
        assert isinstance(watch_data, WatchData)
        assert asdict(watch_data) == {
            "guild_xid": watch.guild_xid,
            "user_xid": watch.user_xid,
            "note": watch.note,
        }
