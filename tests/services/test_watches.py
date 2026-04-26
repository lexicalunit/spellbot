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
        watches_service = WatchesService()
        result = await watches_service.fetch(guild1.xid)
        assert len(result) == 2
        assert result[0].guild_xid == guild1.xid
        assert result[0].user_xid == user1.xid
        assert result[0].note == watch1.note
        assert result[1].guild_xid == guild1.xid
        assert result[1].user_xid == user2.xid
        assert result[1].note == watch2.note
