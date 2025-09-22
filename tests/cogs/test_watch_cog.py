from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from spellbot.cogs import WatchCog
from spellbot.database import DatabaseSession
from spellbot.models import Guild, User, Watch
from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object

if TYPE_CHECKING:
    from collections.abc import Callable

    import discord

    from spellbot import SpellBot

pytestmark = pytest.mark.use_db


@pytest.fixture
def cog(bot: SpellBot) -> WatchCog:
    return WatchCog(bot)


@pytest.mark.asyncio
class TestCogWatch(InteractionMixin):
    async def test_watch_and_unwatch(self, cog: WatchCog, add_user: Callable[..., User]) -> None:
        target_user = add_user()
        target_member = cast("discord.Member", mock_discord_object(target_user))

        await self.run(cog.watch, target=target_member, note="note")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Watching <@{target_member.id}>.",
            ephemeral=True,
        )

        watch = DatabaseSession.query(Watch).one()
        assert watch.to_dict() == {
            "guild_xid": self.guild.xid,
            "user_xid": target_member.id,
            "note": "note",
        }

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.unwatch, target=target_member)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"No longer watching <@{target_member.id}>.",
            ephemeral=True,
        )

        watch = DatabaseSession.query(Watch).one_or_none()
        assert not watch

    async def test_watch_and_unwatch_by_id(
        self,
        cog: WatchCog,
        add_user: Callable[..., User],
    ) -> None:
        target_user = add_user()
        target_member = cast("discord.Member", mock_discord_object(target_user))

        await self.run(cog.watch, id=target_member.id, note="note")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Watching <@{target_member.id}>.",
            ephemeral=True,
        )

        watch = DatabaseSession.query(Watch).one()
        assert watch.to_dict() == {
            "guild_xid": self.guild.xid,
            "user_xid": target_member.id,
            "note": "note",
        }

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.unwatch, id=target_member.id)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"No longer watching <@{target_member.id}>.",
            ephemeral=True,
        )

        watch = DatabaseSession.query(Watch).one_or_none()
        assert not watch

    async def test_watch_with_no_target(self, cog: WatchCog) -> None:
        await self.run(cog.watch, note="note")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "You must provide either a target User or their ID.",
            ephemeral=True,
        )

    async def test_watch_with_invalid_id(self, cog: WatchCog) -> None:
        await self.run(cog.watch, id="wah", note="note")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "You must provide a valid integer for an ID.",
            ephemeral=True,
        )

    async def test_unwatch_with_no_target(self, cog: WatchCog) -> None:
        await self.run(cog.unwatch)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "You must provide either a target User or their ID.",
            ephemeral=True,
        )

    async def test_unwatch_with_invalid_id(self, cog: WatchCog) -> None:
        await self.run(cog.unwatch, id="wah")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "You must provide a valid integer for an ID.",
            ephemeral=True,
        )

    async def test_watched_single_page(
        self,
        cog: WatchCog,
        add_guild: Callable[..., Guild],
        add_user: Callable[..., User],
    ) -> None:
        guild2 = add_guild()
        user1 = add_user(xid=101)
        user2 = add_user(xid=102)
        user3 = add_user(xid=103)
        watch1 = self.factories.watch.create(guild_xid=self.guild.xid, user_xid=user1.xid)
        watch2 = self.factories.watch.create(guild_xid=self.guild.xid, user_xid=user2.xid)
        self.factories.watch.create(guild_xid=guild2.xid, user_xid=user3.xid)

        await self.run(cog.watched)
        assert self.last_send_message("embed") == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": f"• <@{user1.xid}> — {watch1.note}\n• <@{user2.xid}> — {watch2.note}\n",
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "flags": 0,
        }

    async def test_watched_multiple_pages(
        self,
        cog: WatchCog,
        add_user: Callable[..., User],
    ) -> None:
        users = [
            add_user(xid=101),
            add_user(xid=102),
            add_user(xid=103),
            add_user(xid=104),
            add_user(xid=105),
        ]
        watches = [
            self.factories.watch.create(
                guild_xid=self.guild.xid,
                user_xid=users[0].xid,
                note="ab " * 333,
            ),
            self.factories.watch.create(
                guild_xid=self.guild.xid,
                user_xid=users[1].xid,
                note="cd " * 333,
            ),
            self.factories.watch.create(
                guild_xid=self.guild.xid,
                user_xid=users[2].xid,
                note="ef " * 333,
            ),
            self.factories.watch.create(
                guild_xid=self.guild.xid,
                user_xid=users[3].xid,
                note="gh " * 333,
            ),
            self.factories.watch.create(
                guild_xid=self.guild.xid,
                user_xid=users[4].xid,
                note="ij " * 333,
            ),
        ]

        await self.run(cog.watched, page=1)
        assert self.last_send_message("embed") == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                f"• <@{users[0].xid}> — {watches[0].note}\n"
                f"• <@{users[1].xid}> — {watches[1].note}\n"
                f"• <@{users[2].xid}> — {watches[2].note}\n"
                f"• <@{users[3].xid}> — {watches[3].note}\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "footer": {"text": "page 1 of 2"},
            "flags": 0,
        }

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.watched, page=2)
        assert self.last_send_message("embed") == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (f"• <@{users[4].xid}> — {watches[4].note}\n"),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "footer": {"text": "page 2 of 2"},
            "flags": 0,
        }
