from __future__ import annotations

from functools import partial
from inspect import cleandoc
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from spellbot.cogs import OwnerCog
from spellbot.database import DatabaseSession
from spellbot.models import User

from tests.mixins import ContextMixin

if TYPE_CHECKING:
    from discord.ext import commands
    from pytest_mock import MockerFixture


@pytest.mark.asyncio()
class TestCogOwner(ContextMixin):
    async def run(
        self,
        cog: commands.Cog,
        func: commands.Command[OwnerCog, ..., None],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        callback = partial(func.callback, cog)
        await callback(*args, **kwargs)

    async def test_ban_and_unban(self) -> None:
        target_user = MagicMock()
        target_user.id = 1002
        cog = OwnerCog(self.bot)

        await self.run(cog, cog.ban, self.context, str(target_user.id))

        self.context.author.send.assert_called_once_with(
            f"User <@{target_user.id}> has been banned.",
        )
        users = list(DatabaseSession.query(User).all())
        assert len(users) == 1
        assert users[0].xid == target_user.id
        assert users[0].banned

        DatabaseSession.expire_all()
        await self.run(cog, cog.unban, self.context, str(target_user.id))
        users = list(DatabaseSession.query(User).all())
        assert len(users) == 1
        assert users[0].xid == target_user.id
        assert not users[0].banned

    async def test_ban_without_target(self) -> None:
        cog = OwnerCog(self.bot)
        await self.run(cog, cog.ban, self.context, None)
        self.context.author.send.assert_called_once_with("No target user.")

    async def test_ban_with_invalid_target(self) -> None:
        cog = OwnerCog(self.bot)
        await self.run(cog, cog.ban, self.context, "abc")
        self.context.author.send.assert_called_once_with("Invalid user id.")

    async def test_ban_and_unban_exceptions(
        self,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        target_user = MagicMock()
        target_user.id = 1002
        cog = OwnerCog(self.bot)

        mocker.patch("spellbot.cogs.owner_cog.set_banned", AsyncMock(side_effect=RuntimeError()))

        with pytest.raises(RuntimeError):
            await self.run(cog, cog.ban, self.context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

        caplog.clear()

        with pytest.raises(RuntimeError):
            await self.run(cog, cog.unban, self.context, str(target_user.id))
        assert "rolling back database session due to unhandled exception" in caplog.text

    async def test_stats(self) -> None:
        cog = OwnerCog(self.bot)

        await self.run(cog, cog.stats, self.context)

        self.context.author.send.assert_called_once_with(
            cleandoc(
                """
                    ```
                    status:   online
                    activity: None
                    ready:    False
                    shards:   None
                    guilds:   0
                    users:    0
                    ```
                """,
            ),
        )

    async def test_naughty(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.cogs.owner_cog.bad_users", [1, 2, 3])
        cog = OwnerCog(self.bot)

        await self.run(cog, cog.naughty, self.context)

        self.context.author.send.assert_called_once_with(
            "Naughty users: <@1> (1)\n<@2> (2)\n<@3> (3)",
        )

    async def test_add_mirror(self) -> None:
        cog = OwnerCog(self.bot)
        from_guild = self.factories.guild.create()
        from_channel = self.factories.channel.create(guild=from_guild)
        to_guild = self.factories.guild.create()
        to_channel = self.factories.channel.create(guild=to_guild)

        await self.run(
            cog,
            cog.mirror,
            self.context,
            from_guild_xid=from_guild.xid,
            from_channel_xid=from_channel.xid,
            to_guild_xid=to_guild.xid,
            to_channel_xid=to_channel.xid,
        )

        self.context.author.send.assert_called_once_with(
            f"Mirroring from {from_guild.xid}/{from_channel.xid}"
            f" to {to_guild.xid}/{to_channel.xid}"
        )

    async def test_add_mirror_exception(
        self,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        cog = OwnerCog(self.bot)

        mocker.patch("spellbot.cogs.owner_cog.add_mirror", AsyncMock(side_effect=RuntimeError()))

        with pytest.raises(RuntimeError):
            await self.run(
                cog,
                cog.mirror,
                self.context,
                from_guild_xid=404,
                from_channel_xid=404,
                to_guild_xid=404,
                to_channel_xid=404,
            )

        assert "rolling back database session due to unhandled exception" in caplog.text
