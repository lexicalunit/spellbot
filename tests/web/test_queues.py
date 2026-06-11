from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Guild
from spellbot.services import alerts
from spellbot.web.api import admin_auth
from spellbot.web.api import queues as queues_endpoint_mod
from spellbot.web.api.queues import SPELLBOT_DEFAULT_LOGO, format_wait, language_name

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.test_utils import TestClient
    from freezegun.api import FrozenDateTimeFactory
    from pytest_mock import MockerFixture

    from tests.fixtures import Factories

    WebClient = TestClient[web.Request, web.Application]

pytestmark = pytest.mark.use_db

NOW = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clear_icon_fetch_throttle() -> None:
    queues_endpoint_mod._icon_fetch_attempts.clear()


class TestFormatWait:
    def test_sub_minute(self) -> None:
        assert format_wait(0) == "<1m"
        assert format_wait(59) == "<1m"

    def test_minutes_only(self) -> None:
        assert format_wait(60) == "1m"
        assert format_wait(59 * 60) == "59m"

    def test_whole_hours(self) -> None:
        assert format_wait(60 * 60) == "1h"
        assert format_wait(2 * 60 * 60) == "2h"

    def test_hours_and_minutes(self) -> None:
        assert format_wait(60 * 60 + 125) == "1h 2m"
        assert format_wait(3 * 60 * 60 + 45 * 60) == "3h 45m"


class TestLanguageName:
    def test_known_locales(self) -> None:
        assert language_name("en") == "English"
        assert language_name("ja") == "Japanese"
        assert language_name("es-ES") == "Spanish"

    def test_unknown_locale_returns_code(self) -> None:
        assert language_name("xx") == "xx"

    def test_none_defaults_to_english(self) -> None:
        assert language_name(None) == "English"
        assert language_name("") == "English"


