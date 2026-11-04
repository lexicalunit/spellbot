# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from spellbot.cogs import PlaygroupCog
from spellbot.database import DatabaseSession
from spellbot.errors import UserBannedError
from spellbot.models import User
from tests.fixtures import Factories, run_command

if TYPE_CHECKING:
    import discord
    from decoy import Decoy
    from pytest_mock import MockerFixture

    from spellbot import SpellBot

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> PlaygroupCog:
    return PlaygroupCog(bot)


@pytest.mark.asyncio
class TestCogPlaygroup:
    async def test_link_already_linked(
        self,
        decoy: Decoy,
        cog: PlaygroupCog,
        interaction: discord.Interaction,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        factories.user.create(xid=interaction.user.id, playgroup_user_id=42)
        lookup_stub = mocker.patch(
            "spellbot.actions.playgroup_action.find_playgroup_user",
            AsyncMock(),
        )

        await run_command(cog.link, interaction)

        decoy.verify(await interaction.response.defer(ephemeral=True), times=1)
        decoy.verify(
            await interaction.followup.send(
                "Your Discord account is already linked to Playgroup Live!",
                ephemeral=True,
                wait=True,
            ),
            times=1,
        )
        lookup_stub.assert_not_called()

    async def test_link_success(
        self,
        decoy: Decoy,
        cog: PlaygroupCog,
        interaction: discord.Interaction,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        factories.user.create(xid=interaction.user.id)
        mocker.patch(
            "spellbot.actions.playgroup_action.find_playgroup_user",
            AsyncMock(return_value=(99, "testuser")),
        )

        await run_command(cog.link, interaction)

        DatabaseSession.expire_all()
        user = (
            await DatabaseSession.execute(select(User).where(User.xid == interaction.user.id))
        ).scalar_one()
        assert user.playgroup_user_id == 99

        decoy.verify(
            await interaction.followup.send(
                "Linked! Welcome, **testuser**. "
                "Your Playgroup Live games will now be attributed to your account.",
                ephemeral=True,
                wait=True,
            ),
            times=1,
        )

    async def test_link_no_account_found(
        self,
        decoy: Decoy,
        cog: PlaygroupCog,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.actions.playgroup_action.find_playgroup_user",
            AsyncMock(return_value=(None, None)),
        )

        await run_command(cog.link, interaction)

        decoy.verify(
            await interaction.followup.send(
                "No Playgroup account found for your Discord. "
                "Go to <https://playgroup.gg/profiles> and click **Link Discord**, "
                "then run `/playgroup link` again to confirm.",
                ephemeral=True,
                wait=True,
            ),
            times=1,
        )

    async def test_link_banned_user(
        self,
        cog: PlaygroupCog,
        interaction: discord.Interaction,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        factories.user.create(xid=interaction.user.id, banned=True)
        lookup_stub = mocker.patch(
            "spellbot.actions.playgroup_action.find_playgroup_user",
            AsyncMock(),
        )

        with pytest.raises(UserBannedError):
            await run_command(cog.link, interaction)

        lookup_stub.assert_not_called()

    async def test_link_stops_when_defer_fails(
        self,
        cog: PlaygroupCog,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.cogs.playgroup_cog.safe_defer_interaction",
            AsyncMock(return_value=False),
        )
        create = mocker.patch("spellbot.cogs.playgroup_cog.PlaygroupAction.create")
        await run_command(cog.link, interaction)
        create.assert_not_called()
