from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot.services import VerifiesService

if TYPE_CHECKING:
    from spellbot.models import Guild
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceVerifies:
    async def test_verifies_upsert(self, guild: Guild, factories: Factories) -> None:
        user = factories.user.create()

        verifies = VerifiesService()
        await verifies.upsert(guild.xid, user.xid)
        assert not await verifies.is_verified()

        await verifies.upsert(guild.xid, user.xid, verified=True)
        assert await verifies.is_verified()

        await verifies.upsert(guild.xid, user.xid, verified=False)
        assert not await verifies.is_verified()
