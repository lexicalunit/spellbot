from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.services import dashboard
from spellbot.web.dashboard_filters import GuildFilter, PeriodSpec, parse_period

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db

Seed = dict[str, Any]

NOW = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)


def period_all() -> PeriodSpec:
    return PeriodSpec(period="all", start_dt=None, bucket="month")


def period_30d() -> PeriodSpec:
    return parse_period("30d")


def period_180d() -> PeriodSpec:
    return parse_period("180d")


def all_guilds() -> GuildFilter:
    return GuildFilter(mode="all", xid=None)


class TestHelpers:
    def test_game_guild_filter_all_returns_empty(self) -> None:
        assert dashboard.game_guild_filter(all_guilds()) == []

    def test_game_guild_filter_include(self) -> None:
        clauses = dashboard.game_guild_filter(GuildFilter(mode="include", xid=7))
        assert len(clauses) == 1

    def test_game_guild_filter_exclude(self) -> None:
        clauses = dashboard.game_guild_filter(GuildFilter(mode="exclude", xid=7))
        assert len(clauses) == 1

    def test_iso_str_none(self) -> None:
        assert dashboard.iso_str(None) == ""

    def test_iso_str_datetime(self) -> None:
        dt = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)
        assert dashboard.iso_str(dt) == dt.isoformat()

    def test_iso_str_scalar(self) -> None:
        assert dashboard.iso_str(42) == "42"


@pytest_asyncio.fixture
async def seed(
    factories: Factories,
    freezer: FrozenDateTimeFactory,
) -> Seed:
    """Seed a small but varied dataset spanning two guilds and several days."""
    freezer.move_to(NOW)
    g1 = factories.guild.create(xid=900001, name="Guild One")
    g2 = factories.guild.create(xid=900002, name="Guild Two")
    ch1 = factories.channel.create(xid=910001, name="ch1", guild=g1)
    ch2 = factories.channel.create(xid=910002, name="ch2", guild=g2)

    u1 = factories.user.create(xid=800001, name="alice", locale="en")
    u2 = factories.user.create(xid=800002, name="bob", locale="fr")
    u3 = factories.user.create(xid=800003, name="carol", locale="en")
    u4 = factories.user.create(xid=800004, name="dave", locale="es")

    def make_game(
        guild: object,
        channel: object,
        started_offset_hours: float,
        *,
        created_offset_extra_min: float = 10.0,
        fmt: int = GameFormat.COMMANDER.value,
        bracket: int = GameBracket.NONE.value,
        service: int = GameService.SPELLTABLE.value,
        seats: int = 4,
        rules: str | None = None,
        locale: str = "en",
        deleted: bool = False,
    ) -> Any:
        started = NOW - timedelta(hours=started_offset_hours)
        created = started - timedelta(minutes=created_offset_extra_min)
        return factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None if deleted else started,
            created_at=created,
            deleted_at=NOW if deleted else None,
            format=fmt,
            bracket=bracket,
            service=service,
            seats=seats,
            rules=rules,
            locale=locale,
        )

    # Guild 1 games: 3 started commander, 1 cEDH bracketed, 1 expired
    g1_games = [
        make_game(g1, ch1, 1.0, rules="no fast mana"),
        make_game(g1, ch1, 25.0, rules="no fast mana please"),
        make_game(g1, ch1, 50.0, bracket=GameBracket.BRACKET_3.value),
        make_game(g1, ch1, 5.0, fmt=GameFormat.CEDH.value, bracket=GameBracket.BRACKET_5.value),
        make_game(g1, ch1, 2.0, deleted=True),
    ]
    # Guild 2 games: different service / format / seats / locale
    g2_games = [
        make_game(g2, ch2, 3.0, service=GameService.CONVOKE.value, seats=2, locale="de"),
        make_game(g2, ch2, 12.0, fmt=GameFormat.MODERN.value, seats=2, locale="de"),
    ]

    for game in g1_games[:4]:
        factories.play.create(game_id=game.id, user_xid=u1.xid, og_guild_xid=g1.xid)
    for game in g1_games[:3]:
        factories.play.create(game_id=game.id, user_xid=u2.xid, og_guild_xid=g1.xid)
    factories.play.create(game_id=g1_games[0].id, user_xid=u3.xid, og_guild_xid=g1.xid)

    for game in g2_games:
        factories.play.create(game_id=game.id, user_xid=u3.xid, og_guild_xid=g2.xid)
        factories.play.create(game_id=game.id, user_xid=u4.xid, og_guild_xid=g2.xid)

    # Blocks: u2 blocks u1 (twice from different users), and u3 blocks u4
    factories.block.create(user_xid=u2.xid, blocked_user_xid=u1.xid)
    factories.block.create(user_xid=u3.xid, blocked_user_xid=u1.xid)
    factories.block.create(user_xid=u3.xid, blocked_user_xid=u4.xid)

    return {
        "g1": g1,
        "g2": g2,
        "users": [u1, u2, u3, u4],
        "g1_games": g1_games,
        "g2_games": g2_games,
    }


@pytest.mark.asyncio
class TestDashboardGuilds:
    async def test_orders_by_total_games(self, seed: Seed) -> None:
        g1 = seed["g1"]
        g2 = seed["g2"]
        rows = await dashboard.dashboard_guilds()
        names = [r["name"] for r in rows]
        assert names == [g1.name, g2.name]
        assert rows[0]["xid"] == str(int(g1.xid))
        assert rows[1]["xid"] == str(int(g2.xid))

    async def test_top_n_limits_result(self, seed: Seed) -> None:
        del seed
        rows = await dashboard.dashboard_guilds(top_n=1)
        assert len(rows) == 1

    async def test_excludes_guilds_with_no_games(self, factories: Factories) -> None:
        factories.guild.create(xid=900900, name="Empty")
        rows = await dashboard.dashboard_guilds()
        assert all(r["xid"] != "900900" for r in rows)


