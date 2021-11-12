import pytest
from discord_slash.context import InteractionContext

from spellbot import SpellBot
from spellbot.database import DatabaseSession
from spellbot.errors import (
    AdminOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from spellbot.interactions.base_interaction import BaseInteraction
from spellbot.models import Verify
from tests.fixtures import Factories
from tests.mocks import ctx_channel, ctx_guild, ctx_user


class MockInteraction(BaseInteraction):
    async def execute(self, side_effect):
        raise side_effect


@pytest.mark.asyncio
class TestInteractionBase:
    async def test_handle_exception_user_banned(self, bot: SpellBot):
        with pytest.raises(UserBannedError):
            async with MockInteraction.create(bot) as interaction:
                await interaction.execute(UserBannedError())

    async def test_handle_exception_admin_only(self, bot: SpellBot):
        with pytest.raises(AdminOnlyError):
            async with MockInteraction.create(bot) as interaction:
                await interaction.execute(AdminOnlyError())

    async def test_handle_exception(self, bot: SpellBot, caplog):
        error = RuntimeError("whatever")
        with pytest.raises(RuntimeError) as exc:
            async with MockInteraction.create(bot) as interaction:
                await interaction.execute(error)
        assert exc.value is error

        assert (
            "error: rolling back database session due to unhandled exception:"
            " RuntimeError: whatever"
        ) in caplog.text

    async def test_create_when_user_banned(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        factories.user.create(xid=ctx.author_id, banned=True)

        with pytest.raises(UserBannedError):
            async with MockInteraction.create(bot, ctx):
                ...

    async def test_create_when_user_unverified_and_channel_verified_only(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
    ):
        guild = ctx_guild(ctx)
        ctx_channel(ctx, guild=guild, verified_only=True)

        with pytest.raises(UserUnverifiedError):
            async with MockInteraction.create(bot, ctx):
                ...

    async def test_create_when_user_verified_and_channel_unverified_only(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        guild = ctx_guild(ctx)
        user = ctx_user(ctx)
        ctx_channel(ctx, guild=guild, unverified_only=True)
        factories.verify.create(guild_xid=guild.xid, user_xid=user.xid, verified=True)

        with pytest.raises(UserVerifiedError):
            async with MockInteraction.create(bot, ctx):
                ...

    async def test_create_when_channel_auto_verify(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
    ):
        guild = ctx_guild(ctx)
        user = ctx_user(ctx)
        ctx_channel(ctx, guild=guild, auto_verify=True)

        async with MockInteraction.create(bot, ctx):
            ...

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == guild.xid
        assert found.user_xid == user.xid
        assert found.verified
