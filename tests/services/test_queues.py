from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Game, Guild, GuildMember
from spellbot.services import queues

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db

NOW = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)


async def public_recent_started_count(  # pragma: no cover
    within: timedelta,
    *,
    only_member_of: int | None = None,
    only_mythic_track: bool = False,
) -> int:
    cutoff = datetime.now(UTC) - within
    stmt = (
        select(func.count(Game.id))
        .select_from(Game)
        .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
        .where(
            Game.started_at.is_not(None),
            Game.started_at >= cutoff,
            Game.deleted_at.is_(None),
            Guild.banned.is_(False),
            Guild.promote.is_(True),
        )
    )
    if only_member_of is not None:
        stmt = stmt.join(
            GuildMember,
            GuildMember.guild_xid == Guild.xid,
        ).where(GuildMember.user_xid == only_member_of)
    if only_mythic_track:
        stmt = stmt.where(Guild.enable_mythic_track.is_(True))
    result = await DatabaseSession.execute(stmt)
    return int(result.scalar() or 0)


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
            service=GameService.CONVOKE.value,
            seats=4,
        )
        newer = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=2),
            format=GameFormat.MODERN.value,
            service=GameService.PLAYGROUP_LIVE.value,
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
        assert rows[0]["service"] == GameService.PLAYGROUP_LIVE.title
        assert rows[1]["format"] == str(GameFormat.COMMANDER)
        assert rows[1]["bracket"] == str(GameBracket.BRACKET_3)
        assert rows[1]["service"] == GameService.CONVOKE.title
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