@pytest.mark.asyncio
class TestQueuesEndpoint:
    async def test_renders_empty_state(self, client: WebClient) -> None:
        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert "No active queues right now" in body
        assert "Active Queues" in body
        # The Active Games stat lives in the page header and always renders.
        assert "Active Games" in body
        assert '<span class="page-header__stat-value">0</span>' in body

    async def test_renders_cards_for_pending_queues(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        icon = "https://cdn.discordapp.com/icons/980001/cached.png"
        guild = factories.guild.create(
            xid=980001,
            name="Gallery Guild",
            locale="en",
            icon=icon,
        )
        ch = factories.channel.create(xid=980101, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880001, name="u1")
        u2 = factories.user.create(xid=880002, name="u2")
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=8),
            seats=4,
        )
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.post.create(
            guild=guild,
            channel=ch,
            game=game,
            message_xid=999999,
        )

        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert "Gallery Guild" in body
        assert "English" in body
        assert "2 / 4" in body
        assert "8m" in body
        assert f"https://discord.com/channels/{guild.xid}/{ch.xid}/999999" in body
        assert icon in body
        # Player and channel names must not leak into the public template.
        assert u1.name not in body
        assert u2.name not in body
        assert ch.name not in body

    async def test_backfills_icon_from_discord_when_missing(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=980002, name="No Icon Guild", icon=None)
        ch = factories.channel.create(xid=980102, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880003, name="u1")
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW,
        )
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)

        fetched = "https://cdn.discordapp.com/icons/980002/fetched.png"
        with patch(
            "spellbot.services.guilds.fetch_icon_url",
            new=AsyncMock(return_value=fetched),
        ) as mock_fetch:
            resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert fetched in body
        mock_fetch.assert_awaited_once_with(guild.xid)
        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.icon == fetched

    async def test_falls_back_to_default_logo_when_discord_returns_no_icon(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=980003, name="Iconless Guild", icon=None)
        ch = factories.channel.create(xid=980103, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880004, name="u1")
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW,
        )
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)

        with patch(
            "spellbot.services.guilds.fetch_icon_url",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert SPELLBOT_DEFAULT_LOGO in body

    async def test_renders_filter_options_and_orders_shortest_wait_first(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        icon = "https://cdn.discordapp.com/icons/980004/abc.png"
        guild = factories.guild.create(xid=980004, name="Filter Guild", icon=icon, locale="en")
        ja_icon = "https://cdn.discordapp.com/icons/980014/abc.png"
        ja_guild = factories.guild.create(xid=980014, name="JA Guild", icon=ja_icon, locale="ja")
        ch = factories.channel.create(xid=980104, name="lfg", guild=guild)
        ja_ch = factories.channel.create(xid=980114, name="lfg-ja", guild=ja_guild)
        u1 = factories.user.create(xid=880005, name="u1")
        u2 = factories.user.create(xid=880006, name="u2")
        u3 = factories.user.create(xid=880016, name="u3")
        old_game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=30),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_3.value,
        )
        new_game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=2),
            format=GameFormat.MODERN.value,
            bracket=GameBracket.NONE.value,
        )
        ja_game = factories.game.create(
            guild=ja_guild,
            channel=ja_ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
        )
        factories.queue.create(user_xid=u1.xid, game_id=old_game.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=new_game.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u3.xid, game_id=ja_game.id, og_guild_xid=ja_guild.xid)

        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert 'id="filter-format"' in body
        assert 'id="filter-bracket"' in body
        assert 'id="filter-language"' in body
        assert f'data-format="{GameFormat.COMMANDER}"' in body
        assert f'data-format="{GameFormat.MODERN}"' in body
        assert f'data-bracket="{GameBracket.BRACKET_3}"' in body
        assert 'data-language="English"' in body
        assert 'data-language="Japanese"' in body
        # Both languages appear as <option>s in the language filter.
        assert '<option value="English">English</option>' in body
        assert '<option value="Japanese">Japanese</option>' in body
        # A copy button is rendered for each card carrying the guild_xid as its payload.
        assert 'class="queue-card__copy"' in body
        assert 'data-copy="980004"' in body
        assert 'data-copy="980014"' in body
        # Shortest wait first: the newer (Modern) card precedes the older (Commander) card.
        assert body.index(f'data-format="{GameFormat.MODERN}"') < body.index(
            f'data-format="{GameFormat.COMMANDER}"',
        )

    async def test_throttles_repeated_icon_fetch_attempts(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=980005, name="Retry Guild", icon=None)
        ch = factories.channel.create(xid=980105, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880007, name="u1")
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW,
        )
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)

        mock = AsyncMock(return_value=None)
        with patch("spellbot.services.guilds.fetch_icon_url", new=mock):
            assert (await client.get("/queues")).status == 200
            assert (await client.get("/queues")).status == 200
            assert mock.await_count == 1
            freezer.move_to(NOW + queues_endpoint_mod.ICON_FETCH_TTL)
            assert (await client.get("/queues")).status == 200
            assert mock.await_count == 2

    async def test_renders_inline_active_games_stat(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        icon = "https://cdn.discordapp.com/icons/980006/stats.png"
        guild = factories.guild.create(xid=980006, name="Stats Guild", icon=icon)
        ch = factories.channel.create(xid=980106, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880008, name="u1")
        # One pending game with a queued player: should be counted.
        game = factories.game.create(guild=guild, channel=ch, started_at=None)
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)
        # One game started within the 2h window: should be counted.
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(minutes=30),
        )

        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert "Active Games" in body
        assert '<span class="page-header__stat-value">2</span>' in body

    async def test_renders_started_game_cards(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(
            xid=980501,
            name="Started Guild",
            icon="https://cdn.discordapp.com/icons/980501/s.png",
            locale="en",
        )
        ch = factories.channel.create(xid=980511, name="lfg", guild=guild)
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(minutes=15),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_3.value,
            service=GameService.CONVOKE.value,
            seats=4,
        )
        # A stale started game (outside the 2h window) must not appear.
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(hours=3),
        )

        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        # The empty-state copy must not render when only started games exist.
        assert "No active queues right now" not in body
        # Started card markers.
        assert "queue-card--started" in body
        assert "Jump to Channel" in body
        assert "15m ago" in body
        assert f"https://discord.com/channels/{guild.xid}/{ch.xid}" in body
        # Started section divider renders above the started gallery.
        assert "gallery-divider" in body
        assert "Recently Started" in body
        # Filter bar should also render since started games exist.
        assert 'id="filter-format"' in body
        # Stat counts only the in-window started game.
        assert '<span class="page-header__stat-value">1</span>' in body

    async def test_started_games_render_after_queues_in_separate_sections(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(
            xid=980601,
            name="Mixed Guild",
            icon="https://cdn.discordapp.com/icons/980601/m.png",
        )
        ch = factories.channel.create(xid=980611, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880601, name="u1")
        pending = factories.game.create(guild=guild, channel=ch, started_at=None)
        factories.queue.create(user_xid=u1.xid, game_id=pending.id, og_guild_xid=guild.xid)
        factories.game.create(guild=guild, channel=ch, started_at=NOW - timedelta(minutes=10))

        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        # Two separate gallery sections render, with the divider between them,
        # so started cards are guaranteed to appear after queue cards in DOM order.
        first_gallery = body.find('<section class="gallery">')
        divider = body.find('class="gallery-divider"')
        started_gallery = body.find('class="gallery gallery--started"')
        assert -1 < first_gallery < divider < started_gallery

    async def test_renders_login_link_when_login_enabled_and_anonymous(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(queues_endpoint_mod.settings, "BOT_APPLICATION_ID", "appid-1")
        mocker.patch.object(queues_endpoint_mod.settings, "BOT_CLIENT_SECRET", "secret-1")
        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert 'href="/queues/login"' in body
        assert "Log in with Discord" in body

    async def test_my_filter_restricts_rows_and_count(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(NOW)
        mine = factories.guild.create(
            xid=980201,
            name="Mine",
            icon="https://cdn.discordapp.com/icons/980201/m.png",
        )
        theirs = factories.guild.create(
            xid=980202,
            name="Theirs",
            icon="https://cdn.discordapp.com/icons/980202/t.png",
        )
        ch1 = factories.channel.create(xid=980211, name="lfg", guild=mine)
        ch2 = factories.channel.create(xid=980212, name="lfg", guild=theirs)
        me = factories.user.create(xid=880201, name="me")
        other = factories.user.create(xid=880202, name="other")
        factories.guild_member.create(user_xid=me.xid, guild_xid=mine.xid)
        my_game = factories.game.create(guild=mine, channel=ch1, started_at=None)
        their_game = factories.game.create(guild=theirs, channel=ch2, started_at=None)
        factories.queue.create(user_xid=me.xid, game_id=my_game.id, og_guild_xid=mine.xid)
        factories.queue.create(user_xid=other.xid, game_id=their_game.id, og_guild_xid=theirs.xid)
        # A started game in `theirs` should be excluded from the stat when ?my=1.
        factories.game.create(guild=theirs, channel=ch2, started_at=NOW - timedelta(minutes=20))
        # A started game in `mine` should still count.
        factories.game.create(guild=mine, channel=ch1, started_at=NOW - timedelta(minutes=10))

        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )
        resp = await client.get("/queues?my=1")
        body = await resp.text()
        assert "Mine" in body
        assert "Theirs" not in body
        # Stat counts both the pending and started games in `Mine`.
        assert '<span class="page-header__stat-value">2</span>' in body
        assert 'id="filter-mine"' in body
        assert "checked" in body
        assert "Logged in as" in body

    async def test_my_param_ignored_when_no_viewer_session(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(
            xid=980301,
            name="Anon Guild",
            icon="https://cdn.discordapp.com/icons/980301/a.png",
        )
        ch = factories.channel.create(xid=980311, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880301, name="u1")
        game = factories.game.create(guild=guild, channel=ch, started_at=None)
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)

        resp = await client.get("/queues?my=1")
        body = await resp.text()
        # Anonymous: the filter is ignored, rows still render.
        assert "Anon Guild" in body
        assert 'id="filter-mine"' not in body

    async def test_logged_in_with_no_matches_shows_friendly_empty(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        me = factories.user.create(xid=880401, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )
        resp = await client.get("/queues?my=1")
        body = await resp.text()
        assert "servers you've played in" in body
        assert "Uncheck the filter" in body


@pytest.mark.asyncio
class TestQueuesJsonEndpoint:
    async def test_empty_returns_zero_stats_and_no_queues(self, client: WebClient) -> None:
        resp = await client.get("/queues.json")
        assert resp.status == 200
        assert resp.content_type == "application/json"
        payload = await resp.json()
        assert payload == {"stats": {"active_games": 0}, "queues": [], "games": []}

    async def test_returns_queue_rows_with_expected_fields(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        icon = "https://cdn.discordapp.com/icons/980501/abc.png"
        guild = factories.guild.create(
            xid=980501,
            name="JSON Guild",
            icon=icon,
            locale="ja",
        )
        ch = factories.channel.create(xid=980511, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880501, name="u1")
        u2 = factories.user.create(xid=880502, name="u2")
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=8),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_3.value,
            service=GameService.CONVOKE.value,
            seats=4,
        )
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.post.create(guild=guild, channel=ch, game=game, message_xid=987654)
        # One game started within the 2h window powers the active_games stat
        # and appears in the games list.
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(minutes=30),
            format=GameFormat.MODERN.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
            seats=2,
        )

        resp = await client.get("/queues.json")
        assert resp.status == 200
        payload = await resp.json()
        assert payload["stats"] == {"active_games": 2}
        assert len(payload["queues"]) == 1
        assert payload["queues"][0] == {
            "guild_xid": guild.xid,
            "guild_name": "JSON Guild",
            "guild_locale": "ja",
            "logo": icon,
            "format": str(GameFormat.COMMANDER),
            "bracket": str(GameBracket.BRACKET_3),
            "service": GameService.CONVOKE.title,
            "players": 2,
            "seats": 4,
            "wait_seconds": 8 * 60,
            "jump_url": f"https://discord.com/channels/{guild.xid}/{ch.xid}/987654",
        }
        assert len(payload["games"]) == 1
        assert payload["games"][0] == {
            "guild_xid": guild.xid,
            "guild_name": "JSON Guild",
            "guild_locale": "ja",
            "logo": icon,
            "format": str(GameFormat.MODERN),
            "bracket": str(GameBracket.NONE),
            "service": GameService.CONVOKE.title,
            "seats": 2,
            "started_seconds_ago": 30 * 60,
            "jump_url": f"https://discord.com/channels/{guild.xid}/{ch.xid}",
        }

    async def test_mythic_track_param_filters_queues_and_stats(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        on_guild = factories.guild.create(
            xid=980601,
            name="MT On Guild",
            icon="https://cdn.discordapp.com/icons/980601/a.png",
            enable_mythic_track=True,
        )
        off_guild = factories.guild.create(
            xid=980602,
            name="MT Off Guild",
            icon="https://cdn.discordapp.com/icons/980602/b.png",
            enable_mythic_track=False,
        )
        ch1 = factories.channel.create(xid=980611, name="lfg", guild=on_guild)
        ch2 = factories.channel.create(xid=980612, name="lfg", guild=off_guild)
        u1 = factories.user.create(xid=880601, name="u1")
        u2 = factories.user.create(xid=880602, name="u2")
        on_game = factories.game.create(guild=on_guild, channel=ch1, started_at=None)
        off_game = factories.game.create(guild=off_guild, channel=ch2, started_at=None)
        factories.queue.create(user_xid=u1.xid, game_id=on_game.id, og_guild_xid=on_guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=off_game.id, og_guild_xid=off_guild.xid)
        # Started recently in each guild — only the mythic-track one should be counted.
        factories.game.create(guild=on_guild, channel=ch1, started_at=NOW - timedelta(minutes=10))
        factories.game.create(guild=off_guild, channel=ch2, started_at=NOW - timedelta(minutes=10))

        # Without the filter, both guilds appear and all four games (two pending,
        # two started) count toward the active_games stat.
        resp = await client.get("/queues.json")
        payload = await resp.json()
        assert payload["stats"] == {"active_games": 4}
        assert {q["guild_name"] for q in payload["queues"]} == {"MT On Guild", "MT Off Guild"}
        assert {g["guild_name"] for g in payload["games"]} == {"MT On Guild", "MT Off Guild"}

        # With ?mythic_track=1 only the enabled guild is included in the list, stat,
        # and games array (one pending plus one started).
        resp = await client.get("/queues.json?mythic_track=1")
        payload = await resp.json()
        assert payload["stats"] == {"active_games": 2}
        assert [q["guild_name"] for q in payload["queues"]] == ["MT On Guild"]
        assert [g["guild_name"] for g in payload["games"]] == ["MT On Guild"]

        # Any value other than "1" is ignored (both guilds still appear).
        resp = await client.get("/queues.json?mythic_track=true")
        payload = await resp.json()
        assert {q["guild_name"] for q in payload["queues"]} == {"MT On Guild", "MT Off Guild"}
        assert {g["guild_name"] for g in payload["games"]} == {"MT On Guild", "MT Off Guild"}

    async def test_falls_back_to_default_logo_when_icon_unavailable(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=980502, name="No Icon JSON", icon=None)
        ch = factories.channel.create(xid=980512, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880503, name="u1")
        game = factories.game.create(guild=guild, channel=ch, started_at=None)
        factories.queue.create(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid)

        with patch(
            "spellbot.services.guilds.fetch_icon_url",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.get("/queues.json")
        assert resp.status == 200
        payload = await resp.json()
        assert payload["queues"][0]["logo"] == SPELLBOT_DEFAULT_LOGO

    async def test_started_games_fall_back_to_default_logo(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=980503, name="No Icon Game", icon=None)
        ch = factories.channel.create(xid=980513, name="lfg", guild=guild)
        factories.game.create(guild=guild, channel=ch, started_at=NOW - timedelta(minutes=5))

        with patch(
            "spellbot.services.guilds.fetch_icon_url",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.get("/queues.json")
        assert resp.status == 200
        payload = await resp.json()
        assert payload["queues"] == []
        assert len(payload["games"]) == 1
        assert payload["games"][0]["logo"] == SPELLBOT_DEFAULT_LOGO


@pytest.mark.asyncio
class TestPlayedGuildsSection:
    async def test_section_renders_for_logged_in_viewer(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(
            xid=981_001,
            name="Played Guild",
            icon="https://cdn.discordapp.com/icons/981001/p.png",
        )
        ch = factories.channel.create(xid=981_101, name="lfg", guild=guild)
        me = factories.user.create(xid=881_001, name="me")
        game = factories.game.create(guild=guild, channel=ch)
        factories.play.create(
            user_xid=me.xid,
            game_id=game.id,
            og_guild_xid=guild.xid,
            created_at=NOW - timedelta(days=3),
        )
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get("/queues")
        body = await resp.text()
        assert "Your Servers" in body
        assert 'class="played-list__row"' in body
        assert "Played Guild" in body
        assert f'href="/queues/g/{guild.xid}"' in body
        assert 'class="played-list__action"' in body
        assert ">Notifications<" in body
        assert 'class="played-list__action played-list__action--on"' not in body
        assert "Setup notifications" in body
        assert "Manage notifications" not in body
        assert "Notify me" not in body
        assert "Games played" not in body
        assert "First Played" not in body
        assert 'class="players-badge"' not in body

    async def test_section_shows_on_indicator_when_notifications_active(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(
            xid=981_010,
            name="On Guild",
            icon="https://cdn.discordapp.com/icons/981010/p.png",
        )
        ch = factories.channel.create(xid=981_110, name="lfg", guild=guild)
        me = factories.user.create(xid=881_010, name="me")
        game = factories.game.create(guild=guild, channel=ch)
        factories.play.create(
            user_xid=me.xid,
            game_id=game.id,
            og_guild_xid=guild.xid,
            created_at=NOW - timedelta(days=2),
        )
        await alerts.upsert(guild.xid, me.xid, formats=[1])
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get("/queues")
        body = await resp.text()
        assert "On Guild" in body
        assert "played-list__action played-list__action--on" in body
        assert ">On<" in body
        assert "Manage notifications" in body

    async def test_section_hidden_for_anonymous_viewer(
        self,
        client: WebClient,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=981_002, name="Played Anon", icon="i.png")
        ch = factories.channel.create(xid=981_102, name="lfg", guild=guild)
        me = factories.user.create(xid=881_002, name="me")
        game = factories.game.create(guild=guild, channel=ch)
        factories.play.create(user_xid=me.xid, game_id=game.id, og_guild_xid=guild.xid)

        resp = await client.get("/queues")
        body = await resp.text()
        assert "Your Servers" not in body
        assert 'class="played-list__row"' not in body

    async def test_section_hidden_when_no_history(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        me = factories.user.create(xid=881_003, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )
        resp = await client.get("/queues")
        body = await resp.text()
        assert "Your Servers" not in body

    async def test_section_hides_guilds_last_played_over_a_year_ago(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(NOW)
        stale = factories.guild.create(xid=981_004, name="Stale Guild", icon="s.png")
        ch = factories.channel.create(xid=981_104, name="lfg", guild=stale)
        me = factories.user.create(xid=881_004, name="me")
        game = factories.game.create(guild=stale, channel=ch)
        factories.play.create(
            user_xid=me.xid,
            game_id=game.id,
            og_guild_xid=stale.xid,
            created_at=NOW - timedelta(days=400),
        )
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )
        resp = await client.get("/queues")
        body = await resp.text()
        assert "Your Servers" not in body
        assert "Stale Guild" not in body

    async def test_active_queues_divider_rendered_between_played_and_rows(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(NOW)
        played_guild = factories.guild.create(xid=981_005, name="Played", icon="p.png")
        played_ch = factories.channel.create(xid=981_105, name="lfg", guild=played_guild)
        active_guild = factories.guild.create(xid=981_006, name="Active", icon="a.png")
        active_ch = factories.channel.create(xid=981_106, name="lfg", guild=active_guild)
        me = factories.user.create(xid=881_006, name="me")
        other = factories.user.create(xid=881_007, name="other")
        played_game = factories.game.create(guild=played_guild, channel=played_ch)
        factories.play.create(
            user_xid=me.xid,
            game_id=played_game.id,
            og_guild_xid=played_guild.xid,
            created_at=NOW - timedelta(days=3),
        )
        active_game = factories.game.create(
            guild=active_guild,
            channel=active_ch,
            seats=4,
            started_at=None,
        )
        factories.post.create(
            guild=active_guild,
            channel=active_ch,
            game=active_game,
            message_xid=981_206,
        )
        factories.queue.create(
            user_xid=other.xid,
            game_id=active_game.id,
            og_guild_xid=active_guild.xid,
        )
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get("/queues")
        body = await resp.text()
        played_idx = body.index("Your Servers")
        divider_idx = body.index('aria-label="Active queues"')
        active_idx = body.index("Jump to Game")
        assert played_idx < divider_idx < active_idx


@pytest.mark.asyncio
class TestGuildNotifyEndpoint:
    async def test_renders_preferences_form_for_logged_in_viewer(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(
            xid=982_001,
            name="Notify Guild",
            icon="https://cdn.discordapp.com/icons/982001/n.png",
            locale="en",
        )
        me = factories.user.create(xid=882_001, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        assert "Notify Guild" in body
        assert "Notification Preferences" in body
        assert "Formats" in body
        assert "Brackets" in body
        assert f'action="/queues/g/{guild.xid}/notify"' in body
        assert "Save preferences" in body
        assert "Do not notify me about games on this server" in body
        # No alert exists yet, so the off toggle should be pre-checked.
        assert re.search(r'id="notify-off"[^>]*\bchecked\b', body)
        # The toast container is rendered but hidden until the form is submitted.
        assert 'id="notify-toast"' in body
        assert "Your notification preferences have been saved." in body
        assert 'class="notify__flash"' not in body

    async def test_redirects_to_login_when_anonymous(
        self,
        client: WebClient,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=982_003, name="Anon", icon="a.png")
        resp = await client.get(f"/queues/g/{guild.xid}", allow_redirects=False)
        assert resp.status == 302
        location = resp.headers["Location"]
        assert location.startswith("/queues/login")
        assert f"/queues/g/{guild.xid}" in location

    async def test_returns_404_for_unknown_guild(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(882_004, "Me")),
        )
        resp = await client.get("/queues/g/77777777", allow_redirects=False)
        assert resp.status == 404

    async def test_returns_404_for_non_integer_guild(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(882_005, "Me")),
        )
        resp = await client.get("/queues/g/not-a-number", allow_redirects=False)
        assert resp.status == 404

    async def test_returns_404_for_banned_guild(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=982_006, name="Banned", banned=True)
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(882_006, "Me")),
        )
        resp = await client.get(f"/queues/g/{guild.xid}", allow_redirects=False)
        assert resp.status == 404

    async def test_prepopulates_form_with_existing_preferences(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=982_007, name="Prepop", icon="p.png")
        me = factories.user.create(xid=882_007, name="me")
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=me.xid,
            preferences={"formats": [1], "brackets": [2]},
        )
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        assert re.search(r'name="formats"\s+value="1"\s+checked', body)
        assert re.search(r'name="brackets"\s+value="2"\s+checked', body)
        assert not re.search(r'name="formats"\s+value="2"\s+checked', body)
        assert not re.search(r'name="brackets"\s+value="1"\s+checked', body)
        # An alert row exists, so the off toggle should not be pre-checked.
        assert not re.search(r'id="notify-off"[^>]*\bchecked\b', body)

    async def test_prepopulates_form_from_soft_deleted_alert(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=982_008, name="Restore", icon="r.png")
        me = factories.user.create(xid=882_008, name="me")
        await alerts.upsert(guild.xid, me.xid, formats=[1], brackets=[2])
        await alerts.delete(guild.xid, me.xid)
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        # Prior preferences are still surfaced so the user can restore them by
        # simply unchecking the off toggle and saving.
        assert re.search(r'name="formats"\s+value="1"\s+checked', body)
        assert re.search(r'name="brackets"\s+value="2"\s+checked', body)
        # The off toggle is pre-checked because the alert is currently disabled.
        assert re.search(r'id="notify-off"[^>]*\bchecked\b', body)


@pytest.mark.asyncio
class TestGuildNotifySaveEndpoint:
    async def test_redirects_back_to_preferences_page_and_persists(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_001, name="Save Guild", icon="s.png")
        me = factories.user.create(xid=883_001, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"formats": ["1"], "brackets": ["2"]},
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == f"/queues/g/{guild.xid}"

        saved = await alerts.get_for_user_guild(guild.xid, me.xid)
        assert saved is not None
        assert saved.formats == [1]
        assert saved.brackets == [2]

    async def test_returns_json_for_ajax_request(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_010, name="Ajax Guild", icon="a.png")
        me = factories.user.create(xid=883_010, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"formats": ["1", "1", "4"], "brackets": ["2"]},
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload == {
            "ok": True,
            "formats": [1, 4],
            "brackets": [2],
            "channels": [],
            "active_hours": None,
        }

    async def test_returns_400_for_invalid_format_value(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_011, name="Bad Guild", icon="b.png")
        me = factories.user.create(xid=883_011, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"formats": ["not-a-number"], "brackets": []},
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 400
        payload = await resp.json()
        assert payload == {"ok": False, "error": "invalid_input"}

    async def test_returns_400_for_unknown_format_value(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_012, name="Unk Guild", icon="u.png")
        me = factories.user.create(xid=883_012, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"formats": ["9999"], "brackets": []},
            allow_redirects=False,
        )
        assert resp.status == 400

    async def test_redirects_to_login_when_anonymous(
        self,
        client: WebClient,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=983_002, name="Anon Save", icon="a.png")
        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={},
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"].startswith("/queues/login")

    async def test_returns_404_for_non_integer_guild(
        self,
        client: WebClient,
    ) -> None:
        resp = await client.post(
            "/queues/g/not-a-number/notify",
            data={},
            allow_redirects=False,
        )
        assert resp.status == 404

    async def test_off_flag_deletes_existing_alert_and_redirects(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_020, name="Off Guild", icon="d.png")
        me = factories.user.create(xid=883_020, name="me")
        await alerts.upsert(guild.xid, me.xid, formats=[1], brackets=[2])
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"off": "1", "formats": ["1"], "brackets": ["2"]},
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == f"/queues/g/{guild.xid}"
        assert await alerts.get_for_user_guild(guild.xid, me.xid) is None

    async def test_off_flag_returns_json_for_ajax_request(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_021, name="Off Ajax", icon="d.png")
        me = factories.user.create(xid=883_021, name="me")
        await alerts.upsert(guild.xid, me.xid, formats=[1])
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"off": "1"},
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 200
        assert await resp.json() == {"ok": True, "off": True}
        assert await alerts.get_for_user_guild(guild.xid, me.xid) is None

    async def test_off_flag_is_idempotent_when_no_alert_exists(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_022, name="Off Noop", icon="d.png")
        me = factories.user.create(xid=883_022, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"off": "1"},
            allow_redirects=False,
        )
        assert resp.status == 302
        assert await alerts.get_for_user_guild(guild.xid, me.xid) is None

    async def test_save_without_off_restores_soft_deleted_alert(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=983_023, name="Restore Save", icon="r.png")
        me = factories.user.create(xid=883_023, name="me")
        original = await alerts.upsert(guild.xid, me.xid, formats=[1], brackets=[2])
        await alerts.delete(guild.xid, me.xid)
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"formats": ["1"], "brackets": ["2"]},
            allow_redirects=False,
        )

        assert resp.status == 302
        assert resp.headers["Location"] == f"/queues/g/{guild.xid}"
        restored = await alerts.get_for_user_guild(guild.xid, me.xid)
        assert restored is not None
        assert restored.id == original.id
        assert restored.deleted_at is None
        assert restored.formats == [1]
        assert restored.brackets == [2]


