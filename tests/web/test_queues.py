from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat
from spellbot.models import Guild
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
        guild = factories.guild.create(xid=980004, name="Filter Guild", icon=icon)
        ch = factories.channel.create(xid=980104, name="lfg", guild=guild)
        u1 = factories.user.create(xid=880005, name="u1")
        u2 = factories.user.create(xid=880006, name="u2")
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
        factories.queue.create(user_xid=u1.xid, game_id=old_game.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=new_game.id, og_guild_xid=guild.xid)

        resp = await client.get("/queues")
        assert resp.status == 200
        body = await resp.text()
        assert 'id="filter-format"' in body
        assert 'id="filter-bracket"' in body
        assert f'data-format="{GameFormat.COMMANDER}"' in body
        assert f'data-format="{GameFormat.MODERN}"' in body
        assert f'data-bracket="{GameBracket.BRACKET_3}"' in body
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
        # One pending game so the filter bar renders.
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
        assert '<span class="page-header__stat-value">1</span>' in body

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
        # Stat counts only the started game in `Mine`.
        assert '<span class="page-header__stat-value">1</span>' in body
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