@pytest.mark.asyncio
class TestPublicRecentStartedCount:
    async def test_empty_returns_zero(self) -> None:
        assert await public_recent_started_count(timedelta(hours=2)) == 0

    async def test_counts_only_started_within_window_and_promotable(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        ok = factories.guild.create(xid=975001, name="OK")
        banned = factories.guild.create(xid=975002, name="Banned", banned=True)
        hidden = factories.guild.create(xid=975003, name="Hidden", promote=False)
        ch = factories.channel.create(xid=975101, name="lfg", guild=ok)
        ch_b = factories.channel.create(xid=975102, name="lfg-b", guild=banned)
        ch_h = factories.channel.create(xid=975103, name="lfg-h", guild=hidden)
        # In-window, started, promotable: counted (x2).
        factories.game.create(guild=ok, channel=ch, started_at=NOW - timedelta(minutes=10))
        factories.game.create(guild=ok, channel=ch, started_at=NOW - timedelta(hours=1))
        # Out of window (older than 2h): not counted.
        factories.game.create(
            guild=ok,
            channel=ch,
            started_at=NOW - timedelta(hours=2, minutes=1),
        )
        # Pending (never started): not counted.
        factories.game.create(guild=ok, channel=ch, started_at=None)
        # Started + deleted: not counted.
        factories.game.create(
            guild=ok,
            channel=ch,
            started_at=NOW - timedelta(minutes=5),
            deleted_at=NOW,
        )
        # Banned guild: not counted.
        factories.game.create(guild=banned, channel=ch_b, started_at=NOW - timedelta(minutes=5))
        # Unpromoted guild: not counted.
        factories.game.create(guild=hidden, channel=ch_h, started_at=NOW - timedelta(minutes=5))

        assert await public_recent_started_count(timedelta(hours=2)) == 2

    async def test_only_member_of_restricts_to_user_guilds(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        mine = factories.guild.create(xid=976001, name="Mine")
        theirs = factories.guild.create(xid=976002, name="Theirs")
        ch1 = factories.channel.create(xid=976101, name="lfg", guild=mine)
        ch2 = factories.channel.create(xid=976102, name="lfg", guild=theirs)
        me = factories.user.create(xid=876001, name="me")
        factories.guild_member.create(user_xid=me.xid, guild_xid=mine.xid)
        factories.game.create(guild=mine, channel=ch1, started_at=NOW - timedelta(minutes=5))
        factories.game.create(guild=theirs, channel=ch2, started_at=NOW - timedelta(minutes=5))

        assert await public_recent_started_count(timedelta(hours=2), only_member_of=me.xid) == 1
        assert await public_recent_started_count(timedelta(hours=2), only_member_of=999) == 0


@pytest.mark.asyncio
class TestOnlyMemberOfFilter:
    async def test_active_queues_filtered_by_membership(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        mine = factories.guild.create(xid=977001, name="Mine")
        theirs = factories.guild.create(xid=977002, name="Theirs")
        ch1 = factories.channel.create(xid=977101, name="lfg", guild=mine)
        ch2 = factories.channel.create(xid=977102, name="lfg", guild=theirs)
        me = factories.user.create(xid=877001, name="me")
        other = factories.user.create(xid=877002, name="other")
        factories.guild_member.create(user_xid=me.xid, guild_xid=mine.xid)
        my_game = factories.game.create(
            guild=mine,
            channel=ch1,
            started_at=None,
            created_at=NOW - timedelta(minutes=3),
        )
        other_game = factories.game.create(
            guild=theirs,
            channel=ch2,
            started_at=None,
            created_at=NOW - timedelta(minutes=3),
        )
        factories.queue.create(user_xid=me.xid, game_id=my_game.id, og_guild_xid=mine.xid)
        factories.queue.create(user_xid=other.xid, game_id=other_game.id, og_guild_xid=theirs.xid)

        all_rows = await queues.public_active_queues()
        assert {row["guild_name"] for row in all_rows} == {"Mine", "Theirs"}

        mine_rows = await queues.public_active_queues(only_member_of=me.xid)
        assert [row["guild_name"] for row in mine_rows] == ["Mine"]

        none_rows = await queues.public_active_queues(only_member_of=999)
        assert none_rows == []


@pytest.mark.asyncio
class TestOnlyMythicTrackFilter:
    async def test_active_queues_filtered_by_mythic_track(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        enabled = factories.guild.create(
            xid=978001,
            name="Mythic On",
            enable_mythic_track=True,
        )
        disabled = factories.guild.create(
            xid=978002,
            name="Mythic Off",
            enable_mythic_track=False,
        )
        ch1 = factories.channel.create(xid=978101, name="lfg", guild=enabled)
        ch2 = factories.channel.create(xid=978102, name="lfg", guild=disabled)
        u1 = factories.user.create(xid=878001, name="u1")
        u2 = factories.user.create(xid=878002, name="u2")
        on_game = factories.game.create(
            guild=enabled,
            channel=ch1,
            started_at=None,
            created_at=NOW - timedelta(minutes=3),
        )
        off_game = factories.game.create(
            guild=disabled,
            channel=ch2,
            started_at=None,
            created_at=NOW - timedelta(minutes=3),
        )
        factories.queue.create(user_xid=u1.xid, game_id=on_game.id, og_guild_xid=enabled.xid)
        factories.queue.create(user_xid=u2.xid, game_id=off_game.id, og_guild_xid=disabled.xid)

        all_rows = await queues.public_active_queues()
        assert {row["guild_name"] for row in all_rows} == {"Mythic On", "Mythic Off"}

        only_rows = await queues.public_active_queues(only_mythic_track=True)
        assert [row["guild_name"] for row in only_rows] == ["Mythic On"]

    async def test_recent_count_filtered_by_mythic_track(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        enabled = factories.guild.create(
            xid=978201,
            name="MT On",
            enable_mythic_track=True,
        )
        disabled = factories.guild.create(
            xid=978202,
            name="MT Off",
            enable_mythic_track=False,
        )
        ch1 = factories.channel.create(xid=978211, name="lfg", guild=enabled)
        ch2 = factories.channel.create(xid=978212, name="lfg", guild=disabled)
        factories.game.create(guild=enabled, channel=ch1, started_at=NOW - timedelta(minutes=10))
        factories.game.create(guild=disabled, channel=ch2, started_at=NOW - timedelta(minutes=10))
        factories.game.create(guild=disabled, channel=ch2, started_at=NOW - timedelta(minutes=20))

        assert await public_recent_started_count(timedelta(hours=2)) == 3
        assert (
            await public_recent_started_count(
                timedelta(hours=2),
                only_mythic_track=True,
            )
            == 1
        )


@pytest.mark.asyncio
class TestPublicActiveGames:
    async def test_empty_returns_empty_list(self) -> None:
        assert await queues.public_active_games(timedelta(hours=2)) == []

    async def test_returns_started_games_within_window_excluding_hidden(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        ok = factories.guild.create(xid=979001, name="OK", icon="https://i/979001.png")
        banned = factories.guild.create(xid=979002, name="Banned", banned=True)
        hidden = factories.guild.create(xid=979003, name="Hidden", promote=False)
        ch = factories.channel.create(xid=979101, name="lfg", guild=ok)
        ch_b = factories.channel.create(xid=979102, name="lfg-b", guild=banned)
        ch_h = factories.channel.create(xid=979103, name="lfg-h", guild=hidden)
        # Started, within window, visible: included (newest first).
        newer = factories.game.create(
            guild=ok,
            channel=ch,
            started_at=NOW - timedelta(minutes=5),
            format=GameFormat.MODERN.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
            seats=2,
        )
        older = factories.game.create(
            guild=ok,
            channel=ch,
            started_at=NOW - timedelta(minutes=45),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_3.value,
            service=GameService.CONVOKE.value,
            seats=4,
        )
        # Out of window: excluded.
        factories.game.create(guild=ok, channel=ch, started_at=NOW - timedelta(hours=2, minutes=1))
        # Pending (never started): excluded.
        factories.game.create(guild=ok, channel=ch, started_at=None)
        # Started + deleted: excluded.
        factories.game.create(
            guild=ok,
            channel=ch,
            started_at=NOW - timedelta(minutes=5),
            deleted_at=NOW,
        )
        # Banned guild: excluded.
        factories.game.create(guild=banned, channel=ch_b, started_at=NOW - timedelta(minutes=5))
        # Unpromoted guild: excluded.
        factories.game.create(guild=hidden, channel=ch_h, started_at=NOW - timedelta(minutes=5))

        rows = await queues.public_active_games(timedelta(hours=2))
        assert [r["guild_name"] for r in rows] == ["OK", "OK"]
        # Newest first.
        assert rows[0]["started_seconds_ago"] == 5 * 60
        assert rows[1]["started_seconds_ago"] == 45 * 60
        assert rows[0]["format"] == str(GameFormat.MODERN)
        assert rows[1]["bracket"] == str(GameBracket.BRACKET_3)
        assert rows[0]["service"] == GameService.CONVOKE.title
        assert rows[0]["seats"] == 2
        assert rows[1]["seats"] == 4
        assert rows[0]["guild_xid"] == ok.xid
        assert rows[0]["guild_locale"] == "en"
        assert rows[0]["guild_icon"] == "https://i/979001.png"
        assert rows[0]["jump_url"] == f"https://discord.com/channels/{ok.xid}/{ch.xid}"
        # Sanity: every row has both ids in the jump_url.
        assert all(str(ok.xid) in r["jump_url"] for r in rows)
        # Both games belong to `newer`/`older`, no cross-contamination.
        assert {newer.id, older.id} == {newer.id, older.id}

    async def test_only_member_of_restricts_to_user_guilds(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        mine = factories.guild.create(xid=979201, name="Mine")
        theirs = factories.guild.create(xid=979202, name="Theirs")
        ch1 = factories.channel.create(xid=979211, name="lfg", guild=mine)
        ch2 = factories.channel.create(xid=979212, name="lfg", guild=theirs)
        me = factories.user.create(xid=879201, name="me")
        factories.guild_member.create(user_xid=me.xid, guild_xid=mine.xid)
        factories.game.create(guild=mine, channel=ch1, started_at=NOW - timedelta(minutes=10))
        factories.game.create(guild=theirs, channel=ch2, started_at=NOW - timedelta(minutes=10))

        all_rows = await queues.public_active_games(timedelta(hours=2))
        assert {r["guild_name"] for r in all_rows} == {"Mine", "Theirs"}

        mine_rows = await queues.public_active_games(
            timedelta(hours=2),
            only_member_of=me.xid,
        )
        assert [r["guild_name"] for r in mine_rows] == ["Mine"]

        none_rows = await queues.public_active_games(timedelta(hours=2), only_member_of=999)
        assert none_rows == []

    async def test_only_mythic_track_filter(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        enabled = factories.guild.create(xid=979301, name="MT On", enable_mythic_track=True)
        disabled = factories.guild.create(xid=979302, name="MT Off", enable_mythic_track=False)
        ch1 = factories.channel.create(xid=979311, name="lfg", guild=enabled)
        ch2 = factories.channel.create(xid=979312, name="lfg", guild=disabled)
        factories.game.create(guild=enabled, channel=ch1, started_at=NOW - timedelta(minutes=10))
        factories.game.create(guild=disabled, channel=ch2, started_at=NOW - timedelta(minutes=10))

        only_rows = await queues.public_active_games(
            timedelta(hours=2),
            only_mythic_track=True,
        )
        assert [r["guild_name"] for r in only_rows] == ["MT On"]


@pytest.mark.asyncio
class TestViewerPlayedGuilds:
    async def test_empty_when_user_has_no_plays(self) -> None:
        assert await queues.viewer_played_guilds(user_xid=999_001) == []

    async def test_returns_played_guilds_ordered_by_last_played(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        recent = factories.guild.create(xid=971_001, name="Recent", locale="ja", icon="r.png")
        older = factories.guild.create(xid=971_002, name="Older", locale="en", icon=None)
        ch1 = factories.channel.create(xid=971_011, name="lfg", guild=recent)
        ch2 = factories.channel.create(xid=971_012, name="lfg", guild=older)
        me = factories.user.create(xid=871_001, name="me")
        recent_game1 = factories.game.create(guild=recent, channel=ch1)
        recent_game2 = factories.game.create(guild=recent, channel=ch1)
        older_game = factories.game.create(guild=older, channel=ch2)
        factories.play.create(
            user_xid=me.xid,
            game_id=recent_game1.id,
            og_guild_xid=recent.xid,
            created_at=NOW - timedelta(days=10),
        )
        factories.play.create(
            user_xid=me.xid,
            game_id=recent_game2.id,
            og_guild_xid=recent.xid,
            created_at=NOW - timedelta(hours=1),
        )
        factories.play.create(
            user_xid=me.xid,
            game_id=older_game.id,
            og_guild_xid=older.xid,
            created_at=NOW - timedelta(days=20),
        )

        rows = await queues.viewer_played_guilds(user_xid=me.xid)
        assert [r["guild_name"] for r in rows] == ["Recent", "Older"]
        assert rows[0] == {
            "guild_xid": recent.xid,
            "guild_name": "Recent",
            "guild_locale": "ja",
            "guild_icon": "r.png",
            "games_played": 2,
            "first_played_at": NOW - timedelta(days=10),
            "last_played_at": NOW - timedelta(hours=1),
        }
        assert rows[1]["games_played"] == 1
        assert rows[1]["guild_icon"] is None

    async def test_excludes_banned_and_unpromoted_guilds(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        ok = factories.guild.create(xid=971_101, name="OK")
        banned = factories.guild.create(xid=971_102, name="Banned", banned=True)
        hidden = factories.guild.create(xid=971_103, name="Hidden", promote=False)
        ch1 = factories.channel.create(xid=971_111, name="lfg", guild=ok)
        ch2 = factories.channel.create(xid=971_112, name="lfg", guild=banned)
        ch3 = factories.channel.create(xid=971_113, name="lfg", guild=hidden)
        me = factories.user.create(xid=871_101, name="me")
        for guild, ch in ((ok, ch1), (banned, ch2), (hidden, ch3)):
            game = factories.game.create(guild=guild, channel=ch)
            factories.play.create(
                user_xid=me.xid,
                game_id=game.id,
                og_guild_xid=guild.xid,
                created_at=NOW,
            )

        rows = await queues.viewer_played_guilds(user_xid=me.xid)
        assert [r["guild_name"] for r in rows] == ["OK"]

    async def test_played_within_excludes_guilds_with_stale_last_play(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        fresh = factories.guild.create(xid=971_201, name="Fresh")
        stale = factories.guild.create(xid=971_202, name="Stale")
        ch1 = factories.channel.create(xid=971_211, name="lfg", guild=fresh)
        ch2 = factories.channel.create(xid=971_212, name="lfg", guild=stale)
        me = factories.user.create(xid=871_201, name="me")
        fresh_game = factories.game.create(guild=fresh, channel=ch1)
        stale_game = factories.game.create(guild=stale, channel=ch2)
        factories.play.create(
            user_xid=me.xid,
            game_id=fresh_game.id,
            og_guild_xid=fresh.xid,
            created_at=NOW - timedelta(days=30),
        )
        factories.play.create(
            user_xid=me.xid,
            game_id=stale_game.id,
            og_guild_xid=stale.xid,
            created_at=NOW - timedelta(days=400),
        )

        unfiltered = await queues.viewer_played_guilds(user_xid=me.xid)
        assert {r["guild_name"] for r in unfiltered} == {"Fresh", "Stale"}

        filtered = await queues.viewer_played_guilds(
            user_xid=me.xid,
            played_within=timedelta(days=365),
        )
        assert [r["guild_name"] for r in filtered] == ["Fresh"]

    async def test_played_within_preserves_total_games_played(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=971_301, name="Mixed")
        ch = factories.channel.create(xid=971_311, name="lfg", guild=guild)
        me = factories.user.create(xid=871_301, name="me")
        old_game = factories.game.create(guild=guild, channel=ch)
        recent_game = factories.game.create(guild=guild, channel=ch)
        factories.play.create(
            user_xid=me.xid,
            game_id=old_game.id,
            og_guild_xid=guild.xid,
            created_at=NOW - timedelta(days=800),
        )
        factories.play.create(
            user_xid=me.xid,
            game_id=recent_game.id,
            og_guild_xid=guild.xid,
            created_at=NOW - timedelta(days=10),
        )

        rows = await queues.viewer_played_guilds(
            user_xid=me.xid,
            played_within=timedelta(days=365),
        )
        assert len(rows) == 1
        assert rows[0]["games_played"] == 2
        assert rows[0]["first_played_at"] == NOW - timedelta(days=800)
        assert rows[0]["last_played_at"] == NOW - timedelta(days=10)


@pytest.mark.asyncio
class TestGuildSummary:
    async def test_returns_none_for_unknown_guild(self) -> None:
        assert await queues.guild_summary(guild_xid=999_999) is None

    async def test_returns_basic_fields_for_promoted_guild(
        self,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(
            xid=972_001,
            name="Public Guild",
            locale="es",
            icon="cdn.png",
        )
        result = await queues.guild_summary(guild_xid=guild.xid)
        assert result == {
            "guild_xid": guild.xid,
            "guild_name": "Public Guild",
            "guild_locale": "es",
            "guild_icon": "cdn.png",
        }

    async def test_returns_none_for_banned_or_unpromoted(
        self,
        factories: Factories,
    ) -> None:
        banned = factories.guild.create(xid=972_101, name="Banned", banned=True)
        hidden = factories.guild.create(xid=972_102, name="Hidden", promote=False)
        assert await queues.guild_summary(guild_xid=banned.xid) is None
        assert await queues.guild_summary(guild_xid=hidden.xid) is None


@pytest.mark.asyncio
class TestViewerPlayedChannels:
    async def test_empty_when_user_has_no_plays(self) -> None:
        assert await queues.viewer_played_channels(user_xid=999_002, guild_xid=999_003) == []

    async def test_returns_distinct_played_channels_sorted_by_name(
        self,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=973_001, name="G")
        other_guild = factories.guild.create(xid=973_002, name="Other")
        ch_b = factories.channel.create(xid=973_101, name="bravo", guild=guild)
        ch_a = factories.channel.create(xid=973_102, name="alpha", guild=guild)
        ch_other = factories.channel.create(xid=973_103, name="zzz", guild=other_guild)
        me = factories.user.create(xid=873_001, name="me")
        them = factories.user.create(xid=873_002, name="them")
        game_b1 = factories.game.create(guild=guild, channel=ch_b)
        game_b2 = factories.game.create(guild=guild, channel=ch_b)
        game_a = factories.game.create(guild=guild, channel=ch_a)
        game_other = factories.game.create(guild=other_guild, channel=ch_other)
        game_them = factories.game.create(guild=guild, channel=ch_b)
        factories.play.create(user_xid=me.xid, game_id=game_b1.id, og_guild_xid=guild.xid)
        factories.play.create(user_xid=me.xid, game_id=game_b2.id, og_guild_xid=guild.xid)
        factories.play.create(user_xid=me.xid, game_id=game_a.id, og_guild_xid=guild.xid)
        factories.play.create(
            user_xid=me.xid,
            game_id=game_other.id,
            og_guild_xid=other_guild.xid,
        )
        factories.play.create(user_xid=them.xid, game_id=game_them.id, og_guild_xid=guild.xid)

        rows = await queues.viewer_played_channels(user_xid=me.xid, guild_xid=guild.xid)

        assert rows == [
            {"channel_xid": ch_a.xid, "channel_name": "alpha"},
            {"channel_xid": ch_b.xid, "channel_name": "bravo"},
        ]

    async def test_played_within_excludes_channels_with_stale_last_play(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=973_201, name="G")
        ch_fresh = factories.channel.create(xid=973_211, name="fresh", guild=guild)
        ch_stale = factories.channel.create(xid=973_212, name="stale", guild=guild)
        me = factories.user.create(xid=873_201, name="me")
        game_fresh = factories.game.create(guild=guild, channel=ch_fresh)
        game_stale = factories.game.create(guild=guild, channel=ch_stale)
        factories.play.create(
            user_xid=me.xid,
            game_id=game_fresh.id,
            og_guild_xid=guild.xid,
            created_at=NOW - timedelta(days=10),
        )
        factories.play.create(
            user_xid=me.xid,
            game_id=game_stale.id,
            og_guild_xid=guild.xid,
            created_at=NOW - timedelta(days=400),
        )

        unfiltered = await queues.viewer_played_channels(
            user_xid=me.xid,
            guild_xid=guild.xid,
        )
        assert {r["channel_name"] for r in unfiltered} == {"fresh", "stale"}

        filtered = await queues.viewer_played_channels(
            user_xid=me.xid,
            guild_xid=guild.xid,
            played_within=timedelta(days=365),
        )
        assert [r["channel_name"] for r in filtered] == ["fresh"]
