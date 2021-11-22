from unittest.mock import MagicMock

import pytest
from discord_slash.context import MenuContext

from spellbot import SpellBot
from spellbot.cogs.block_cog import BlockCog
from spellbot.database import DatabaseSession
from spellbot.models import Block, User


@pytest.mark.asyncio
class TestCogBlock:
    async def test_block_and_unblock(self, bot: SpellBot, ctx: MenuContext):
        target_author = MagicMock()
        target_author.id = 2
        target_author.display_name = "target-author-display-name"
        ctx.target_author = target_author

        cog = BlockCog(bot)
        await cog.block.func(cog, ctx)

        ctx.send.assert_called_once_with(
            f"<@{target_author.id}> has been blocked.",
            hidden=True,
        )

        users = sorted(list(DatabaseSession.query(User).all()), key=lambda u: u.name)
        assert len(users) == 2
        assert users[0].name == target_author.display_name
        assert users[0].xid == target_author.id
        assert users[1].name == ctx.author.display_name
        assert users[1].xid == ctx.author_id

        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 1
        assert blocks[0].user_xid == ctx.author_id
        assert blocks[0].blocked_user_xid == target_author.id

        DatabaseSession.expire_all()
        await cog.unblock.func(cog, ctx)
        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 0
