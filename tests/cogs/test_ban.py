from unittest.mock import MagicMock

import pytest
from discord_slash.context import InteractionContext

from spellbot import SpellBot
from spellbot.cogs.ban import BanCog
from spellbot.database import DatabaseSession
from spellbot.models import User


@pytest.mark.asyncio
class TestCogBan:
    async def test_ban_and_unban(self, bot: SpellBot, ctx: InteractionContext):
        target_user = MagicMock()
        target_user.id = 1002
        cog = BanCog(bot)
        await cog.ban.callback(cog, ctx, str(target_user.id))

        ctx.author.send.assert_called_once_with(
            f"User <@{target_user.id}> has been banned.",
        )
        users = list(DatabaseSession.query(User).all())
        assert len(users) == 1
        assert users[0].xid == target_user.id
        assert users[0].banned

        DatabaseSession.expire_all()
        await cog.unban.callback(cog, ctx, str(target_user.id))
        users = list(DatabaseSession.query(User).all())
        assert len(users) == 1
        assert users[0].xid == target_user.id
        assert not users[0].banned

    async def test_ban_without_target(self, bot: SpellBot, ctx: InteractionContext):
        cog = BanCog(bot)
        await cog.ban.callback(cog, ctx, None)
        ctx.author.send.assert_called_once_with("No target user.")

    async def test_ban_with_invalid_target(self, bot: SpellBot, ctx: InteractionContext):
        cog = BanCog(bot)
        await cog.ban.callback(cog, ctx, "abc")
        ctx.author.send.assert_called_once_with("Invalid user id.")
