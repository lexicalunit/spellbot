from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from dateutil.relativedelta import relativedelta

Bucket = Literal["day", "week", "month"]
Period = Literal["7d", "30d", "90d", "180d", "365d", "730d", "all"]

VALID_PERIODS: frozenset[str] = frozenset(("7d", "30d", "90d", "180d", "365d", "730d", "all"))

PERIOD_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
    "730d": 730,
}
PERIOD_BUCKET: dict[str, Bucket] = {
    "7d": "day",
    "30d": "day",
    "90d": "day",
    "180d": "week",
    "365d": "week",
    "730d": "month",
    "all": "month",
}


@dataclass(frozen=True)
class PeriodSpec:
    period: Period
    start_dt: datetime | None
    bucket: Bucket


def parse_period(period: str | None) -> PeriodSpec:
    """
    Parse the period query parameter into a (start_dt, bucket) spec.

    Unknown values default to 30d. `all` returns `start_dt=None` (no lower bound).
    """
    p = period if period in VALID_PERIODS else "30d"
    bucket = PERIOD_BUCKET[p]
    if p == "all":
        return PeriodSpec(period="all", start_dt=None, bucket=bucket)
    days = PERIOD_DAYS[p]
    start = datetime.now(tz=UTC) + relativedelta(days=-days)
    return PeriodSpec(period=p, start_dt=start, bucket=bucket)  # type: ignore[arg-type]


GuildMode = Literal["all", "include", "exclude"]


@dataclass(frozen=True)
class GuildFilter:
    mode: GuildMode
    xid: int | None

    @property
    def applies(self) -> bool:
        """Whether this filter should be applied (i.e. not the unrestricted default)."""
        return self.mode != "all" and self.xid is not None


def parse_guild(value: str | None) -> GuildFilter:
    """
    Parse the guild query parameter into a GuildFilter.

    Recognized values:
      * missing / empty / "all" -> all guilds
      * "<xid>" -> include only that guild
      * "not:<xid>" -> exclude that guild
    Invalid input falls back to "all".
    """
    if not value or value == "all":
        return GuildFilter(mode="all", xid=None)
    if value.startswith("not:"):
        rest = value[4:].strip()
        try:
            return GuildFilter(mode="exclude", xid=int(rest))
        except ValueError:
            return GuildFilter(mode="all", xid=None)
    try:
        return GuildFilter(mode="include", xid=int(value))
    except ValueError:
        return GuildFilter(mode="all", xid=None)
