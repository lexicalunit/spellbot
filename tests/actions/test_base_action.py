# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from spellbot.actions import BlockAction, TasksAction
from spellbot.database import DatabaseSession
from spellbot.errors import GuildBannedError
from spellbot.models import Channel, Guild, User

if TYPE_CHECKING:
    import discord
    from decoy import Decoy

    from spellbot import SpellBot
    from tests.fixtures import Factories, Stub

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestBaseActionCreate:
    async def test_upserts_the_request_objects(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
    ) -> None:
        async with BlockAction.create(bot, interaction) as action:
            assert action.guild_data is not None
            assert action.guild_data.xid == interaction.guild_id
            assert action.channel_data.xid == interaction.channel_id
            assert action.user_data is not None
            assert action.user_data.xid == interaction.user.id

    async def test_banned_guild(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        factories: Factories,
    ) -> None:
        factories.guild.create(xid=interaction.guild_id, banned=True)
        # Entering is enough: a banned guild's action never gets to run.
        with pytest.raises(GuildBannedError):
            await BlockAction.create(bot, interaction).__aenter__()

    async def test_without_a_guild(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        decoy: Decoy,
    ) -> None:
        decoy.when(interaction.guild).then_return(None)
        async with BlockAction.create(bot, interaction) as action:
            assert action.guild_data is None
            assert action.user_data is not None
            assert action.user_data.xid == interaction.user.id
        assert (await DatabaseSession.execute(select(Guild))).scalars().all() == []

    async def test_without_a_channel(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(interaction, "channel", None)
        async with BlockAction.create(bot, interaction):
            pass
        assert (await DatabaseSession.execute(select(Channel))).scalars().all() == []
        assert (await DatabaseSession.execute(select(User))).scalars().all() != []

    async def test_unhandled_error_rolls_back(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        rollback = stub(DatabaseSession, "rollback")
        with pytest.raises(RuntimeError, match="boom"):
            async with BlockAction.create(bot, interaction):
                raise RuntimeError("boom")
        decoy.verify(await rollback(), times=1, ignore_extra_args=True)


@pytest.mark.asyncio
class TestTasksActionCreate:
    async def test_unhandled_error_rolls_back(
        self,
        bot: SpellBot,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        rollback = stub(DatabaseSession, "rollback")
        with pytest.raises(RuntimeError, match="boom"):
            async with TasksAction.create(bot):
                raise RuntimeError("boom")
        decoy.verify(await rollback(), times=1, ignore_extra_args=True)
