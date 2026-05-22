from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from spellbot.web.dashboard_filters import (
    GuildFilter,
    PeriodSpec,
    parse_guild,
    parse_period,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory


class TestParsePeriod:
    @pytest.mark.parametrize(
        ("period", "expected_period", "expected_bucket", "expected_days"),
        [
            pytest.param("7d", "7d", "day", 7, id="7d"),
            pytest.param("30d", "30d", "day", 30, id="30d"),
            pytest.param("90d", "90d", "day", 90, id="90d"),
            pytest.param("180d", "180d", "week", 180, id="180d"),
            pytest.param("365d", "365d", "week", 365, id="365d"),
            pytest.param("730d", "730d", "month", 730, id="730d"),
        ],
    )
    def test_valid_periods(
        self,
        freezer: FrozenDateTimeFactory,
        period: str,
        expected_period: str,
        expected_bucket: str,
        expected_days: int,
    ) -> None:
        freezer.move_to(datetime(2024, 6, 15, 12, 0, tzinfo=UTC))
        spec = parse_period(period)
        assert spec.period == expected_period
        assert spec.bucket == expected_bucket
        assert spec.start_dt is not None
        assert spec.start_dt == datetime.now(tz=UTC) - timedelta(days=expected_days)

    def test_all(self) -> None:
        spec = parse_period("all")
        assert spec.period == "all"
        assert spec.bucket == "month"
        assert spec.start_dt is None

    def test_none_defaults_to_30d(self) -> None:
        spec = parse_period(None)
        assert spec.period == "30d"
        assert spec.bucket == "day"
        assert spec.start_dt is not None

    def test_unknown_defaults_to_30d(self) -> None:
        spec = parse_period("bogus")
        assert spec.period == "30d"
        assert spec.bucket == "day"


class TestParseGuild:
    @pytest.mark.parametrize("value", [None, "", "all"])
    def test_all(self, value: str | None) -> None:
        opts = parse_guild(value)
        assert opts.mode == "all"
        assert opts.xid is None
        assert opts.applies is False

    def test_include(self) -> None:
        opts = parse_guild("12345")
        assert opts.mode == "include"
        assert opts.xid == 12345
        assert opts.applies is True

    def test_exclude(self) -> None:
        opts = parse_guild("not:12345")
        assert opts.mode == "exclude"
        assert opts.xid == 12345
        assert opts.applies is True

    def test_exclude_invalid_xid_falls_back_to_all(self) -> None:
        opts = parse_guild("not:abc")
        assert opts.mode == "all"
        assert opts.xid is None

    def test_invalid_include_falls_back_to_all(self) -> None:
        opts = parse_guild("not-a-number")
        assert opts.mode == "all"
        assert opts.xid is None


class TestGuildFilterApplies:
    def test_all_mode_does_not_apply(self) -> None:
        assert GuildFilter(mode="all", xid=None).applies is False

    def test_include_with_xid_applies(self) -> None:
        assert GuildFilter(mode="include", xid=42).applies is True

    def test_exclude_with_xid_applies(self) -> None:
        assert GuildFilter(mode="exclude", xid=42).applies is True


class TestPeriodSpec:
    def test_is_dataclass_with_fields(self) -> None:
        spec = PeriodSpec(period="7d", start_dt=None, bucket="day")
        assert spec.period == "7d"
        assert spec.bucket == "day"