@pytest.mark.asyncio
class TestDashboardSummary:
    async def test_all_time_counts(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_summary(period_all(), all_guilds())
        # 4 started in g1 + 2 in g2 = 6 started games (deleted has no started_at).
        assert result["games"] == 6
        assert result["expired"] == 1
        assert result["fill_rate"] == pytest.approx(85.7, rel=0.01)
        assert result["players"] == 4
        assert result["servers"] >= 2
        assert result["period"] == "all"
        assert result["bucket"] == "month"
        assert sum(result["brackets"].values()) == 6

    async def test_guild_include_filter(self, seed: Seed) -> None:
        g1 = seed["g1"]
        opts = GuildFilter(mode="include", xid=int(g1.xid))
        result = await dashboard.dashboard_summary(period_all(), opts)
        assert result["games"] == 4
        assert result["expired"] == 1
        assert result["fill_rate"] == 80.0
        assert result["players"] == 3

    async def test_guild_exclude_filter(self, seed: Seed) -> None:
        g1 = seed["g1"]
        opts = GuildFilter(mode="exclude", xid=int(g1.xid))
        result = await dashboard.dashboard_summary(period_all(), opts)
        assert result["games"] == 2
        assert result["expired"] == 0
        assert result["fill_rate"] == 100.0
        assert result["players"] == 2

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_summary(period_30d(), all_guilds())
        assert result["games"] >= 1
        assert result["bucket"] == "day"

    async def test_fill_rate_zero_when_no_games(self, factories: Factories) -> None:
        del factories
        result = await dashboard.dashboard_summary(period_30d(), all_guilds())
        assert result["games"] == 0
        assert result["expired"] == 0
        assert result["fill_rate"] == 0.0


@pytest.mark.asyncio
class TestDashboardTotals:
    async def test_totals_ignore_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_totals(period_30d(), all_guilds())
        assert result["games"] == 6
        assert result["players"] == 4
        assert result["servers"] >= 2

    async def test_totals_honor_guild_filter(self, seed: Seed) -> None:
        g1 = seed["g1"]
        result = await dashboard.dashboard_totals(
            period_all(),
            GuildFilter(mode="include", xid=int(g1.xid)),
        )
        assert result["games"] == 4


@pytest.mark.asyncio
class TestDashboardUsersActivity:
    async def test_all_series_present(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_users_activity(period_all(), all_guilds())
        assert {"new_users", "dau", "wau", "mau", "dau_mau"} <= set(result)
        assert isinstance(result["dau_mau"], float)
        assert len(result["new_users"]) >= 1

    async def test_day_bucket_short_circuits(self, seed: Seed) -> None:
        # 30d period -> bucket "day", which means dau_daily reuses dau.
        del seed
        result = await dashboard.dashboard_users_activity(period_30d(), all_guilds())
        assert isinstance(result["dau"], list)
        assert isinstance(result["dau_mau"], float)

    async def test_week_bucket_branch(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_users_activity(period_180d(), all_guilds())
        assert isinstance(result["dau"], list)

    async def test_guild_filter_narrows_results(self, seed: Seed) -> None:
        g2 = seed["g2"]
        result = await dashboard.dashboard_users_activity(
            period_all(),
            GuildFilter(mode="include", xid=int(g2.xid)),
        )
        # Guild 2 only has u3 and u4 playing.
        new_total = sum(p["count"] for p in result["new_users"])
        assert new_total == 2


@pytest.mark.asyncio
class TestDashboardGames:
    async def test_started_and_expired_series(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_games(period_all(), all_guilds())
        assert sum(p["count"] for p in result["started"]) == 6
        assert sum(p["count"] for p in result["expired"]) == 1

    async def test_guild_filter(self, seed: Seed) -> None:
        g2 = seed["g2"]
        result = await dashboard.dashboard_games(
            period_all(),
            GuildFilter(mode="include", xid=int(g2.xid)),
        )
        assert sum(p["count"] for p in result["started"]) == 2
        assert sum(p["count"] for p in result["expired"]) == 0

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_games(period_30d(), all_guilds())
        assert isinstance(result["started"], list)


@pytest.mark.asyncio
class TestDashboardPlayerGrowth:
    async def test_cumulative_reaches_all_players(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_player_growth(period_all(), all_guilds())
        series = result["cumulative_players"]
        assert series, "expected at least one bucket"
        # 4 distinct players ever play across both guilds.
        assert series[-1]["count"] == 4
        # Series is monotonically non-decreasing.
        running = 0
        for row in series:
            assert row["count"] >= running
            running = row["count"]

    async def test_guild_filter(self, seed: Seed) -> None:
        g2 = seed["g2"]
        result = await dashboard.dashboard_player_growth(
            period_all(),
            GuildFilter(mode="include", xid=int(g2.xid)),
        )
        # Only u3 and u4 play in g2.
        assert result["cumulative_players"][-1]["count"] == 2

    async def test_bounded_period_returns_list(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_player_growth(period_30d(), all_guilds())
        assert isinstance(result["cumulative_players"], list)

    async def test_empty_when_no_plays(self, factories: Factories) -> None:
        del factories
        result = await dashboard.dashboard_player_growth(period_30d(), all_guilds())
        assert result["cumulative_players"] == []


@pytest.mark.asyncio
class TestDashboardCasualVsCedh:
    async def test_cedh_by_curated_guild_id(
        self,
        factories: Factories,
        seed: Seed,
    ) -> None:
        del seed
        # 113555415446413312 is in CEDH_GUILDS; name intentionally avoids "cedh"
        # so the classification is driven solely by the guild id.
        cedh_guild = factories.guild.create(xid=113555415446413312, name="Comp Server")
        ch = factories.channel.create(xid=910101, name="a", guild=cedh_guild)
        factories.game.create(
            guild=cedh_guild,
            channel=ch,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=2),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
        )
        result = await dashboard.dashboard_casual_vs_cedh(
            period_all(),
            GuildFilter(mode="include", xid=int(cedh_guild.xid)),
        )
        assert sum(p["count"] for p in result["cedh"]) == 1
        assert result["casual"] == []

    async def test_cedh_by_guild_name_contains_cedh(
        self,
        factories: Factories,
        seed: Seed,
    ) -> None:
        del seed
        # Guild id is not in CEDH_GUILDS, but its name contains "cedh" (case
        # insensitive); every game on it is therefore cEDH.
        guild = factories.guild.create(xid=900111, name="The cEDH Lounge")
        ch = factories.channel.create(xid=910111, name="a", guild=guild)
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=2),
            format=GameFormat.MODERN.value,
            bracket=GameBracket.NONE.value,
        )
        result = await dashboard.dashboard_casual_vs_cedh(
            period_all(),
            GuildFilter(mode="include", xid=int(guild.xid)),
        )
        assert sum(p["count"] for p in result["cedh"]) == 1
        assert result["casual"] == []

    async def test_cedh_by_format_and_bracket(
        self,
        factories: Factories,
        seed: Seed,
    ) -> None:
        del seed
        guild = factories.guild.create(xid=900112, name="Mixed Server")
        ch = factories.channel.create(xid=910112, name="a", guild=guild)
        # Three cEDH-qualifying games (format CEDH, format EDH_MAX, bracket 5)
        # and one casual game on the same non-curated, non-cedh-named server.
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=2),
            format=GameFormat.CEDH.value,
            bracket=GameBracket.NONE.value,
        )
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(hours=3),
            created_at=NOW - timedelta(hours=4),
            format=GameFormat.EDH_MAX.value,
            bracket=GameBracket.NONE.value,
        )
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(hours=5),
            created_at=NOW - timedelta(hours=6),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_5.value,
        )
        factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(hours=7),
            created_at=NOW - timedelta(hours=8),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_3.value,
        )
        result = await dashboard.dashboard_casual_vs_cedh(
            period_all(),
            GuildFilter(mode="include", xid=int(guild.xid)),
        )
        assert sum(p["count"] for p in result["cedh"]) == 3
        assert sum(p["count"] for p in result["casual"]) == 1

    async def test_guild_filter_is_honored(self, seed: Seed) -> None:
        g2 = seed["g2"]
        # g2 has only casual commander/modern games and is not in CEDH_GUILDS
        # and its name does not contain "cedh"; cEDH series should be empty.
        result = await dashboard.dashboard_casual_vs_cedh(
            period_all(),
            GuildFilter(mode="include", xid=int(g2.xid)),
        )
        assert result["cedh"] == []
        assert sum(p["count"] for p in result["casual"]) == 2

    async def test_classification_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_casual_vs_cedh(period_30d(), all_guilds())
        assert isinstance(result["casual"], list)
        assert isinstance(result["cedh"], list)


