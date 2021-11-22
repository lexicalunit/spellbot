from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from pygicord import Config

from spellbot.cogs.watch_cog import WatchCog
from spellbot.database import DatabaseSession
from spellbot.interactions import watch_interaction
from spellbot.models import Watch
from tests.mixins import InteractionContextMixin


@pytest.mark.asyncio
class TestCogWatch(InteractionContextMixin):
    async def test_watch_and_unwatch(self):
        assert self.ctx.guild
        target = MagicMock(spec=discord.Member)
        target.id = 1002
        target.display_name = "user"
        cog = WatchCog(self.bot)

        await cog.watch.func(cog, self.ctx, target, "note")
        self.ctx.send.assert_called_once_with(f"Watching <@{target.id}>.", hidden=True)

        watch = DatabaseSession.query(Watch).one()
        assert watch.to_dict() == {
            "guild_xid": self.ctx.guild_id,
            "user_xid": target.id,
            "note": "note",
        }

        self.ctx.send = AsyncMock()  # reset mock
        await cog.unwatch.func(cog, self.ctx, target)
        self.ctx.send.assert_called_once_with(
            f"No longer watching <@{target.id}>.",
            hidden=True,
        )

        watch = DatabaseSession.query(Watch).one_or_none()
        assert not watch

    async def test_watched_single_page(self):
        guild1 = self.factories.guild.create()
        guild2 = self.factories.guild.create()
        user1 = self.factories.user.create(xid=101)
        user2 = self.factories.user.create(xid=102)
        user3 = self.factories.user.create(xid=103)
        watch1 = self.factories.watch.create(guild_xid=guild1.xid, user_xid=user1.xid)
        watch2 = self.factories.watch.create(guild_xid=guild1.xid, user_xid=user2.xid)
        self.factories.watch.create(guild_xid=guild2.xid, user_xid=user3.xid)

        self.ctx.guild_id = guild1.xid
        cog = WatchCog(self.bot)
        await cog.watched.func(cog, self.ctx)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                f"• <@{user1.xid}> — {watch1.note}\n"
                f"• <@{user2.xid}> — {watch2.note}\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
        }

    async def test_watched_multiple_pages(self, monkeypatch):
        guild1 = self.factories.guild.create()
        users = [
            self.factories.user.create(xid=101),
            self.factories.user.create(xid=102),
            self.factories.user.create(xid=103),
            self.factories.user.create(xid=104),
            self.factories.user.create(xid=105),
        ]
        watches = [
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[0].xid,
                note="ab " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[1].xid,
                note="cd " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[2].xid,
                note="ef " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[3].xid,
                note="gh " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[4].xid,
                note="ij " * 333,
            ),
        ]

        paginator_mock = MagicMock()
        paginator_mock.start = AsyncMock()
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(watch_interaction, "Paginator", Paginator_mock)

        self.ctx.guild_id = guild1.xid
        cog = WatchCog(self.bot)
        await cog.watched.func(cog, self.ctx)
        Paginator_mock.assert_called_once()
        assert Paginator_mock.call_args_list[0].kwargs["config"] is Config.MINIMAL
        pages = Paginator_mock.call_args_list[0].kwargs["pages"]
        assert len(pages) == 2
        assert pages[0].to_dict() == {
            "color": self.settings.EMBED_COLOR,
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
        }
        assert pages[1].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (f"• <@{users[4].xid}> — {watches[4].note}\n"),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "footer": {"text": "page 2 of 2"},
        }
        paginator_mock.start.assert_called_once_with(self.ctx)

    async def test_watched_pagination_start_error(self, monkeypatch, caplog):
        guild1 = self.factories.guild.create()
        user1 = self.factories.user.create(xid=101)
        user2 = self.factories.user.create(xid=102)
        user3 = self.factories.user.create(xid=103)
        user4 = self.factories.user.create(xid=104)
        user5 = self.factories.user.create(xid=105)
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user1.xid,
            note="ab " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user2.xid,
            note="cd " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user3.xid,
            note="ef " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user4.xid,
            note="gh " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user5.xid,
            note="ij " * 333,
        )

        paginator_mock = MagicMock()
        error = RuntimeError("start-error")
        paginator_mock.start = AsyncMock(side_effect=error)
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(watch_interaction, "Paginator", Paginator_mock)

        self.ctx.guild_id = guild1.xid
        cog = WatchCog(self.bot)
        await cog.watched.func(cog, self.ctx)

        assert "warning: discord: pagination error: start-error" in caplog.text