@pytest.mark.asyncio
class TestGuildNotifyChannelsFieldset:
    async def test_channels_fieldset_hidden_when_no_played_channels(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=984_001, name="NoChans", icon="n.png")
        me = factories.user.create(xid=884_001, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        assert ">Channels<" not in body
        assert 'name="channels"' not in body

    async def test_channels_fieldset_hidden_with_single_played_channel(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=984_002, name="OneChan", icon="o.png")
        ch = factories.channel.create(xid=984_201, name="lfg", guild=guild)
        me = factories.user.create(xid=884_002, name="me")
        game = factories.game.create(guild=guild, channel=ch)
        factories.play.create(user_xid=me.xid, game_id=game.id, og_guild_xid=guild.xid)
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        assert ">Channels<" not in body
        assert 'name="channels"' not in body

    async def test_channels_fieldset_shown_with_multiple_played_channels(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=984_003, name="MultiChan", icon="m.png")
        ch_a = factories.channel.create(xid=984_301, name="alpha", guild=guild)
        ch_b = factories.channel.create(xid=984_302, name="bravo", guild=guild)
        me = factories.user.create(xid=884_003, name="me")
        game_a = factories.game.create(guild=guild, channel=ch_a)
        game_b = factories.game.create(guild=guild, channel=ch_b)
        factories.play.create(user_xid=me.xid, game_id=game_a.id, og_guild_xid=guild.xid)
        factories.play.create(user_xid=me.xid, game_id=game_b.id, og_guild_xid=guild.xid)
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=me.xid,
            preferences={"formats": [], "brackets": [], "channels": [ch_a.xid]},
        )
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        assert ">Channels<" in body
        assert "#alpha" in body
        assert "#bravo" in body
        assert re.search(
            rf'name="channels"\s+value="{ch_a.xid}"\s+checked',
            body,
        )
        assert not re.search(
            rf'name="channels"\s+value="{ch_b.xid}"\s+checked',
            body,
        )

    async def test_save_persists_channels_when_played(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=984_004, name="SaveChan", icon="c.png")
        ch_a = factories.channel.create(xid=984_401, name="alpha", guild=guild)
        ch_b = factories.channel.create(xid=984_402, name="bravo", guild=guild)
        me = factories.user.create(xid=884_004, name="me")
        game_a = factories.game.create(guild=guild, channel=ch_a)
        game_b = factories.game.create(guild=guild, channel=ch_b)
        factories.play.create(user_xid=me.xid, game_id=game_a.id, og_guild_xid=guild.xid)
        factories.play.create(user_xid=me.xid, game_id=game_b.id, og_guild_xid=guild.xid)
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data=[
                ("formats", "1"),
                ("brackets", "2"),
                ("channels", str(ch_a.xid)),
                ("channels", str(ch_b.xid)),
            ],
            allow_redirects=False,
        )
        assert resp.status == 302

        saved = await alerts.get_for_user_guild(guild.xid, me.xid)
        assert saved is not None
        assert saved.channels == sorted([ch_a.xid, ch_b.xid])

    async def test_save_returns_400_for_unplayed_channel(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=984_005, name="BadChan", icon="x.png")
        ch_a = factories.channel.create(xid=984_501, name="alpha", guild=guild)
        me = factories.user.create(xid=884_005, name="me")
        game_a = factories.game.create(guild=guild, channel=ch_a)
        factories.play.create(user_xid=me.xid, game_id=game_a.id, og_guild_xid=guild.xid)
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data=[("channels", "9999999")],
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 400
        payload = await resp.json()
        assert payload == {"ok": False, "error": "invalid_input"}

    async def test_channel_stale_for_over_a_year_is_excluded(
        self,
        client: WebClient,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=984_006, name="StaleGuild", icon="s.png")
        ch_fresh = factories.channel.create(xid=984_601, name="fresh", guild=guild)
        ch_stale = factories.channel.create(xid=984_602, name="stale", guild=guild)
        me = factories.user.create(xid=884_006, name="me")
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
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        # Only one fresh channel remains, so the fieldset is hidden entirely.
        assert ">Channels<" not in body
        assert "#stale" not in body

        # Posting a stale channel xid is rejected as invalid.
        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data=[("channels", str(ch_stale.xid))],
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 400


