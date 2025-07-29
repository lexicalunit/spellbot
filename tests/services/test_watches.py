from __future__ import annotations

import pytest

from spellbot.database import DatabaseSession
from spellbot.services import WatchesService
from tests.factories import GuildFactory, UserFactory, WatchFactory

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceWatches:
    async def test_fetch(self) -> None:
        guild1 = GuildFactory.create()
        guild2 = GuildFactory.create()
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        watch1 = WatchFactory.create(guild_xid=guild1.xid, user_xid=user1.xid)
        watch2 = WatchFactory.create(guild_xid=guild1.xid, user_xid=user2.xid)
        WatchFactory.create(guild_xid=guild2.xid, user_xid=user3.xid)

        DatabaseSession.expire_all()
        watches = WatchesService()
        assert await watches.fetch(guild1.xid) == [
            {
                "guild_xid": guild1.xid,
                "note": watch1.note,
                "user_xid": user1.xid,
            },
            {
                "guild_xid": guild1.xid,
                "note": watch2.note,
                "user_xid": user2.xid,
            },
        ]
