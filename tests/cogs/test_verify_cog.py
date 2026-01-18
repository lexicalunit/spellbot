from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
import pytest_asyncio

from spellbot.cogs import VerifyCog
from spellbot.database import DatabaseSession
from spellbot.models import Guild, User, Verify
from tests.fixtures import run_command
from tests.mocks import mock_discord_object

if TYPE_CHECKING:
    from collections.abc import Callable

    import discord

    from spellbot import SpellBot

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> VerifyCog:
    return VerifyCog(bot)


@pytest.mark.asyncio
class TestCogVerify:
    @pytest_asyncio.fixture
    async def target(self, add_user: Callable[..., User]) -> discord.Member:
        return cast("discord.Member", mock_discord_object(add_user()))

    async def test_verify_and_unverify(
        self,
        cog: VerifyCog,
        target: discord.Member,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        await run_command(cog.verify, interaction, target=target)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Verified <@{target.id}>.",
            ephemeral=True,
        )
        found = DatabaseSession.query(Verify).filter(Verify.user_xid == target.id).one()
        assert found.guild_xid == guild.xid
        assert found.user_xid == target.id
        assert found.verified

        interaction.response.send_message.reset_mock()  # type: ignore
        await run_command(cog.unverify, interaction, target=target)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Unverified <@{target.id}>.",
            ephemeral=True,
        )
        found = DatabaseSession.query(Verify).filter(Verify.user_xid == target.id).one()
        assert not found.verified
