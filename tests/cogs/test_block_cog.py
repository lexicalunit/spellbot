from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from spellbot import SpellBot
from spellbot.cogs import BlockCog
from spellbot.database import DatabaseSession
from spellbot.models import Block, User
from tests.mixins import InteractionMixin


@pytest.fixture
async def cog(bot: SpellBot) -> BlockCog:
    return BlockCog(bot)


@pytest.mark.asyncio
class TestCogBlock(InteractionMixin):
    async def test_block_and_unblock(self, cog: BlockCog):
        target = MagicMock()
        target.id = 2
        target.display_name = "target-author-display-name"

        await self.run(cog.block, target=target)

        self.interaction.response.send_message.assert_called_once_with(
            f"<@{target.id}> has been blocked.",
            ephemeral=True,
        )

        users = sorted(list(DatabaseSession.query(User).all()), key=lambda u: u.name)
        assert len(users) == 2
        assert users[0].name == target.display_name
        assert users[0].xid == target.id
        assert users[1].name == self.interaction.user.display_name
        assert users[1].xid == self.interaction.user.id

        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 1
        assert blocks[0].user_xid == self.interaction.user.id
        assert blocks[0].blocked_user_xid == target.id

        DatabaseSession.expire_all()
        await self.run(cog.unblock, target=target)
        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 0
