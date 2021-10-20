import pytest

from spellbot.database import DatabaseSession
from spellbot.services.verifies import VerifiesService
from tests.factories.user import UserFactory


@pytest.mark.asyncio
class TestServiceVerifies:
    async def test_verifies_upsert(self, guild):
        user = UserFactory.create()
        DatabaseSession.commit()

        verifies = VerifiesService()
        await verifies.upsert(guild.xid, user.xid)
        assert not await verifies.is_verified()

        await verifies.upsert(guild.xid, user.xid, verified=True)
        assert await verifies.is_verified()

        await verifies.upsert(guild.xid, user.xid, verified=False)
        assert not await verifies.is_verified()
