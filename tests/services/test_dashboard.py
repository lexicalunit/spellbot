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
        assert result["players"] == 3

    async def test_guild_exclude_filter(self, seed: Seed) -> None:
        g1 = seed["g1"]
        opts = GuildFilter(mode="exclude", xid=int(g1.xid))
        result = await dashboard.dashboard_summary(period_all(), opts)
        assert result["games"] == 2
        assert result["players"] == 2

    async def test_bounded_period(self, seed: Seed) -> None:
        del seed
        result = await dashboard.dashboard_summary(period_30d(), all_guilds())
        assert result["games"] >= 1
        assert result["bucket"] == "day"


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
class TestDashboardCasualVsCedh:
    async def test_classification(self, factories: Factories, seed: Seed) -> None:
        del seed
        casual_guild = factories.guild.create(xid=304276578005942272, name="PlayEDH")
        cedh_guild = factories.guild.create(xid=113555415446413312, name="cEDH")
        ch_a = factories.channel.create(xid=910101, name="a", guild=casual_guild)
        ch_b = factories.channel.create(xid=910102, name="b", guild=cedh_guild)
        factories.game.create(
            guild=casual_guild,
            channel=ch_a,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=2),
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
        )
        factories.game.create(
            guild=cedh_guild,
            channel=ch_b,
            started_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=2),
        )
        result = await dashboard.dashboard_casual_vs_cedh(period_all(), all_guilds())
        assert sum(p["count"] for p in result["casual"]) >= 1
        # cEDH includes guild2 from seed (bracket 5) plus the cedh guild here.
        assert sum(p["count"] for p in result["cedh"]) >= 1

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
