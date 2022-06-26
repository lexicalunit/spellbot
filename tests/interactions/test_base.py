from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.errors import AdminOnlyError, UserBannedError, UserUnverifiedError, UserVerifiedError
from spellbot.interactions import BaseInteraction, base_interaction
from spellbot.models import Verify
from tests.mixins import InteractionContextMixin
from tests.mocks import ctx_channel, ctx_guild, ctx_user


class MockInteraction(BaseInteraction):
    async def execute(self, side_effect):
        raise side_effect


@pytest.mark.asyncio
class TestInteractionBase(InteractionContextMixin):
    async def test_handle_exception_user_banned(self):
        with pytest.raises(UserBannedError):
            async with MockInteraction.create(self.bot) as interaction:
                await interaction.execute(UserBannedError())

    async def test_handle_exception_admin_only(self):
        with pytest.raises(AdminOnlyError):
            async with MockInteraction.create(self.bot) as interaction:
                await interaction.execute(AdminOnlyError())

    async def test_handle_exception(self, caplog):
        error = RuntimeError("whatever")
        with pytest.raises(RuntimeError) as exc:
            async with MockInteraction.create(self.bot) as interaction:
                await interaction.execute(error)
        assert exc.value is error

        assert (
            "error: rolling back database session due to unhandled exception:"
            " RuntimeError: whatever"
        ) in caplog.text

    async def test_create_when_user_banned(self):
        self.factories.user.create(xid=self.ctx.author_id, banned=True)

        with pytest.raises(UserBannedError):
            async with MockInteraction.create(self.bot, self.ctx):
                ...

    async def test_create_when_user_unverified_and_channel_verified_only(self):
        guild = ctx_guild(self.ctx)
        ctx_channel(self.ctx, guild=guild, verified_only=True)

        with pytest.raises(UserUnverifiedError):
            async with MockInteraction.create(self.bot, self.ctx):
                ...

    async def test_create_when_user_is_mod_and_channel_verified_only(self, monkeypatch):
        guild = ctx_guild(self.ctx)
        ctx_channel(self.ctx, guild=guild, verified_only=True)
        monkeypatch.setattr(
            base_interaction,
            "user_can_moderate",
            MagicMock(return_value=True),
        )

        async with MockInteraction.create(self.bot, self.ctx):
            ...

        base_interaction.user_can_moderate.assert_called_once()

    async def test_create_when_user_verified_and_channel_unverified_only(self):
        guild = ctx_guild(self.ctx)
        user = ctx_user(self.ctx)
        ctx_channel(self.ctx, guild=guild, unverified_only=True)
        self.factories.verify.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            verified=True,
        )

        with pytest.raises(UserVerifiedError):
            async with MockInteraction.create(self.bot, self.ctx):
                ...

    async def test_create_when_channel_auto_verify(self):
        guild = ctx_guild(self.ctx)
        user = ctx_user(self.ctx)
        ctx_channel(self.ctx, guild=guild, auto_verify=True)

        async with MockInteraction.create(self.bot, self.ctx):
            ...

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == guild.xid
        assert found.user_xid == user.xid
        assert found.verified