@pytest.mark.asyncio
class TestDashboardServerPopularity:
    async def test_top_guilds(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_server_popularity(period_all(), all_guilds())
        names = [s["name"] for s in result["series"]]
        assert "Guild One" in names
        assert "Guild Two" in names

    async def test_empty_when_no_matching_games(self, factories: Factories) -> None:
        del factories
        result = await dashboard.dashboard_server_popularity(period_30d(), all_guilds())
        assert result["series"] == []

    async def test_top_n_limit(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_server_popularity(
            period_all(),
            all_guilds(),
            top_n=1,
        )
        assert len(result["series"]) == 1

    async def test_totals_threshold_filters_table_only(self, seed: Seed) -> None:
        del seed
        # The seeded guilds have far fewer than 10 games; with the default
        # threshold totals is empty but the chart series is unaffected.
        result = await dashboard.dashboard_server_popularity(period_all(), all_guilds())
        assert result["totals"] == []
        assert len(result["series"]) >= 2

    async def test_totals_includes_qualifying_guilds_sorted_desc(
        self,
        seed: Seed,
    ) -> None:
        del seed
        result = await dashboard.dashboard_server_popularity(
            period_all(),
            all_guilds(),
            totals_min=2,
        )
        names = [r["name"] for r in result["totals"]]
        counts = [r["count"] for r in result["totals"]]
        assert "Guild One" in names
        assert "Guild Two" in names
        assert all(c >= 2 for c in counts)
        assert counts == sorted(counts, reverse=True)


@pytest.mark.asyncio
class TestDashboardServicePopularity:
    async def test_groups_by_service(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_service_popularity(period_all(), all_guilds())
        names = [s["name"] for s in result["series"]]
        assert "SpellTable" in names
        assert "Convoke" in names
        # Series is sorted by total descending; SpellTable should be first (more games).
        assert result["series"][0]["name"] == "SpellTable"

    async def test_groups_by_service_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_service_popularity(period_30d(), all_guilds())
        assert isinstance(result["series"], list)


@pytest.mark.asyncio
class TestDashboardLanguages:
    async def test_user_languages(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_user_languages(period_all(), all_guilds())
        locales = {row["locale"]: row["count"] for row in result["rows"]}
        assert locales.get("en", 0) >= 2
        assert locales.get("fr", 0) >= 1

    async def test_game_languages(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_game_languages(period_all(), all_guilds())
        locales = {row["locale"]: row["count"] for row in result["rows"]}
        assert locales.get("en", 0) >= 1
        assert locales.get("de", 0) == 2

    async def test_user_languages_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_user_languages(period_30d(), all_guilds())
        assert isinstance(result["rows"], list)

    async def test_game_languages_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_game_languages(period_30d(), all_guilds())
        assert isinstance(result["rows"], list)

    async def test_top_guild_per_game_language(self, seed: Seed) -> None:
        g1 = seed["g1"]
        g2 = seed["g2"]
        result = await dashboard.dashboard_top_guild_per_game_language(
            period_all(),
            all_guilds(),
        )
        by_locale = {row["locale"]: row for row in result["rows"]}
        assert by_locale["en"]["guild_name"] == g1.name
        assert by_locale["en"]["guild_xid"] == str(int(g1.xid))
        assert by_locale["en"]["count"] == 4
        assert by_locale["de"]["guild_name"] == g2.name
        assert by_locale["de"]["guild_xid"] == str(int(g2.xid))
        assert by_locale["de"]["count"] == 2
        # Rows are ordered by count descending then locale.
        assert result["rows"][0]["locale"] == "en"
        assert result["rows"][1]["locale"] == "de"

    async def test_top_guild_per_game_language_guild_filter(self, seed: Seed) -> None:
        g1 = seed["g1"]
        opts = GuildFilter(mode="exclude", xid=int(g1.xid))
        result = await dashboard.dashboard_top_guild_per_game_language(period_all(), opts)
        locales = {row["locale"] for row in result["rows"]}
        assert "en" not in locales
        assert "de" in locales

    async def test_top_guild_per_game_language_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_top_guild_per_game_language(
            period_30d(),
            all_guilds(),
        )
        assert isinstance(result["rows"], list)

    async def test_top_guild_per_game_language_keeps_only_top_per_locale(
        self,
        factories: Factories,
    ) -> None:
        top = factories.guild.create(xid=900101, name="Top Guild")
        runner_up = factories.guild.create(xid=900102, name="Runner Up")
        top_ch = factories.channel.create(xid=910101, name="top-ch", guild=top)
        runner_up_ch = factories.channel.create(xid=910102, name="ru-ch", guild=runner_up)
        for offset in (1.0, 2.0):
            factories.game.create(
                guild=top,
                channel=top_ch,
                started_at=NOW - timedelta(hours=offset),
                locale="ja",
            )
        factories.game.create(
            guild=runner_up,
            channel=runner_up_ch,
            started_at=NOW - timedelta(hours=3.0),
            locale="ja",
        )

        result = await dashboard.dashboard_top_guild_per_game_language(
            period_all(),
            all_guilds(),
        )
        ja_rows = [row for row in result["rows"] if row["locale"] == "ja"]
        assert len(ja_rows) == 1
        assert ja_rows[0]["guild_xid"] == str(int(top.xid))
        assert ja_rows[0]["count"] == 2

    async def test_guild_languages(self, factories: Factories) -> None:
        g_en_a = factories.guild.create(xid=900201, name="EN A", locale="en")
        g_en_b = factories.guild.create(xid=900202, name="EN B", locale="en")
        g_de = factories.guild.create(xid=900203, name="DE", locale="de")
        ch_en_a = factories.channel.create(xid=910201, name="en-a-ch", guild=g_en_a)
        ch_en_b = factories.channel.create(xid=910202, name="en-b-ch", guild=g_en_b)
        ch_de = factories.channel.create(xid=910203, name="de-ch", guild=g_de)
        # Multiple games per guild should not inflate the distinct-guild count.
        for offset in (1.0, 2.0):
            factories.game.create(
                guild=g_en_a,
                channel=ch_en_a,
                started_at=NOW - timedelta(hours=offset),
            )
        factories.game.create(
            guild=g_en_b,
            channel=ch_en_b,
            started_at=NOW - timedelta(hours=3.0),
        )
        factories.game.create(
            guild=g_de,
            channel=ch_de,
            started_at=NOW - timedelta(hours=4.0),
        )

        result = await dashboard.dashboard_guild_languages(period_all(), all_guilds())
        by_locale = {row["locale"]: row["count"] for row in result["rows"]}
        assert by_locale["en"] == 2
        assert by_locale["de"] == 1
        # Rows are ordered by count descending then locale.
        assert result["rows"][0]["locale"] == "en"

    async def test_guild_languages_guild_filter(self, factories: Factories) -> None:
        g1 = factories.guild.create(xid=900301, name="Excluded", locale="en")
        g2 = factories.guild.create(xid=900302, name="Kept", locale="fr")
        ch1 = factories.channel.create(xid=910301, name="ex-ch", guild=g1)
        ch2 = factories.channel.create(xid=910302, name="kept-ch", guild=g2)
        factories.game.create(guild=g1, channel=ch1, started_at=NOW - timedelta(hours=1.0))
        factories.game.create(guild=g2, channel=ch2, started_at=NOW - timedelta(hours=2.0))

        opts = GuildFilter(mode="exclude", xid=int(g1.xid))
        result = await dashboard.dashboard_guild_languages(period_all(), opts)
        locales = {row["locale"] for row in result["rows"]}
        assert "en" not in locales
        assert "fr" in locales

    async def test_guild_languages_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_guild_languages(period_30d(), all_guilds())
        assert isinstance(result["rows"], list)


@pytest.mark.asyncio
class TestDashboardHourAndDay:
    async def test_hour_of_day_returns_24_buckets(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_hour_of_day(period_all(), all_guilds())
        assert len(result["hours"]) == 24
        assert sum(h["count"] for h in result["hours"]) == 6

    async def test_day_of_week_returns_7_buckets(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_day_of_week(period_all(), all_guilds())
        assert len(result["days"]) == 7
        assert sum(d["count"] for d in result["days"]) == 6

    async def test_hour_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_hour_of_day(period_30d(), all_guilds())
        assert len(result["hours"]) == 24

    async def test_day_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_day_of_week(period_30d(), all_guilds())
        assert len(result["days"]) == 7


@pytest.mark.asyncio
class TestDashboardFormatsSeats:
    async def test_popular_formats(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_popular_formats(period_all(), all_guilds())
        formats = {row["format"]: row["count"] for row in result["rows"]}
        assert formats.get("Commander", 0) >= 1
        assert formats.get("Modern", 0) >= 1
        assert formats.get("cEDH", 0) >= 1

    async def test_popular_seats(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_popular_seats(period_all(), all_guilds())
        seats = {row["seats"]: row["count"] for row in result["rows"]}
        assert seats.get(4, 0) == 4
        assert seats.get(2, 0) == 2

    async def test_popular_formats_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_popular_formats(period_30d(), all_guilds())
        assert isinstance(result["rows"], list)

    async def test_popular_seats_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_popular_seats(period_30d(), all_guilds())
        assert isinstance(result["rows"], list)


@pytest.mark.asyncio
class TestDashboardBracketAdoption:
    async def test_adoption_rate(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_bracket_adoption(period_all(), all_guilds())
        assert isinstance(result["rate"], list)
        # Every point should be a percent between 0 and 100.
        for point in result["rate"]:
            assert 0.0 <= point["count"] <= 100.0

    async def test_adoption_rate_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_bracket_adoption(period_30d(), all_guilds())
        assert isinstance(result["rate"], list)

    async def test_leaders_shape_and_default_empty(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_bracket_adoption(period_all(), all_guilds())
        leaders = result["leaders"]
        # One row per non-NONE bracket, in bracket order.
        assert [r["bracket"] for r in leaders] == [
            "Bracket 1: Exhibition",
            "Bracket 2: Core",
            "Bracket 3: Upgraded",
            "Bracket 4: Optimized",
            "Bracket 5: Competitive",
        ]
        # The seed's bracketable bracket-3 game lives on Guild One; bracket 5
        # is on a CEDH-format game which is not bracketable, so it has no
        # qualifying leader.
        by_bracket = {r["bracket"]: r for r in leaders}
        assert by_bracket["Bracket 3: Upgraded"]["server"] == "Guild One"
        assert by_bracket["Bracket 3: Upgraded"]["count"] == 1
        assert by_bracket["Bracket 5: Competitive"]["server"] is None
        assert by_bracket["Bracket 5: Competitive"]["count"] == 0
        # Brackets with no games come through as empty placeholders.
        assert by_bracket["Bracket 1: Exhibition"]["server"] is None
        assert by_bracket["Bracket 1: Exhibition"]["count"] == 0

    async def test_leaders_picks_top_server_per_bracket(
        self,
        factories: Factories,
        seed: Seed,
    ) -> None:
        del seed
        # Two more guilds both playing bracket-4 commander games; the one
        # with more games should be reported as the leader.
        ga = factories.guild.create(xid=900801, name="Alpha Guild")
        gb = factories.guild.create(xid=900802, name="Beta Guild")
        cha = factories.channel.create(xid=910801, name="a", guild=ga)
        chb = factories.channel.create(xid=910802, name="b", guild=gb)
        for off in (1.0, 2.0, 3.0):
            factories.game.create(
                guild=ga,
                channel=cha,
                started_at=NOW - timedelta(hours=off),
                created_at=NOW - timedelta(hours=off + 0.1),
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.BRACKET_4.value,
            )
        factories.game.create(
            guild=gb,
            channel=chb,
            started_at=NOW - timedelta(hours=5),
            created_at=NOW - timedelta(hours=5.1),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_4.value,
        )
        result = await dashboard.dashboard_bracket_adoption(period_all(), all_guilds())
        by_bracket = {r["bracket"]: r for r in result["leaders"]}
        assert by_bracket["Bracket 4: Optimized"]["server"] == "Alpha Guild"
        assert by_bracket["Bracket 4: Optimized"]["count"] == 3

    async def test_leaders_tie_breaks_alphabetically(
        self,
        factories: Factories,
        seed: Seed,
    ) -> None:
        del seed
        # Equal counts on the same bracket; the alphabetically-first guild
        # name wins. "Alpha Guild" beats "Beta Guild" for bracket 2.
        ga = factories.guild.create(xid=900811, name="Alpha Guild")
        gb = factories.guild.create(xid=900812, name="Beta Guild")
        cha = factories.channel.create(xid=910811, name="a", guild=ga)
        chb = factories.channel.create(xid=910812, name="b", guild=gb)
        for guild, channel, off in ((ga, cha, 1.0), (gb, chb, 2.0)):
            factories.game.create(
                guild=guild,
                channel=channel,
                started_at=NOW - timedelta(hours=off),
                created_at=NOW - timedelta(hours=off + 0.1),
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.BRACKET_2.value,
            )
        result = await dashboard.dashboard_bracket_adoption(period_all(), all_guilds())
        by_bracket = {r["bracket"]: r for r in result["leaders"]}
        assert by_bracket["Bracket 2: Core"]["server"] == "Alpha Guild"
        assert by_bracket["Bracket 2: Core"]["count"] == 1

    async def test_leaders_honors_guild_filter(self, seed: Seed) -> None:
        g2 = seed["g2"]
        # g2 has no bracketed games at all; every leader row should be empty.
        result = await dashboard.dashboard_bracket_adoption(
            period_all(),
            GuildFilter(mode="include", xid=int(g2.xid)),
        )
        for row in result["leaders"]:
            assert row["server"] is None
            assert row["count"] == 0


@pytest.mark.asyncio
class TestDashboardAvgWaitTime:
    async def test_avg_wait_time(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_avg_wait_time(period_all(), all_guilds())
        assert len(result["series"]) >= 1
        # Every game's wait was 10 minutes (created_offset_extra_min default).
        for point in result["series"]:
            assert point["minutes"] == 10.0

    async def test_avg_wait_time_bounded(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_avg_wait_time(period_30d(), all_guilds())
        assert isinstance(result["series"], list)


@pytest.mark.asyncio
class TestDashboardTopPlayers:
    async def test_orders_by_plays(self, seed: Seed) -> None:
        users = seed["users"]
        u1 = users[0]
        result = await dashboard.dashboard_top_players(period_all(), all_guilds())
        # u1 played 4 games (most of anyone).
        assert result["rows"][0]["user_xid"] == str(int(u1.xid))
        assert result["rows"][0]["count"] == 4

    async def test_top_n_limit(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_top_players(period_all(), all_guilds(), top_n=2)
        assert len(result["rows"]) == 2

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_top_players(period_30d(), all_guilds())
        assert isinstance(result["rows"], list)


@pytest.mark.asyncio
class TestDashboardTopBlocked:
    async def test_orders_by_blocks(self, seed: Seed) -> None:
        users = seed["users"]
        u1 = users[0]
        result = await dashboard.dashboard_top_blocked(period_30d(), all_guilds())
        # u1 was blocked twice (by u2 and u3), more than u4 (blocked once).
        assert result["rows"][0]["user_xid"] == str(int(u1.xid))
        assert result["rows"][0]["count"] == 2

    async def test_top_n_limit(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_top_blocked(period_all(), all_guilds(), top_n=1)
        assert len(result["rows"]) == 1


@pytest.mark.asyncio
class TestDashboardGamesPerPlayer:
    async def test_histogram(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_games_per_player(period_all(), all_guilds())
        # 4 players: u1=4, u2=3, u3=3, u4=2 => median = 3
        assert result["median"] == 3
        buckets = {row["bucket"]: row["players"] for row in result["histogram"]}
        assert buckets.get("2", 0) == 1
        assert buckets.get("3", 0) == 2
        assert buckets.get("4", 0) == 1

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_games_per_player(period_30d(), all_guilds())
        assert result["median"] == 0
        assert result["histogram"] == []

    async def test_overflow_bucket(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=950001, name="Heavy")
        channel = factories.channel.create(xid=950002, name="ch", guild=guild)
        user = factories.user.create(xid=850001, name="grinder")
        for i in range(25):
            g = factories.game.create(
                guild=guild,
                channel=channel,
                started_at=NOW - timedelta(hours=i + 1),
                created_at=NOW - timedelta(hours=i + 2),
            )
            factories.play.create(game_id=g.id, user_xid=user.xid, og_guild_xid=guild.xid)
        result = await dashboard.dashboard_games_per_player(period_all(), all_guilds())
        overflow = [r for r in result["histogram"] if r["bucket"] == "21+"]
        assert len(overflow) == 1
        assert overflow[0]["players"] == 1


@pytest.mark.asyncio
class TestDashboardRules:
    async def test_rules_and_ngrams(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_rules(period_all(), all_guilds())
        rules = {row["rule"]: row["count"] for row in result["top_rules"]}
        assert any("no fast mana" in r for r in rules)
        assert isinstance(result["rule_ngrams"], list)

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_rules(period_30d(), all_guilds())
        assert result["top_rules"] == []
        assert result["rule_ngrams"] == []

    async def test_skips_rules_that_normalize_to_empty(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=960001, name="RulesG")
        channel = factories.channel.create(xid=960002, name="ch", guild=guild)
        # A rule of only punctuation passes the SQL filter but normalizes to "".
        factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=2),
            rules="...",
        )
        result = await dashboard.dashboard_rules(period_all(), all_guilds())
        assert all(r["rule"] != "" for r in result["top_rules"])


@pytest.mark.asyncio
class TestDashboardCohortRetention:
    async def test_cohorts_built_from_first_play_week(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_cohort_retention(period_all(), all_guilds())
        assert result["max_weeks"] >= 0
        assert len(result["cohorts"]) >= 1
        first = result["cohorts"][0]
        assert {"cohort", "size", "weeks"} <= set(first)
        assert first["size"] >= 1
        zero = next(w for w in first["weeks"] if w["offset"] == 0)
        assert zero["pct"] == 100.0

    async def test_returners_across_weeks(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=950101, name="Cohort")
        channel = factories.channel.create(xid=950102, name="ch", guild=guild)
        user = factories.user.create(xid=850101, name="ret")
        early = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(days=21),
            created_at=NOW - timedelta(days=21, minutes=5),
        )
        late = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(days=7),
            created_at=NOW - timedelta(days=7, minutes=5),
        )
        factories.play.create(game_id=early.id, user_xid=user.xid, og_guild_xid=guild.xid)
        factories.play.create(game_id=late.id, user_xid=user.xid, og_guild_xid=guild.xid)
        result = await dashboard.dashboard_cohort_retention(
            period_all(),
            GuildFilter(mode="include", xid=int(guild.xid)),
        )
        assert result["max_weeks"] >= 1
        cohort = result["cohorts"][0]
        offsets = {w["offset"]: w for w in cohort["weeks"]}
        assert offsets[0]["pct"] == 100.0
        assert max(offsets) >= 1

    async def test_bounded_period_applies_filter(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_cohort_retention(period_30d(), all_guilds())
        assert isinstance(result["cohorts"], list)

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_cohort_retention(period_30d(), all_guilds())
        assert result == {"cohorts": [], "max_weeks": 0}


@pytest.mark.asyncio
class TestDashboardActivityHeatmap:
    async def test_cells_present(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_activity_heatmap(period_all(), all_guilds())
        assert isinstance(result["cells"], list)
        assert len(result["cells"]) >= 1
        cell = result["cells"][0]
        assert {"dow", "hour", "count"} == set(cell)
        assert 0 <= cell["dow"] <= 6
        assert 0 <= cell["hour"] <= 23

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_activity_heatmap(period_30d(), all_guilds())
        assert isinstance(result["cells"], list)

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_activity_heatmap(period_30d(), all_guilds())
        assert result == {"cells": []}


@pytest.mark.asyncio
class TestDashboardWaitTimeDistribution:
    async def test_returns_three_percentile_series(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_wait_time_distribution(period_all(), all_guilds())
        assert {"p50", "p95", "p99"} == set(result)
        assert len(result["p50"]) >= 1
        point = result["p50"][0]
        assert {"date", "minutes"} == set(point)
        assert point["minutes"] >= 0

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_wait_time_distribution(period_30d(), all_guilds())
        assert isinstance(result["p95"], list)

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_wait_time_distribution(period_30d(), all_guilds())
        assert result == {"p50": [], "p95": [], "p99": []}


@pytest.mark.asyncio
class TestDashboardVoiceAdoption:
    async def test_rate_reflects_voice_xid_presence(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=952001, name="V")
        channel = factories.channel.create(xid=952002, name="ch", guild=guild)
        factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=1, minutes=5),
            voice_xid=987654,
        )
        factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(hours=2),
            created_at=NOW - timedelta(hours=2, minutes=5),
            voice_xid=None,
        )
        result = await dashboard.dashboard_voice_adoption(
            period_all(),
            GuildFilter(mode="include", xid=int(guild.xid)),
        )
        assert len(result["rate"]) == 1
        assert result["rate"][0]["count"] == 50.0

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_voice_adoption(period_30d(), all_guilds())
        assert isinstance(result["rate"], list)

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_voice_adoption(period_30d(), all_guilds())
        assert result == {"rate": []}


@pytest.mark.asyncio
class TestDashboardBlindAdoption:
    async def test_rate_reflects_blind_flag(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=953001, name="B")
        channel = factories.channel.create(xid=953002, name="ch", guild=guild)
        for _ in range(3):
            factories.game.create(
                guild=guild,
                channel=channel,
                started_at=NOW - timedelta(hours=1),
                created_at=NOW - timedelta(hours=1, minutes=5),
                blind=True,
            )
        factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=1, minutes=5),
            blind=False,
        )
        result = await dashboard.dashboard_blind_adoption(
            period_all(),
            GuildFilter(mode="include", xid=int(guild.xid)),
        )
        assert len(result["rate"]) == 1
        assert result["rate"][0]["count"] == 75.0

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_blind_adoption(period_30d(), all_guilds())
        assert isinstance(result["rate"], list)

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_blind_adoption(period_30d(), all_guilds())
        assert result == {"rate": []}


@pytest.mark.asyncio
class TestDashboardMythicVerification:
    async def test_rate_for_enabled_guild(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=954001, name="M", enable_mythic_track=True)
        channel = factories.channel.create(xid=954002, name="ch", guild=guild)
        u1 = factories.user.create(xid=854001, name="m1")
        u2 = factories.user.create(xid=854002, name="m2")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=1, minutes=5),
        )
        factories.play.create(
            game_id=game.id,
            user_xid=u1.xid,
            og_guild_xid=guild.xid,
            verified_at=NOW,
        )
        factories.play.create(
            game_id=game.id,
            user_xid=u2.xid,
            og_guild_xid=guild.xid,
            verified_at=None,
        )
        result = await dashboard.dashboard_mythic_verification(
            period_all(),
            GuildFilter(mode="include", xid=int(guild.xid)),
        )
        assert len(result["rate"]) == 1
        assert result["rate"][0]["count"] == 50.0

    async def test_excludes_guilds_without_track(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_mythic_verification(period_all(), all_guilds())
        assert result == {"rate": []}

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_mythic_verification(period_30d(), all_guilds())
        assert isinstance(result["rate"], list)


@pytest.mark.asyncio
class TestDashboardQueueDepth:
    async def test_counts_pending_only(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=955001, name="Q")
        channel = factories.channel.create(xid=955002, name="ch", guild=guild)
        u1 = factories.user.create(xid=855001, name="q1")
        u2 = factories.user.create(xid=855002, name="q2")
        u3 = factories.user.create(xid=855003, name="q3")
        pending = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
            format=GameFormat.COMMANDER.value,
        )
        started = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=NOW - timedelta(minutes=1),
            created_at=NOW - timedelta(minutes=5),
        )
        deleted = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
            deleted_at=NOW,
        )
        factories.queue.create(user_xid=u1.xid, game_id=pending.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u2.xid, game_id=pending.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u3.xid, game_id=started.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=u1.xid, game_id=deleted.id, og_guild_xid=guild.xid)
        result = await dashboard.dashboard_queue_depth(
            period_30d(),
            GuildFilter(mode="include", xid=int(guild.xid)),
        )
        assert result["total"] == 2
        assert result["by_format"] == [{"format": str(GameFormat.COMMANDER), "count": 2}]

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_queue_depth(period_all(), all_guilds())
        assert result == {"total": 0, "by_format": []}


@pytest.mark.asyncio
class TestDashboardActiveQueues:
    async def test_one_row_per_pending_game_with_players(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild_a = factories.guild.create(xid=956001, name="Alpha")
        guild_b = factories.guild.create(xid=956002, name="Bravo")
        ch_a1 = factories.channel.create(xid=956101, name="lfg-a1", guild=guild_a)
        ch_a2 = factories.channel.create(xid=956102, name="lfg-a2", guild=guild_a)
        ch_b1 = factories.channel.create(xid=956103, name="lfg-b1", guild=guild_b)
        u1 = factories.user.create(xid=856001, name="u1")
        u2 = factories.user.create(xid=856002, name="u2")
        u3 = factories.user.create(xid=856003, name="u3")
        u4 = factories.user.create(xid=856004, name="u4")
        # Guild A, channel 1: pending with two players (highest count).
        pending_a1 = factories.game.create(
            guild=guild_a,
            channel=ch_a1,
            started_at=None,
            created_at=NOW - timedelta(minutes=7),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_3.value,
        )
        # Guild A, channel 2: pending with one player.
        pending_a2 = factories.game.create(
            guild=guild_a,
            channel=ch_a2,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
            format=GameFormat.MODERN.value,
        )
        # Guild B, channel 1: pending with one player.
        pending_b1 = factories.game.create(
            guild=guild_b,
            channel=ch_b1,
            started_at=None,
            created_at=NOW - timedelta(seconds=90),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.BRACKET_5.value,
        )
        # Pending game with zero players in queue: must be omitted.
        factories.game.create(
            guild=guild_a,
            channel=ch_a1,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        # Started game: not pending, must be omitted even with queue rows.
        started = factories.game.create(
            guild=guild_a,
            channel=ch_a1,
            started_at=NOW - timedelta(minutes=1),
            created_at=NOW - timedelta(minutes=5),
        )
        # Deleted pending game: must be omitted.
        deleted = factories.game.create(
            guild=guild_a,
            channel=ch_a1,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
            deleted_at=NOW,
        )
        factories.queue.create(user_xid=u1.xid, game_id=pending_a1.id, og_guild_xid=guild_a.xid)
        factories.queue.create(user_xid=u2.xid, game_id=pending_a1.id, og_guild_xid=guild_a.xid)
        factories.queue.create(user_xid=u3.xid, game_id=pending_a2.id, og_guild_xid=guild_a.xid)
        factories.queue.create(user_xid=u4.xid, game_id=pending_b1.id, og_guild_xid=guild_b.xid)
        factories.queue.create(user_xid=u1.xid, game_id=started.id, og_guild_xid=guild_a.xid)
        factories.queue.create(user_xid=u2.xid, game_id=deleted.id, og_guild_xid=guild_a.xid)
        result = await dashboard.dashboard_active_queues(period_30d(), all_guilds())
        assert result["rows"] == [
            {
                "guild_xid": str(int(guild_a.xid)),
                "guild_name": "Alpha",
                "channel_xid": str(int(ch_a1.xid)),
                "channel_name": "lfg-a1",
                "format": str(GameFormat.COMMANDER),
                "bracket": GameBracket.BRACKET_3.title,
                "wait_seconds": 7 * 60,
                "players": 2,
            },
            {
                "guild_xid": str(int(guild_a.xid)),
                "guild_name": "Alpha",
                "channel_xid": str(int(ch_a2.xid)),
                "channel_name": "lfg-a2",
                "format": str(GameFormat.MODERN),
                "bracket": GameBracket.NONE.title,
                "wait_seconds": 5 * 60,
                "players": 1,
            },
            {
                "guild_xid": str(int(guild_b.xid)),
                "guild_name": "Bravo",
                "channel_xid": str(int(ch_b1.xid)),
                "channel_name": "lfg-b1",
                "format": str(GameFormat.COMMANDER),
                "bracket": GameBracket.BRACKET_5.title,
                "wait_seconds": 90,
                "players": 1,
            },
        ]

    async def test_guild_filter_restricts_results(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild_a = factories.guild.create(xid=957001, name="A")
        guild_b = factories.guild.create(xid=957002, name="B")
        ch_a = factories.channel.create(xid=957101, name="ch-a", guild=guild_a)
        ch_b = factories.channel.create(xid=957102, name="ch-b", guild=guild_b)
        u1 = factories.user.create(xid=857001, name="u1")
        u2 = factories.user.create(xid=857002, name="u2")
        pending_a = factories.game.create(
            guild=guild_a,
            channel=ch_a,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        pending_b = factories.game.create(
            guild=guild_b,
            channel=ch_b,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        factories.queue.create(user_xid=u1.xid, game_id=pending_a.id, og_guild_xid=guild_a.xid)
        factories.queue.create(user_xid=u2.xid, game_id=pending_b.id, og_guild_xid=guild_b.xid)
        result = await dashboard.dashboard_active_queues(
            period_all(),
            GuildFilter(mode="include", xid=int(guild_b.xid)),
        )
        assert [r["guild_xid"] for r in result["rows"]] == [str(int(guild_b.xid))]

    async def test_missing_names_fall_back_to_empty_string(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=958001, name=None)
        channel = factories.channel.create(xid=958002, name=None, guild=guild)
        user = factories.user.create(xid=858001, name="u")
        pending = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
        )
        factories.queue.create(user_xid=user.xid, game_id=pending.id, og_guild_xid=guild.xid)
        result = await dashboard.dashboard_active_queues(period_all(), all_guilds())
        assert len(result["rows"]) == 1
        assert result["rows"][0]["guild_name"] == ""
        assert result["rows"][0]["channel_name"] == ""

    async def test_empty(self) -> None:
        result = await dashboard.dashboard_active_queues(period_all(), all_guilds())
        assert result == {"rows": []}
