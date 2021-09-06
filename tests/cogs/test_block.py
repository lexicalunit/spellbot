from unittest.mock import MagicMock

import pytest

from spellbot.cogs.block import BlockCog
from spellbot.database import DatabaseSession
from spellbot.models.block import Block
from spellbot.models.user import User


@pytest.mark.asyncio
class TestCogBlock:
    async def test_block_and_unblock(self, bot, ctx):
        target_author = MagicMock()
        target_author.id = 2
        target_author.display_name = "target-author-display-name"
        ctx.target_author = target_author
        ctx.target_author_id = target_author.id

        cog = BlockCog(bot)
        await cog._block.func(cog, ctx)

        ctx.send.assert_called_once_with(
            f"<@{target_author.id}> has been blocked.",
            hidden=True,
        )

        users = sorted(list(DatabaseSession.query(User).all()), key=lambda u: u.name)
        assert len(users) == 2
        assert users[0].name == target_author.display_name
        assert users[0].xid == target_author.id
        assert users[1].name == ctx.author.display_name
        assert users[1].xid == ctx.author.id

        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 1
        assert blocks[0].user_xid == ctx.author.id
        assert blocks[0].blocked_user_xid == target_author.id

        DatabaseSession.expire_all()
        await cog._unblock.func(cog, ctx)
        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 0
