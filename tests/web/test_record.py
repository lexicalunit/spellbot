from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from sqlalchemy import select

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat
from spellbot.models import Channel, GameStatus, Guild
from spellbot.web.api import admin_auth, record

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
    from freezegun.api import FrozenDateTimeFactory
    from pytest_mock import MockerFixture
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


@pytest.mark.asyncio
class TestWebGuildDetail:
    async def test_guild_detail(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        guild = factories.guild.create(xid=201, name="guild")
        channel1 = factories.channel.create(xid=301, name="channel-one", guild=guild)
        channel2 = factories.channel.create(xid=302, name="channel-two", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel1,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel1, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel2,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel2, game=game2, message_xid=902)

        resp = await client.get(f"/g/{guild.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_guild_detail_only_lists_channels_with_posts(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        posted = factories.channel.create(xid=301, name="posted", guild=guild)
        bare = factories.channel.create(xid=302, name="bare", guild=guild)
        game = factories.game.create(id=1, guild=guild, channel=posted)
        factories.post.create(guild=guild, channel=posted, game=game, message_xid=901)
        # A game without a post should not surface its channel.
        factories.game.create(id=2, guild=guild, channel=bare)

        resp = await client.get(f"/g/{guild.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert "posted" in text
        assert "bare" not in text
        assert f"/g/{guild.xid}/c/{posted.xid}" in text

    async def test_guild_detail_with_cookies(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(id=1, guild=guild, channel=channel)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=901)
        resp = await client.get(
            f"/g/{guild.xid}",
            cookies={"timezone_offset": "480", "timezone_name": "America/Los_Angeles"},
        )
        assert resp.status == 200

    async def test_guild_detail_no_channels(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        resp = await client.get(f"/g/{guild.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert "No channels with games yet." in text

    async def test_guild_detail_missing(self, client: ClientSession) -> None:
        resp = await client.get("/g/99999")
        assert resp.status == 404

    async def test_guild_detail_invalid_id(self, client: ClientSession) -> None:
        resp = await client.get("/g/abc")
        assert resp.status == 404

    async def test_guild_detail_hides_owner_controls_for_anonymous(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        resp = await client.get(f"/g/{guild.xid}")
        text = await resp.text()
        assert "Owner Controls" not in text


def make_owner_httpx_client() -> MagicMock:
    """Mock `httpx.AsyncClient` for an OAuth flow identifying the owner (xid=42)."""
    inner = MagicMock()
    token_resp = MagicMock(status_code=200)
    token_resp.json = MagicMock(return_value={"access_token": "tok"})
    inner.post = AsyncMock(return_value=token_resp)
    identify_resp = MagicMock(status_code=200)
    identify_resp.json = MagicMock(return_value={"id": "42", "username": "owner"})
    inner.get = AsyncMock(return_value=identify_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest_asyncio.fixture
async def owner_client(client: ClientSession, mocker: MockerFixture) -> ClientSession:
    """Return a client whose cookie jar holds an authenticated owner session."""
    mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    mocker.patch.object(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    mocker.patch.object(admin_auth.settings, "OWNER_XID", 42)
    login_resp = await client.get("/admin/login", allow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["Location"]).query)["state"][0]
    mocker.patch(
        "spellbot.web.api.admin_auth.httpx.AsyncClient",
        return_value=make_owner_httpx_client(),
    )
    cb = await client.get(
        f"/admin/oauth/callback?code=abc&state={state}",
        allow_redirects=False,
    )
    assert cb.status == 302
    return client


@pytest.mark.asyncio
class TestWebGuildPromote:
    async def test_owner_sees_controls_when_promote_enabled(
        self,
        owner_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild", promote=True)
        resp = await owner_client.get(f"/g/{guild.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert "Owner Controls" in text
        assert "<strong>enabled</strong>" in text
        assert "Disable promotion" in text
        assert 'name="promote" value="false"' in text

    async def test_owner_sees_controls_when_promote_disabled(
        self,
        owner_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=202, name="guild", promote=False)
        resp = await owner_client.get(f"/g/{guild.xid}")
        text = await resp.text()
        assert "Enable promotion" in text
        assert 'name="promote" value="true"' in text

    async def test_owner_can_disable_promotion(
        self,
        owner_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=203, name="guild", promote=True)
        resp = await owner_client.post(
            f"/g/{guild.xid}/promote",
            data={"promote": "false"},
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == f"/g/{guild.xid}"
        # The change is persisted: re-rendering shows the disabled state.
        follow = await owner_client.get(f"/g/{guild.xid}")
        assert "<strong>disabled</strong>" in await follow.text()

    async def test_owner_can_enable_promotion(
        self,
        owner_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=204, name="guild", promote=False)
        resp = await owner_client.post(
            f"/g/{guild.xid}/promote",
            data={"promote": "true"},
            allow_redirects=False,
        )
        assert resp.status == 302
        follow = await owner_client.get(f"/g/{guild.xid}")
        assert "<strong>enabled</strong>" in await follow.text()

    async def test_non_owner_cannot_post(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=205, name="guild", promote=True)
        resp = await client.post(
            f"/g/{guild.xid}/promote",
            data={"promote": "false"},
            allow_redirects=False,
        )
        assert resp.status == 403
        # The flag is untouched.
        follow = await client.get(f"/g/{guild.xid}")
        assert "Owner Controls" not in await follow.text()

    async def test_invalid_guild_id_is_404(
        self,
        owner_client: ClientSession,
    ) -> None:
        resp = await owner_client.post(
            "/g/abc/promote",
            data={"promote": "false"},
            allow_redirects=False,
        )
        assert resp.status == 404


@pytest_asyncio.fixture
async def mod_client(owner_client: ClientSession, mocker: MockerFixture) -> ClientSession:
    """Return a logged-in client whose viewer moderates every guild."""
    mocker.patch(
        "spellbot.web.api.record.viewer_is_moderator",
        AsyncMock(return_value=True),
    )
    return owner_client


@pytest.mark.asyncio
class TestWebGuildSettings:
    async def test_panel_hidden_for_anonymous(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=701, name="guild")
        resp = await client.get(f"/g/{guild.xid}")
        text = await resp.text()
        assert "Server Settings" not in text
        # Anonymous visitors are offered a login button that returns to this page.
        assert "Log in with Discord" in text
        assert f"/queues/login?next=%2Fg%2F{guild.xid}" in text

    async def test_panel_hidden_for_non_moderator(
        self,
        owner_client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.web.api.record.viewer_is_moderator",
            AsyncMock(return_value=False),
        )
        guild = factories.guild.create(xid=702, name="guild")
        resp = await owner_client.get(f"/g/{guild.xid}")
        text = await resp.text()
        assert "Server Settings" not in text
        # Already-authenticated viewers are not shown the login prompt.
        assert "Log in with Discord" not in text

    async def test_panel_visible_for_moderator(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=703, name="guild", motd="hello world")
        resp = await mod_client.get(f"/g/{guild.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert "Server Settings" in text
        assert 'name="motd"' in text
        assert 'value="hello world"' in text
        assert "Log in with Discord" not in text
        # The column's doc (minus the marker) is shown as help text.
        assert "shown in all game posts on the server." in text
        assert "[web-editable]" not in text

    async def test_settings_update_persists(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(
            xid=704,
            name="guild",
            motd="old",
            show_links=False,
            voice_create=False,
        )
        resp = await mod_client.post(
            f"/g/{guild.xid}/settings",
            data={"motd": "new message", "show_links": "true"},
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == f"/g/{guild.xid}"
        updated = (
            await DatabaseSession.execute(select(Guild).where(Guild.xid == guild.xid))
        ).scalar_one()
        assert updated.motd == "new message"
        assert updated.show_links is True
        # Unchecked boolean fields are written as False.
        assert updated.voice_create is False

    async def test_settings_ignores_unlisted_fields(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=705, name="guild", banned=False, promote=True)
        resp = await mod_client.post(
            f"/g/{guild.xid}/settings",
            data={"motd": "x", "banned": "true", "promote": "false"},
            allow_redirects=False,
        )
        assert resp.status == 302
        updated = (
            await DatabaseSession.execute(select(Guild).where(Guild.xid == guild.xid))
        ).scalar_one()
        # Protected columns are not writable through the settings form.
        assert updated.banned is False
        assert updated.promote is True

    async def test_anonymous_cannot_post(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=706, name="guild", motd="keep")
        resp = await client.post(
            f"/g/{guild.xid}/settings",
            data={"motd": "hacked"},
            allow_redirects=False,
        )
        assert resp.status == 403
        updated = (
            await DatabaseSession.execute(select(Guild).where(Guild.xid == guild.xid))
        ).scalar_one()
        assert updated.motd == "keep"

    async def test_non_moderator_cannot_post(
        self,
        owner_client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.web.api.record.viewer_is_moderator",
            AsyncMock(return_value=False),
        )
        guild = factories.guild.create(xid=707, name="guild", motd="keep")
        resp = await owner_client.post(
            f"/g/{guild.xid}/settings",
            data={"motd": "hacked"},
            allow_redirects=False,
        )
        assert resp.status == 403

    async def test_invalid_guild_id_is_404(
        self,
        mod_client: ClientSession,
    ) -> None:
        resp = await mod_client.post(
            "/g/abc/settings",
            data={"motd": "x"},
            allow_redirects=False,
        )
        assert resp.status == 404


@pytest.mark.asyncio
class TestWebChannelSettings:
    async def test_panel_hidden_for_anonymous(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=711, name="guild")
        channel = factories.channel.create(xid=811, name="channel", guild=guild)
        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        text = await resp.text()
        assert "Channel Settings" not in text
        # Anonymous visitors are offered a login button that returns to this page.
        assert "Log in with Discord" in text
        assert f"/queues/login?next=%2Fg%2F{guild.xid}%2Fc%2F{channel.xid}" in text

    async def test_panel_visible_for_moderator(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=712, name="guild")
        channel = factories.channel.create(xid=812, name="channel", guild=guild)
        resp = await mod_client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert "Channel Settings" in text
        assert 'name="default_format"' in text
        assert 'name="default_seats"' in text
        assert "Log in with Discord" not in text
        # The column's doc (minus the marker) is shown as help text.
        assert "The default commander bracket for this channel" in text
        assert "[web-editable]" not in text

    async def test_settings_update_persists(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=713, name="guild")
        channel = factories.channel.create(
            xid=813,
            name="channel",
            guild=guild,
            default_seats=4,
            default_format=GameFormat.COMMANDER.value,
            auto_verify=False,
        )
        resp = await mod_client.post(
            f"/g/{guild.xid}/c/{channel.xid}/settings",
            data={
                "default_seats": "2",
                "default_format": str(GameFormat.MODERN.value),
                "default_bracket": str(GameBracket.BRACKET_1.value),
                "motd": "channel motd",
                "auto_verify": "true",
            },
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == f"/g/{guild.xid}/c/{channel.xid}"
        updated = (
            await DatabaseSession.execute(select(Channel).where(Channel.xid == channel.xid))
        ).scalar_one()
        assert updated.default_seats == 2
        assert updated.default_format == GameFormat.MODERN.value
        assert updated.default_bracket == GameBracket.BRACKET_1.value
        assert updated.motd == "channel motd"
        assert updated.auto_verify is True

    async def test_settings_update_to_mode(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=716, name="guild")
        channel = factories.channel.create(xid=816, name="channel", guild=guild, to_mode=False)

        # Enabling tournament organizer mode round-trips through the settings form.
        resp = await mod_client.post(
            f"/g/{guild.xid}/c/{channel.xid}/settings",
            data={"to_mode": "true"},
            allow_redirects=False,
        )
        assert resp.status == 302
        updated = (
            await DatabaseSession.execute(select(Channel).where(Channel.xid == channel.xid))
        ).scalar_one()
        assert updated.to_mode is True

        # Omitting the checkbox disables it again.
        resp = await mod_client.post(
            f"/g/{guild.xid}/c/{channel.xid}/settings",
            data={"motd": "x"},
            allow_redirects=False,
        )
        assert resp.status == 302
        DatabaseSession.expire_all()
        updated = (
            await DatabaseSession.execute(select(Channel).where(Channel.xid == channel.xid))
        ).scalar_one()
        assert updated.to_mode is False

    async def test_settings_rejects_invalid_enum(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=714, name="guild")
        channel = factories.channel.create(
            xid=814,
            name="channel",
            guild=guild,
            default_format=GameFormat.COMMANDER.value,
            default_seats=4,
        )
        resp = await mod_client.post(
            f"/g/{guild.xid}/c/{channel.xid}/settings",
            data={"default_format": "99999", "default_seats": "100"},
            allow_redirects=False,
        )
        assert resp.status == 302
        updated = (
            await DatabaseSession.execute(select(Channel).where(Channel.xid == channel.xid))
        ).scalar_one()
        # Out-of-range values are ignored, leaving the originals intact.
        assert updated.default_format == GameFormat.COMMANDER.value
        assert updated.default_seats == 4

    async def test_anonymous_cannot_post(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=715, name="guild")
        channel = factories.channel.create(
            xid=815,
            name="channel",
            guild=guild,
            motd="keep",
        )
        resp = await client.post(
            f"/g/{guild.xid}/c/{channel.xid}/settings",
            data={"motd": "hacked"},
            allow_redirects=False,
        )
        assert resp.status == 403
        updated = (
            await DatabaseSession.execute(select(Channel).where(Channel.xid == channel.xid))
        ).scalar_one()
        assert updated.motd == "keep"

    async def test_invalid_ids_is_404(
        self,
        mod_client: ClientSession,
    ) -> None:
        resp = await mod_client.post(
            "/g/abc/c/xyz/settings",
            data={"motd": "x"},
            allow_redirects=False,
        )
        assert resp.status == 404


class TestFormChoice:
    def test_missing_returns_none(self) -> None:
        assert record.form_choice({}, "default_seats", record.VALID_SEATS) is None

    def test_non_numeric_returns_none(self) -> None:
        # A value that cannot be coerced to int must be treated as absent, not raise.
        form = {"default_seats": "lots"}
        assert record.form_choice(form, "default_seats", record.VALID_SEATS) is None

    def test_out_of_range_returns_none(self) -> None:
        form = {"default_seats": "99"}
        assert record.form_choice(form, "default_seats", record.VALID_SEATS) is None

    def test_valid_value_is_returned(self) -> None:
        form = {"default_seats": "4"}
        assert record.form_choice(form, "default_seats", record.VALID_SEATS) == 4


class TestParseChannelSettings:
    def test_valid_default_service_is_included(self) -> None:
        service = next(iter(record.VALID_SERVICES))
        values = record.parse_channel_settings({"default_service": str(service)})
        assert values["default_service"] == service

    def test_invalid_default_service_is_omitted(self) -> None:
        values = record.parse_channel_settings({"default_service": "99999"})
        assert "default_service" not in values
