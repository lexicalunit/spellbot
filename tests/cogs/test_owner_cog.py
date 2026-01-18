from __future__ import annotations

from functools import partial
from inspect import cleandoc
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from spellbot.cogs import OwnerCog
from spellbot.database import DatabaseSession
from spellbot.models import Guild, User

if TYPE_CHECKING:
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
        context: commands.Context[SpellBot],
    ) -> None:
        target_user = MagicMock()
        target_user.id = 1002
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.ban, context, str(target_user.id))

        context.author.send.assert_called_once_with(  # type: ignore
            f"User <@{target_user.id}> has been banned.",
        )
        users = list(DatabaseSession.query(User).all())
        assert len(users) == 1
        assert users[0].xid == target_user.id
        assert users[0].banned

        DatabaseSession.expire_all()
        await run_owner_command(cog, cog.unban, context, str(target_user.id))
        users = list(DatabaseSession.query(User).all())
        assert len(users) == 1
        assert users[0].xid == target_user.id
        assert not users[0].banned

    async def test_ban_without_target(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban, context, None)
        context.author.send.assert_called_once_with("No target user.")  # type: ignore

    async def test_ban_with_invalid_target(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban, context, "abc")
        context.author.send.assert_called_once_with("Invalid user id.")  # type: ignore

    async def test_ban_and_unban_exceptions(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        target_user = MagicMock()
        target_user.id = 1002
        cog = OwnerCog(bot)

        mocker.patch("spellbot.cogs.owner_cog.set_banned", AsyncMock(side_effect=RuntimeError()))

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.ban, context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

        caplog.clear()

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.unban, context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

    async def test_ban_and_unban_guild(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
    ) -> None:
        target_guild = 1002
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.ban_guild, context, str(target_guild))

        context.author.send.assert_called_once_with(  # type: ignore
            f"Guild {target_guild} has been banned.",
        )
        guilds = list(DatabaseSession.query(Guild).all())
        assert len(guilds) == 1
        assert guilds[0].xid == target_guild
        assert guilds[0].banned

        DatabaseSession.expire_all()
        await run_owner_command(cog, cog.unban_guild, context, str(target_guild))
        guilds = list(DatabaseSession.query(Guild).all())
        assert len(guilds) == 1
        assert guilds[0].xid == target_guild
        assert not guilds[0].banned

    async def test_ban_guild_without_target(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban_guild, context, None)
        context.author.send.assert_called_once_with("No target guild.")  # type: ignore

    async def test_ban_guild_with_invalid_target(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
    ) -> None:
        cog = OwnerCog(bot)
        await run_owner_command(cog, cog.ban_guild, context, "abc")
        context.author.send.assert_called_once_with("Invalid guild id.")  # type: ignore

    async def test_ban_and_unban_guild_exceptions(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
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
            await run_owner_command(cog, cog.ban_guild, context, str(target_guild))
        assert "rolling back database session due to unhandled exception" in caplog.text

        caplog.clear()

        with pytest.raises(RuntimeError):
            await run_owner_command(cog, cog.unban_guild, context, str(target_guild))
        assert "rolling back database session due to unhandled exception" in caplog.text

    async def test_stats(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
    ) -> None:
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.stats, context)

        context.author.send.assert_called_once_with(  # type: ignore
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
        )

    async def test_is_bad(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.cogs.owner_cog.is_bad_user", side_effect=[True, False])
        cog = OwnerCog(bot)

        await run_owner_command(cog, cog.is_bad, context, "1")
        context.author.send.assert_called_once_with("Yes")  # type: ignore

        context.author.send.reset_mock()  # type: ignore

        await run_owner_command(cog, cog.is_bad, context, "2")
        context.author.send.assert_called_once_with("No")  # type: ignore

    async def test_sync(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.cogs.owner_cog.load_extensions", AsyncMock())
        cog = OwnerCog(bot)
        callback = partial(cog.sync.callback, cog)

        await callback(context)

        context.author.send.assert_called_once_with("Commands synced!")  # type: ignore

    async def test_sync_exception(
        self,
        bot: SpellBot,
        context: commands.Context[SpellBot],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.cogs.owner_cog.load_extensions",
            AsyncMock(side_effect=RuntimeError("oops")),
        )
        cog = OwnerCog(bot)
        callback = partial(cog.sync.callback, cog)

        with pytest.raises(RuntimeError):
            await callback(context)

        context.author.send.assert_called_once_with("Error: oops")  # type: ignore
