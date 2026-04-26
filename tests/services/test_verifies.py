from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from spellbot.data import VerifyData
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

        # First upsert with no verified parameter - should return unverified
        verify_data = await verifies.upsert(guild.xid, user.xid)
        assert isinstance(verify_data, VerifyData)
        assert asdict(verify_data) == {
            "guild_xid": guild.xid,
            "user_xid": user.xid,
            "verified": False,
        }

        # Upsert with verified=True
        verify_data = await verifies.upsert(guild.xid, user.xid, verified=True)
        assert verify_data.verified is True

        # Upsert with verified=False
        verify_data = await verifies.upsert(guild.xid, user.xid, verified=False)
        assert verify_data.verified is False
