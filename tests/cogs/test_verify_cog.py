from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spellbot.cogs import VerifyCog
from spellbot.database import DatabaseSession
from spellbot.models import Verify
from tests.mixins import InteractionContextMixin


@pytest.mark.asyncio
class TestCogVerify(InteractionContextMixin):
    async def test_verify_and_unverify(self):
        target = MagicMock(spec=discord.Member)
        target.id = 1002
        target.display_name = "user"
        cog = VerifyCog(self.bot)

        await cog.verify.func(cog, self.ctx, target)
        self.ctx.send.assert_called_once_with(f"Verified <@{target.id}>.", hidden=True)

        found = DatabaseSession.query(Verify).filter(Verify.user_xid == target.id).one()
        assert found.guild_xid == self.ctx.guild_id
        assert found.user_xid == target.id
        assert found.verified

        self.ctx.send = AsyncMock()  # reset mock
        await cog.unverify.func(cog, self.ctx, target)
        self.ctx.send.assert_called_once_with(f"Unverified <@{target.id}>.", hidden=True)

        found = DatabaseSession.query(Verify).filter(Verify.user_xid == target.id).one()
        assert not found.verified
