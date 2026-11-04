# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import select

from spellbot.actions import playgroup_action
from spellbot.cogs import PlaygroupCog, playgroup_cog
from spellbot.database import DatabaseSession
from spellbot.errors import UserBannedError
from spellbot.models import User
from tests.fixtures import Factories, run_command
from tests.mocks.decoys import ANY

if TYPE_CHECKING:
    import discord
    from decoy import Decoy

    from spellbot import SpellBot
    from tests.fixtures import Stub

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
        stub: Stub,
    ) -> None:
        factories.user.create(xid=interaction.user.id, playgroup_user_id=42)
        lookup_stub = stub(playgroup_action, "find_playgroup_user")

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
        decoy.verify(await lookup_stub(discord_id=ANY), times=0, ignore_extra_args=True)

    async def test_link_success(
        self,
        decoy: Decoy,
        cog: PlaygroupCog,
        interaction: discord.Interaction,
        factories: Factories,
        stub: Stub,
    ) -> None:
        factories.user.create(xid=interaction.user.id)
        find_playgroup_user_fake = stub(playgroup_action, "find_playgroup_user")
        decoy.when(
            await find_playgroup_user_fake(discord_id=ANY),
            ignore_extra_args=True,
        ).then_return((99, "testuser"))

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
        stub: Stub,
    ) -> None:
        find_playgroup_user_fake = stub(playgroup_action, "find_playgroup_user")
        decoy.when(
            await find_playgroup_user_fake(discord_id=ANY),
            ignore_extra_args=True,
        ).then_return((None, None))

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
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        factories.user.create(xid=interaction.user.id, banned=True)
        lookup_stub = stub(playgroup_action, "find_playgroup_user")

        with pytest.raises(UserBannedError):
            await run_command(cog.link, interaction)

        decoy.verify(await lookup_stub(discord_id=ANY), times=0, ignore_extra_args=True)

    async def test_link_stops_when_defer_fails(
        self,
        cog: PlaygroupCog,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        safe_defer_interaction_fake = stub(playgroup_cog, "safe_defer_interaction")
        decoy.when(
            await safe_defer_interaction_fake(interaction=ANY),
            ignore_extra_args=True,
        ).then_return(False)
        create = stub(playgroup_cog.PlaygroupAction, "create")
        await run_command(cog.link, interaction)
        decoy.verify(create(bot=ANY, interaction=ANY), times=0, ignore_extra_args=True)
