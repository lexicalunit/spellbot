from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from spellbot.enums import GameBracket, GameFormat
from spellbot.models import GameStatus

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
    from freezegun.api import FrozenDateTimeFactory
    from syrupy.assertion import SnapshotAssertion

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestWebRecord:
    async def test_user_record(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user:1")
        user2 = factories.user.create(xid=102, name="user@2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid)
        factories.play.create(game_id=game2.id, user_xid=user1.xid)
        factories.play.create(game_id=game2.id, user_xid=user2.xid)
        factories.play.create(game_id=game3.id, user_xid=user1.xid)
        factories.play.create(game_id=game3.id, user_xid=user2.xid)

        resp = await client.get(f"/u/{user1.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_with_cookies(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user:1")
        user2 = factories.user.create(xid=102, name="user@2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid)
        factories.play.create(game_id=game2.id, user_xid=user1.xid)
        factories.play.create(game_id=game2.id, user_xid=user2.xid)
        factories.play.create(game_id=game3.id, user_xid=user1.xid)
        factories.play.create(game_id=game3.id, user_xid=user2.xid)

        resp = await client.get(
            f"/u/{user1.xid}",
            cookies={
                "timezone_offset": "480",
                "timezone_name": "America/Los_Angeles",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_no_plays(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
    ) -> None:
        user = factories.user.create(xid=101, name="user")

        resp = await client.get(f"/u/{user.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user1")
        user2 = factories.user.create(xid=102, name="user2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid)
        factories.play.create(game_id=game2.id, user_xid=user1.xid)
        factories.play.create(game_id=game2.id, user_xid=user2.xid)
        factories.play.create(game_id=game3.id, user_xid=user1.xid)
        factories.play.create(game_id=game3.id, user_xid=user2.xid)

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record_with_cookies(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user1")
        user2 = factories.user.create(xid=102, name="user2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid)
        factories.play.create(game_id=game2.id, user_xid=user1.xid)
        factories.play.create(game_id=game2.id, user_xid=user2.xid)
        factories.play.create(game_id=game3.id, user_xid=user1.xid)
        factories.play.create(game_id=game3.id, user_xid=user2.xid)

        resp = await client.get(
            f"/g/{guild.xid}/c/{channel.xid}",
            cookies={
                "timezone_offset": "480",
                "timezone_name": "America/Los_Angeles",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record_with_invalid_cookies(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user1")
        user2 = factories.user.create(xid=102, name="user2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid)
        factories.play.create(game_id=game2.id, user_xid=user1.xid)
        factories.play.create(game_id=game2.id, user_xid=user2.xid)
        factories.play.create(game_id=game3.id, user_xid=user1.xid)
        factories.play.create(game_id=game3.id, user_xid=user2.xid)

        resp = await client.get(
            f"/g/{guild.xid}/c/{channel.xid}",
            cookies={
                "timezone_offset": "BOGUS",
                "timezone_name": "America/Los_Angeles",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record_no_plays(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=101, name="channel", guild=guild)

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_invalid_ids(self, client: ClientSession) -> None:
        resp = await client.get("/u/xyz")
        assert resp.status == 404

    async def test_channel_record_invalid_ids(self, client: ClientSession) -> None:
        resp = await client.get("/g/abc/c/xyz")
        assert resp.status == 404

    async def test_user_record_missing_user(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/u/404")
        assert resp.status == 404

    async def test_channel_record_missing_guild(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        resp = await client.get(f"/g/404/c/{channel.xid}")
        assert resp.status == 404

    async def test_channel_record_missing_channel(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        resp = await client.get(f"/g/{guild.xid}/c/404")
        assert resp.status == 404


@pytest.mark.asyncio
class TestWebRecordFilters:
    """Tests for the filter and sort query parameters on the record listing pages."""

    @staticmethod
    def seed_channel(factories: Factories) -> tuple[int, int, list[int]]:
        guild = factories.guild.create(xid=701, name="filter-guild")
        channel = factories.channel.create(xid=801, name="filter-channel", guild=guild)
        users = [
            factories.user.create(xid=601, name="alice"),
            factories.user.create(xid=602, name="bob"),
        ]
        game_ids: list[int] = []
        cases: list[tuple[int, int, int, datetime]] = [
            (11, GameFormat.MODERN.value, GameBracket.NONE.value, datetime(2024, 1, 1, tzinfo=UTC)),
            (
                12,
                GameFormat.LEGACY.value,
                GameBracket.BRACKET_1.value,
                datetime(2024, 2, 1, tzinfo=UTC),
            ),
            (
                13,
                GameFormat.MODERN.value,
                GameBracket.BRACKET_2.value,
                datetime(2024, 3, 1, tzinfo=UTC),
            ),
        ]
        for gid, fmt, brk, when in cases:
            g = factories.game.create(
                id=gid,
                seats=2,
                status=GameStatus.STARTED.value,
                format=fmt,
                bracket=brk,
                guild=guild,
                channel=channel,
                created_at=when,
                updated_at=when,
            )
            factories.post.create(guild=guild, channel=channel, game=g, message_xid=9000 + gid)
            for u in users:
                factories.play.create(game_id=g.id, user_xid=u.xid)
            game_ids.append(gid)
        return guild.xid, channel.xid, game_ids

    async def test_channel_filter_by_format(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        resp = await client.get(
            f"/g/{guild_xid}/c/{channel_xid}?formats={GameFormat.MODERN.value}",
        )
        assert resp.status == 200
        text = await resp.text()
        assert "SB#11" in text
        assert "SB#13" in text
        assert "SB#12" not in text
        assert "(2 matching)" in text

    async def test_channel_filter_by_multi_bracket(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        resp = await client.get(
            f"/g/{guild_xid}/c/{channel_xid}"
            f"?brackets={GameBracket.BRACKET_1.value}&brackets={GameBracket.BRACKET_2.value}",
        )
        assert resp.status == 200
        text = await resp.text()
        assert "SB#11" not in text
        assert "SB#12" in text
        assert "SB#13" in text
        assert "(2 matching)" in text

    async def test_channel_filter_by_date_range_with_tz(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        # Viewer at UTC-8 (offset=480) requesting Feb 1, 2024 in local time should still
        # match the game recorded at 2024-02-01T00:00:00Z because Feb 1 local starts
        # at 2024-02-01T08:00:00Z and the previous local day window includes that game.
        resp = await client.get(
            f"/g/{guild_xid}/c/{channel_xid}?from=2024-01-31&to=2024-01-31",
            cookies={"timezone_offset": "480", "timezone_name": "America/Los_Angeles"},
        )
        assert resp.status == 200
        text = await resp.text()
        assert "(1 matching)" in text
        assert "SB#12" in text
        assert "SB#11" not in text
        assert "SB#13" not in text

    async def test_channel_sort_ascending_by_id(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        resp = await client.get(f"/g/{guild_xid}/c/{channel_xid}?sort=id&dir=asc")
        assert resp.status == 200
        text = await resp.text()
        i11 = text.index("SB#11")
        i12 = text.index("SB#12")
        i13 = text.index("SB#13")
        assert i11 < i12 < i13
        # The current sort column header should carry the up-arrow indicator.
        assert 'href="?sort=id&amp;dir=desc">Game<span class="arrow">&#9650;' in text

    async def test_channel_invalid_sort_falls_back(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        resp = await client.get(
            f"/g/{guild_xid}/c/{channel_xid}?sort=evil;DROP&dir=sideways",
        )
        assert resp.status == 200
        text = await resp.text()
        # Default sort is updated_at desc; SB#13 (latest) should appear before SB#11.
        assert text.index("SB#13") < text.index("SB#11")

    async def test_channel_filter_by_player_name(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        resp = await client.get(f"/g/{guild_xid}/c/{channel_xid}?with_player=alice")
        assert resp.status == 200
        text = await resp.text()
        assert "(3 matching)" in text

    async def test_channel_filter_by_unknown_player_xid(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        resp = await client.get(f"/g/{guild_xid}/c/{channel_xid}?with_player=999999")
        assert resp.status == 200
        text = await resp.text()
        assert "(0 matching)" in text
        assert "No games found" in text

    async def test_user_filter_by_guild_name(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_a = factories.guild.create(xid=711, name="alpha-guild")
        guild_b = factories.guild.create(xid=712, name="beta-guild")
        chan_a = factories.channel.create(xid=811, name="ca", guild=guild_a)
        chan_b = factories.channel.create(xid=812, name="cb", guild=guild_b)
        user = factories.user.create(xid=611, name="solo")
        now = datetime(2024, 5, 5, tzinfo=UTC)
        ga = factories.game.create(
            id=21,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild_a,
            channel=chan_a,
            created_at=now,
            updated_at=now,
        )
        gb = factories.game.create(
            id=22,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild_b,
            channel=chan_b,
            created_at=now + timedelta(minutes=1),
            updated_at=now + timedelta(minutes=1),
        )
        factories.post.create(guild=guild_a, channel=chan_a, game=ga, message_xid=9101)
        factories.post.create(guild=guild_b, channel=chan_b, game=gb, message_xid=9102)
        factories.play.create(game_id=ga.id, user_xid=user.xid)
        factories.play.create(game_id=gb.id, user_xid=user.xid)

        resp = await client.get(f"/u/{user.xid}?guild=alpha")
        assert resp.status == 200
        text = await resp.text()
        assert "(1 matching)" in text
        assert "SB#21" in text
        assert "SB#22" not in text

        resp = await client.get(f"/u/{user.xid}?guild={guild_b.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert "(1 matching)" in text
        assert "SB#22" in text
        assert "SB#21" not in text

    async def test_pagination_qs_preserves_filters(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        resp = await client.get(
            f"/g/{guild_xid}/c/{channel_xid}?formats={GameFormat.MODERN.value}&sort=id&dir=asc",
        )
        assert resp.status == 200
        text = await resp.text()
        # The export and (when present) navigation links must carry the filters.
        assert f"export.csv?formats={GameFormat.MODERN.value}" in text
        assert "sort=id" in text
        assert "dir=asc" in text

    async def test_filter_tolerates_empty_and_invalid_tokens(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        # Empty tokens between commas and a non-integer token must be ignored
        # without rejecting the request. An invalid `from` date is also dropped.
        resp = await client.get(
            f"/g/{guild_xid}/c/{channel_xid}"
            f"?formats=,{GameFormat.MODERN.value},,abc,&from=not-a-date",
        )
        assert resp.status == 200
        text = await resp.text()
        assert "(2 matching)" in text

    async def test_date_filter_without_tz_cookie_uses_utc(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild_xid, channel_xid, _ = self.seed_channel(factories)
        # No timezone_offset cookie -> dates interpreted as UTC. Asking for
        # 2024-02-01..2024-02-01 should match exactly the Feb 1 game.
        resp = await client.get(
            f"/g/{guild_xid}/c/{channel_xid}?from=2024-02-01&to=2024-02-01",
        )
        assert resp.status == 200
        text = await resp.text()
        assert "(1 matching)" in text
        assert "SB#12" in text


@pytest.mark.asyncio
class TestWebRecordExport:
    async def test_user_export_success(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user-1")
        user2 = factories.user.create(xid=102, name="user-2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=901)
        factories.play.create(game_id=game.id, user_xid=user1.xid)
        factories.play.create(game_id=game.id, user_xid=user2.xid)

        resp = await client.get(f"/u/{user1.xid}/export.csv")
        assert resp.status == 200
        assert resp.headers["Content-Type"].startswith("text/csv")
        assert "attachment" in resp.headers["Content-Disposition"]
        assert f"user-{user1.xid}" in resp.headers["Content-Disposition"]
        assert resp.headers.get("Content-Encoding") == "gzip"

        body = (await resp.read()).decode("utf-8")
        lines = body.strip().split("\r\n")
        assert lines[0] == "Game,Time,Guild,Channel,Format,Seats,Bracket,Locale,Link,Players"
        assert len(lines) == 2
        assert lines[1].startswith(f"{game.id},2020-01-01T00:00:00+00:00,guild,channel,Modern,2,")
        assert "user-1 (101)" in lines[1]
        assert "user-2 (102)" in lines[1]

    async def test_user_export_no_plays(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        user = factories.user.create(xid=101, name="user")

        resp = await client.get(f"/u/{user.xid}/export.csv")
        assert resp.status == 200
        body = (await resp.read()).decode("utf-8")
        assert body.strip() == "Game,Time,Guild,Channel,Format,Seats,Bracket,Locale,Link,Players"

    async def test_user_export_missing_user(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/u/404/export.csv")
        assert resp.status == 404

    async def test_user_export_invalid_ids(self, client: ClientSession) -> None:
        resp = await client.get("/u/xyz/export.csv")
        assert resp.status == 404

    async def test_channel_export_success(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user-1")
        user2 = factories.user.create(xid=102, name="user-2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=901)
        factories.play.create(game_id=game.id, user_xid=user1.xid)
        factories.play.create(game_id=game.id, user_xid=user2.xid)

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}/export.csv")
        assert resp.status == 200
        assert resp.headers["Content-Type"].startswith("text/csv")
        assert f"channel-{channel.xid}" in resp.headers["Content-Disposition"]
        assert resp.headers.get("Content-Encoding") == "gzip"

        body = (await resp.read()).decode("utf-8")
        lines = body.strip().split("\r\n")
        assert (
            lines[0] == "Game,Time,Guild,Channel,Format,Seats,Bracket,Locale,Link,User Name,User ID"
        )
        assert len(lines) == 3
        assert "user-1,101" in lines[1] or "user-1,101" in lines[2]
        assert "user-2,102" in lines[1] or "user-2,102" in lines[2]

    async def test_channel_export_no_plays(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}/export.csv")
        assert resp.status == 200
        body = (await resp.read()).decode("utf-8")
        assert body.strip() == (
            "Game,Time,Guild,Channel,Format,Seats,Bracket,Locale,Link,User Name,User ID"
        )

    async def test_channel_export_missing_guild(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        resp = await client.get(f"/g/404/c/{channel.xid}/export.csv")
        assert resp.status == 404

    async def test_channel_export_missing_channel(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        resp = await client.get(f"/g/{guild.xid}/c/404/export.csv")
        assert resp.status == 404

    async def test_channel_export_invalid_ids(self, client: ClientSession) -> None:
        resp = await client.get("/g/abc/c/xyz/export.csv")
        assert resp.status == 404


@pytest.mark.asyncio
class TestWebGameDetail:
    async def test_game_detail_started(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user-1")
        user2 = factories.user.create(xid=102, name="user-2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            game_link="https://example.com/play/abc",
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
            started_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=901)
        factories.play.create(game_id=game.id, user_xid=user1.xid, og_guild_xid=guild.xid)
        factories.play.create(game_id=game.id, user_xid=user2.xid, og_guild_xid=guild.xid)

        resp = await client.get(f"/game/{game.id}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_game_detail_pending(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user = factories.user.create(xid=101, name="user-1")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=42,
            seats=4,
            status=GameStatus.PENDING.value,
            format=GameFormat.COMMANDER.value,
            guild=guild,
            channel=channel,
        )
        factories.queue.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)

        resp = await client.get(f"/game/{game.id}")
        assert resp.status == 200
        text = await resp.text()
        assert "SB#42" in text
        assert "Queued" in text
        assert "user-1" in text

    async def test_game_detail_with_cookies(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=7,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=901)
        resp = await client.get(
            f"/game/{game.id}",
            cookies={"timezone_offset": "480", "timezone_name": "America/Los_Angeles"},
        )
        assert resp.status == 200

    async def test_game_detail_missing(self, client: ClientSession) -> None:
        resp = await client.get("/game/99999")
        assert resp.status == 404

    async def test_game_detail_invalid_id(self, client: ClientSession) -> None:
        resp = await client.get("/game/abc")
        assert resp.status == 404
