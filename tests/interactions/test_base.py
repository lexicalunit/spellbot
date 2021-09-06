import pytest

from spellbot.database import DatabaseSession
from spellbot.errors import SpellbotAdminOnly, UserBannedError
from spellbot.interactions import BaseInteraction
from tests.factories.user import UserFactory


class MockInteraction(BaseInteraction):
    async def execute(self, side_effect):
        raise side_effect


@pytest.mark.asyncio
class TestInteractionBase:
    async def test_handle_exception_user_banned(self, bot, ctx):
        with pytest.raises(UserBannedError):
            async with MockInteraction.create(bot, ctx) as interaction:
                await interaction.execute(UserBannedError())

    async def test_handle_exception_admin_only(self, bot, ctx):
        with pytest.raises(SpellbotAdminOnly):
            async with MockInteraction.create(bot, ctx) as interaction:
                await interaction.execute(SpellbotAdminOnly())

    async def test_handle_exception(self, bot, ctx, caplog):
        error = RuntimeError("whatever")
        with pytest.raises(RuntimeError) as exc:
            async with MockInteraction.create(bot, ctx) as interaction:
                await interaction.execute(error)
        assert exc.value is error

        assert (
            "error: rolling back database transaction due to unhandled exception:"
            " RuntimeError: whatever"
        ) in caplog.text

    async def test_create_when_user_banned(self, bot, ctx):
        UserFactory.create(xid=ctx.author.id, banned=True)
        DatabaseSession.commit()

        with pytest.raises(UserBannedError):
            async with MockInteraction.create(bot, ctx):
                ...