@pytest.mark.asyncio
class TestGuildNotifyActiveHours:
    async def test_get_renders_active_hours_controls(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=985_001, name="Hours Guild", icon="h.png")
        me = factories.user.create(xid=885_001, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        assert ">Active Hours<" in body
        assert 'name="active_hours_enabled"' in body
        assert 'name="active_hours_start"' in body
        assert 'name="active_hours_end"' in body
        assert 'name="active_hours_tz"' in body

    async def test_get_prefills_existing_active_hours(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=985_002, name="Pref Guild", icon="p.png")
        me = factories.user.create(xid=885_002, name="me")
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=me.xid,
            preferences={
                "formats": [],
                "brackets": [],
                "channels": [],
                "active_hours": {"start": 19, "end": 23, "tz": "America/New_York"},
            },
        )
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.get(f"/queues/g/{guild.xid}")
        assert resp.status == 200
        body = await resp.text()
        assert re.search(r'id="active-hours-enabled"[^>]*\bchecked\b', body)
        assert re.search(r'id="active-hours-start"[^>]*value="19"', body)
        assert re.search(r'id="active-hours-end"[^>]*value="23"', body)
        assert 'value="America/New_York"' in body

    async def test_post_saves_active_hours(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=985_010, name="Save Hours", icon="s.png")
        me = factories.user.create(xid=885_010, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={
                "active_hours_enabled": "1",
                "active_hours_start": "17",
                "active_hours_end": "22",
                "active_hours_tz": "America/Los_Angeles",
            },
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload["active_hours"] == {
            "start": 17,
            "end": 22,
            "tz": "America/Los_Angeles",
        }

        saved = await alerts.get_for_user_guild(guild.xid, me.xid)
        assert saved is not None
        assert saved.active_hours == {
            "start": 17,
            "end": 22,
            "tz": "America/Los_Angeles",
        }

    async def test_post_without_enabled_flag_omits_active_hours(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=985_011, name="No Hours", icon="n.png")
        me = factories.user.create(xid=885_011, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={"formats": ["1"]},
            allow_redirects=False,
        )
        assert resp.status == 302

        saved = await alerts.get_for_user_guild(guild.xid, me.xid)
        assert saved is not None
        assert saved.active_hours is None

    async def test_post_rejects_range_over_max(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=985_020, name="Wide Hours", icon="w.png")
        me = factories.user.create(xid=885_020, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={
                "active_hours_enabled": "1",
                "active_hours_start": "0",
                "active_hours_end": "12",
                "active_hours_tz": "UTC",
            },
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 400
        payload = await resp.json()
        assert payload["ok"] is False
        assert payload["error"] == "invalid_active_hours"

    async def test_post_rejects_invalid_timezone(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=985_021, name="Bad TZ", icon="b.png")
        me = factories.user.create(xid=885_021, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={
                "active_hours_enabled": "1",
                "active_hours_start": "17",
                "active_hours_end": "22",
                "active_hours_tz": "Mars/Olympus",
            },
            allow_redirects=False,
        )
        assert resp.status == 400

    async def test_post_rejects_equal_start_end(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=985_022, name="Equal Hours", icon="e.png")
        me = factories.user.create(xid=885_022, name="me")
        mocker.patch(
            "spellbot.web.api.queues.get_viewer",
            AsyncMock(return_value=(me.xid, "Me")),
        )

        resp = await client.post(
            f"/queues/g/{guild.xid}/notify",
            data={
                "active_hours_enabled": "1",
                "active_hours_start": "10",
                "active_hours_end": "10",
                "active_hours_tz": "UTC",
            },
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
        assert resp.status == 400


def make_admin_httpx_client() -> MagicMock:
    """Mock `httpx.AsyncClient` for an OAuth flow identifying the owner (xid=42)."""
    inner = MagicMock()
    token_resp = MagicMock(status_code=200)
    token_resp.json = MagicMock(return_value={"access_token": "tok"})
    inner.post = AsyncMock(return_value=token_resp)
    identify_resp = MagicMock(status_code=200)
    identify_resp.json = MagicMock(return_value={"id": "42", "username": "admin"})
    inner.get = AsyncMock(return_value=identify_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest_asyncio.fixture
async def admin_session_client(client: WebClient, mocker: MockerFixture) -> WebClient:
    """Return a client whose cookie jar holds an authenticated admin session."""
    mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    mocker.patch.object(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    mocker.patch.object(admin_auth.settings, "OWNER_XID", 42)
    login_resp = await client.get("/admin/login", allow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["Location"]).query)["state"][0]
    mocker.patch(
        "spellbot.web.api.admin_auth.httpx.AsyncClient",
        return_value=make_admin_httpx_client(),
    )
    cb = await client.get(
        f"/admin/oauth/callback?code=abc&state={state}",
        allow_redirects=False,
    )
    assert cb.status == 302
    return client


@pytest.mark.asyncio
class TestQueuesAdminLink:
    async def test_anonymous_visitor_has_no_admin_link(self, client: WebClient) -> None:
        resp = await client.get("/queues")
        body = await resp.text()
        # The class name appears in the inlined CSS; assert the link itself is absent.
        assert 'href="/admin/dashboard"' not in body
        assert ">Admin Dashboard</a>" not in body

    async def test_admin_session_shows_admin_link(
        self,
        admin_session_client: WebClient,
    ) -> None:
        resp = await admin_session_client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert 'class="page-header__admin" href="/admin/dashboard"' in body
        assert "Admin Dashboard" in body
