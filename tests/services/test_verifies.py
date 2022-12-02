from __future__ import annotations

import pytest
from spellbot.models import Guild
from spellbot.services import VerifiesService

from tests.fixtures import Factories


@pytest.mark.asyncio
class TestServiceVerifies:
    async def test_verifies_upsert(self, guild: Guild, factories: Factories):
        user = factories.user.create()

        verifies = VerifiesService()
        await verifies.upsert(guild.xid, user.xid)
        assert not await verifies.is_verified()

        await verifies.upsert(guild.xid, user.xid, verified=True)
        assert await verifies.is_verified()

        await verifies.upsert(guild.xid, user.xid, verified=False)
        assert not await verifies.is_verified()
