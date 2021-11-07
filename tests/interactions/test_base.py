import pytest
from discord_slash.context import InteractionContext

from spellbot import SpellBot
from spellbot.errors import SpellbotAdminOnly, UserBannedError
from spellbot.interactions import BaseInteraction
from tests.fixtures import Factories


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
        with pytest.raises(SpellbotAdminOnly):
            async with MockInteraction.create(bot) as interaction:
                await interaction.execute(SpellbotAdminOnly())

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
