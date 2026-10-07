# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from functools import partial
from inspect import cleandoc
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from spellbot.cogs import OwnerCog
from spellbot.database import DatabaseSession
from spellbot.models import Guild, User

if TYPE_CHECKING:
    import discord
    from decoy import Decoy
    from discord.ext import commands
    from pytest_mock import MockerFixture

    from spellbot import SpellBot

pytestmark = pytest.mark.use_db


async def run_owner_command(
    cog: commands.Cog,
    func: commands.Command[OwnerCog, ..., None],
    *args: Any,
    **kwargs: Any,
) -> None:
    callback = partial(func.callback, cog)
    await callback(*args, **kwargs)


@pytest.mark.asyncio
class TestCogOwner:
    async def test_ban_and_unban(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        target_user = MagicMock()
        target_user.id = 1002
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.ban, decoy_context, str(target_user.id))

        decoy.verify(
            await decoy_member.send(
                f"User <@{target_user.id}> has been banned.",
            ),
        )
        user = (
            await DatabaseSession.execute(select(User).where(User.xid == target_user.id))
        ).scalar_one()
        assert user.xid == target_user.id
        assert user.banned

        DatabaseSession.expire_all()
        await run_owner_command(cog, cog.unban, decoy_context, str(target_user.id))
        user = (
            await DatabaseSession.execute(select(User).where(User.xid == target_user.id))
        ).scalar_one()
        assert user.xid == target_user.id
        assert not user.banned

    async def test_ban_without_target(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban, decoy_context, None)
        decoy.verify(await decoy_member.send("No target user."))

    async def test_ban_with_invalid_target(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban, decoy_context, "abc")
        decoy.verify(await decoy_member.send("Invalid user id."))

    async def test_ban_and_unban_exceptions(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        target_user = MagicMock()
        target_user.id = 1002
        cog = OwnerCog(bot)

        mocker.patch("spellbot.cogs.owner_cog.set_banned", AsyncMock(side_effect=RuntimeError()))

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.ban, decoy_context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

        caplog.clear()

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.unban, decoy_context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

    async def test_ban_and_unban_guild(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        target_guild = 1002
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.ban_guild, decoy_context, str(target_guild))

        decoy.verify(
            await decoy_member.send(
                f"Guild {target_guild} has been banned.",
            ),
        )
        guild = (
            await DatabaseSession.execute(select(Guild).where(Guild.xid == target_guild))
        ).scalar_one()
        assert guild.xid == target_guild
        assert guild.banned

        DatabaseSession.expire_all()
        await run_owner_command(cog, cog.unban_guild, decoy_context, str(target_guild))
        guild = (
            await DatabaseSession.execute(select(Guild).where(Guild.xid == target_guild))
        ).scalar_one()
        assert guild.xid == target_guild
        assert not guild.banned

    async def test_ban_guild_without_target(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban_guild, decoy_context, None)
        decoy.verify(await decoy_member.send("No target guild."))

    async def test_ban_guild_with_invalid_target(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban_guild, decoy_context, "abc")
        decoy.verify(await decoy_member.send("Invalid guild id."))

    async def test_ban_and_unban_guild_exceptions(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        target_guild = 1002
        cog = OwnerCog(bot)

        mocker.patch(
            "spellbot.cogs.owner_cog.set_banned_guild",
            AsyncMock(side_effect=RuntimeError()),
        )

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.ban_guild, decoy_context, str(target_guild))
        assert "rolling back database session due to unhandled exception" in caplog.text

        caplog.clear()

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.unban_guild, decoy_context, str(target_guild))
        assert "rolling back database session due to unhandled exception" in caplog.text

    async def test_promote_and_demote(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        target_user = MagicMock()
        target_user.id = 2002
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.promote, decoy_context, str(target_user.id))

        decoy.verify(
            await decoy_member.send(
                f"User <@{target_user.id}> is now an admin.",
            ),
        )
        user = (
            await DatabaseSession.execute(select(User).where(User.xid == target_user.id))
        ).scalar_one()
        assert user.is_admin

        DatabaseSession.expire_all()
        await run_owner_command(cog, cog.demote, decoy_context, str(target_user.id))
        user = (
            await DatabaseSession.execute(select(User).where(User.xid == target_user.id))
        ).scalar_one()
        assert not user.is_admin

    async def test_promote_without_target(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.promote, decoy_context, None)
        decoy.verify(await decoy_member.send("No target user."))

    async def test_promote_with_invalid_target(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.promote, decoy_context, "abc")
        decoy.verify(await decoy_member.send("Invalid user id."))

    async def test_promote_and_demote_exceptions(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        target_user = MagicMock()
        target_user.id = 2002
        cog = OwnerCog(bot)

        mocker.patch("spellbot.cogs.owner_cog.set_admin", AsyncMock(side_effect=RuntimeError()))

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.promote, decoy_context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

        caplog.clear()

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.demote, decoy_context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

    async def test_stats(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
    ) -> None:
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.stats, decoy_context)

        decoy.verify(
            await decoy_member.send(
                cleandoc(
                    """
                        ```
                        status:   online
                        activity: None
                        ready:    False
                        shards:   None
                        guilds:   0
                        users:    0
                        patrons:  set()
                        ```
                    """,
                ),
            ),
        )

    async def test_sync(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.cogs.owner_cog.load_extensions", AsyncMock())
        cog = OwnerCog(bot)
        callback = partial(cog.sync.callback, cog)

        await callback(decoy_context)

        decoy.verify(await decoy_member.send("Commands synced!"))

    async def test_sync_exception(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_context: commands.Context[SpellBot],
        decoy_member: discord.Member,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.cogs.owner_cog.load_extensions",
            AsyncMock(side_effect=RuntimeError("oops")),
        )
        cog = OwnerCog(bot)
        callback = partial(cog.sync.callback, cog)

        with pytest.raises(RuntimeError):
            await callback(decoy_context)

        decoy.verify(await decoy_member.send("Error: oops"))
