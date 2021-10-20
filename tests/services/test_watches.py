import pytest

from spellbot.database import DatabaseSession
from spellbot.services.watches import WatchesService
from tests.factories.guild import GuildFactory
from tests.factories.user import UserFactory
from tests.factories.watch import WatchFactory


@pytest.mark.asyncio
class TestServiceWatches:
    async def test_fetch(self):
        guild1 = GuildFactory.create()
        guild2 = GuildFactory.create()
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        watch1 = WatchFactory.create(guild_xid=guild1.xid, user_xid=user1.xid)
        watch2 = WatchFactory.create(guild_xid=guild1.xid, user_xid=user2.xid)
        WatchFactory.create(guild_xid=guild2.xid, user_xid=user3.xid)
        DatabaseSession.commit()

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
