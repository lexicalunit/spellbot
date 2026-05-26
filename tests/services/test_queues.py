from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from spellbot.enums import GameBracket, GameFormat
from spellbot.services import queues

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db

NOW = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
class TestPublicActiveQueues:
    async def test_empty_returns_empty_list(self) -> None:
        assert await queues.public_active_queues() == []

    async def test_excludes_started_deleted_banned_unpromoted_and_empty_queues(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=970001, name="OK Guild", locale="en")
        banned = factories.guild.create(xid=970002, name="Banned", banned=True)
        unpromoted = factories.guild.create(xid=970003, name="Hidden", promote=False)
        ch = factories.channel.create(xid=970101, name="lfg", guild=guild)
        ch_b = factories.channel.create(xid=970102, name="lfg-b", guild=banned)
        ch_u = factories.channel.create(xid=970103, name="lfg-u", guild=unpromoted)
        u1 = factories.user.create(xid=870001, name="u1")
        u2 = factories.user.create(xid=870002, name="u2")
        u3 = factories.user.create(xid=870003, name="u3")
        pending = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        started = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW,
            created_at=NOW - timedelta(minutes=5),
        )
        deleted = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
            deleted_at=NOW,
        )
        on_banned = factories.game.create(
            guild=banned,
            channel=ch_b,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        on_unpromoted = factories.game.create(
            guild=unpromoted,
            channel=ch_u,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        empty = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        del empty
        factories.queue.create(user_xid=u1.xid, game_id=pending.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=started.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u1.xid, game_id=deleted.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=on_banned.id, og_guild_xid=banned.xid)
        factories.queue.create(
            user_xid=u3.xid, game_id=on_unpromoted.id, og_guild_xid=unpromoted.xid
        )

        rows = await queues.public_active_queues()
        assert len(rows) == 1
        assert rows[0]["guild_name"] == "OK Guild"

    async def test_orders_shortest_wait_first_and_aggregates_fields(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=971001, name="Alpha", locale="ja")
        ch = factories.channel.create(xid=971101, name="lfg", guild=guild)
        u1 = factories.user.create(xid=871001, name="u1")
        u2 = factories.user.create(xid=871002, name="u2")
        older = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=10),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_3.value,
            seats=4,
        )
        newer = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=2),
            format=GameFormat.MODERN.value,
            seats=2,
        )
        factories.queue.create(user_xid=u1.xid, game_id=older.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=older.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u1.xid, game_id=newer.id, og_guild_xid=guild.xid)

        rows = await queues.public_active_queues()
        assert [r["players"] for r in rows] == [1, 2]
        assert [r["seats"] for r in rows] == [2, 4]
        assert [r["wait_seconds"] for r in rows] == [2 * 60, 10 * 60]
        assert rows[0]["format"] == str(GameFormat.MODERN)
        assert rows[0]["bracket"] == str(GameBracket.NONE)
        assert rows[1]["format"] == str(GameFormat.COMMANDER)
        assert rows[1]["bracket"] == str(GameBracket.BRACKET_3)
        assert rows[1]["guild_locale"] == "ja"
        assert rows[1]["guild_xid"] == guild.xid
        assert rows[1]["guild_icon"] is None

    async def test_includes_cached_guild_icon(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        icon = "https://cdn.discordapp.com/icons/973001/abc.png"
        guild = factories.guild.create(xid=973001, name="With Icon", icon=icon)
        ch = factories.channel.create(xid=973101, name="lfg", guild=guild)
        u1 = factories.user.create(xid=873001, name="u1")
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=1),
        )
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)

        rows = await queues.public_active_queues()
        assert len(rows) == 1
        assert rows[0]["guild_icon"] == icon

    async def test_jump_url_prefers_latest_post_else_channel_only(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=972001, name="Gamma")
        ch = factories.channel.create(xid=972101, name="lfg", guild=guild)
        u1 = factories.user.create(xid=872001, name="u1")
        u2 = factories.user.create(xid=872002, name="u2")
        u3 = factories.user.create(xid=872003, name="u3")
        with_post = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        without_post = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=2),
        )
        factories.queue.create(user_xid=u1.xid, game_id=with_post.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=with_post.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u3.xid, game_id=without_post.id, og_guild_xid=guild.xid)
        freezer.move_to(NOW - timedelta(seconds=10))
        factories.post.create(
            guild=guild,
            channel=ch,
            game=with_post,
            message_xid=111111,
        )
        freezer.move_to(NOW)
        factories.post.create(
            guild=guild,
            channel=ch,
            game=with_post,
            message_xid=222222,
        )

        rows = await queues.public_active_queues()
        by_players = {r["players"]: r["jump_url"] for r in rows}
        assert by_players[2] == f"https://discord.com/channels/{guild.xid}/{ch.xid}/222222"
        assert by_players[1] == f"https://discord.com/channels/{guild.xid}/{ch.xid}"
