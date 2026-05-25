from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, distinct, extract, func, or_, select

from spellbot.database import DatabaseSession, any_of
from spellbot.enums import (
    GAME_BRACKET_ORDER,
    GAME_FORMAT_ORDER,
    GameBracket,
    GameFormat,
    GameService,
)
from spellbot.models import Block, Game, Guild, Play, Queue, User
from spellbot.services.plays import extract_ngrams, normalize_rule

if TYPE_CHECKING:
    from sqlalchemy.sql import ColumnElement

    from spellbot.web.dashboard_filters import GuildFilter, PeriodSpec

SERVICE_LABEL = case(
    *((Game.service == s.value, s.title) for s in GameService),
    else_="Unknown",
).label("service")

# Formats considered "bracketable" for the bracket adoption rate.
BRACKETABLE_FORMATS: frozenset[int] = frozenset(
    {
        GameFormat.COMMANDER.value,
        GameFormat.EDH_MAX.value,
        GameFormat.EDH_HIGH.value,
        GameFormat.EDH_MID.value,
        GameFormat.EDH_LOW.value,
        GameFormat.EDH_BATTLECRUISER.value,
        GameFormat.PLANECHASE.value,
    },
)

# Curated allowlist of cEDH guilds used by `dashboard_casual_vs_cedh`. Any
# game on one of these servers is classified as cEDH regardless of its format
# or bracket. Guilds whose name contains "cedh" (case-insensitive) are also
# treated as cEDH without needing to be listed here.
CEDH_GUILDS: frozenset[int] = frozenset(
    {
        113555415446413312,  # Competitive EDH
        1321026027337547817,  # CriticalEDH
        682734915846275184,  # Play to Win
        530219227924267008,  # PWP
        954838268275470367,  # ka0s Tournaments
        763138565231345665,  # WreckRoomCedh
        1036729704180355202,  # Training Grounds
    },
)


def game_guild_filter(opts: GuildFilter) -> list[ColumnElement[bool]]:
    """Build a list of SQLAlchemy filter clauses for games.guild_xid."""
    if not opts.applies:
        return []
    assert opts.xid is not None
    if opts.mode == "include":
        return [Game.guild_xid == opts.xid]
    return [Game.guild_xid != opts.xid]


def trunc_date(column: Any, bucket: str) -> Any:
    """Apply Postgres `date_trunc` to a timestamp column."""
    return func.date_trunc(bucket, column)


def iso_str(value: Any) -> str:
    """Format a date / datetime / string as an ISO date string."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


async def dashboard_guilds(*, top_n: int = 100) -> list[dict[str, Any]]:
    """
    Return the top `top_n` guilds (xid + name) for the filter dropdown.

    Guilds are ordered by total number of games (descending) so the most
    popular servers appear first. Guilds with no games are excluded. `xid`
    is returned as a string because Discord snowflake IDs exceed
    JavaScript's safe-integer range and would lose precision if parsed as
    JSON numbers.
    """
    top_rows = (
        await DatabaseSession.execute(
            select(Guild.xid, Guild.name, func.count(Game.id).label("total"))  # type: ignore[arg-type]
            .select_from(Guild)
            .join(Game, Game.guild_xid == Guild.xid)
            .group_by(Guild.xid, Guild.name)
            .order_by(func.count(Game.id).desc())
            .limit(top_n),
        )
    ).all()
    return [{"xid": str(int(xid)), "name": (name or "")} for xid, name, _ in top_rows]


async def dashboard_summary(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return the headline totals shown across the top of the dashboard."""
    game_filters = [Game.started_at.isnot(None), *game_guild_filter(opts)]
    if period.start_dt is not None:
        game_filters.append(Game.started_at >= period.start_dt)

    games = int(
        (await DatabaseSession.execute(select(func.count(Game.id)).where(*game_filters))).scalar()
        or 0,
    )

    expired_filters = [
        Game.started_at.is_(None),
        Game.deleted_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        expired_filters.append(Game.deleted_at >= period.start_dt)
    expired = int(
        (
            await DatabaseSession.execute(select(func.count(Game.id)).where(*expired_filters))
        ).scalar()
        or 0,
    )

    total_attempted = games + expired
    fill_rate = round(100.0 * games / total_attempted, 1) if total_attempted else 0.0

    players = int(
        (
            await DatabaseSession.execute(
                select(func.count(distinct(Play.user_xid)))
                .select_from(Play)
                .join(Game, Play.game_id == Game.id)  # type: ignore
                .where(*game_filters),
            )
        ).scalar()
        or 0,
    )

    server_filters: list[ColumnElement[bool]] = []
    if period.start_dt is not None:
        server_filters.append(Guild.updated_at >= period.start_dt)
    servers = int(
        (
            await DatabaseSession.execute(
                select(func.count(Guild.xid)).where(*server_filters),  # type: ignore[arg-type]
            )
        ).scalar()
        or 0,
    )

    bracket_rows = (
        await DatabaseSession.execute(
            select(Game.bracket, func.count(Game.id))  # type: ignore[arg-type]
            .where(*game_filters)
            .group_by(Game.bracket),
        )
    ).all()
    bracket_counts = {int(value): int(count) for value, count in bracket_rows}
    brackets = {b.name: bracket_counts.get(b.value, 0) for b in GameBracket}

    return {
        "games": games,
        "expired": expired,
        "fill_rate": fill_rate,
        "players": players,
        "servers": servers,
        "brackets": brackets,
        "period": period.period,
        "bucket": period.bucket,
    }


async def dashboard_totals(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return all-time totals shown in the global stat cards.

    `period` is accepted to match the standard endpoint signature but is
    intentionally ignored. `games` and `players` respect the guild filter;
    `servers` is global and intentionally ignores the guild filter.
    """
    del period
    game_filters = [Game.started_at.isnot(None), *game_guild_filter(opts)]
    games = int(
        (await DatabaseSession.execute(select(func.count(Game.id)).where(*game_filters))).scalar()
        or 0,
    )
    players = int(
        (
            await DatabaseSession.execute(
                select(func.count(distinct(Play.user_xid)))
                .select_from(Play)
                .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
                .where(*game_filters),
            )
        ).scalar()
        or 0,
    )
    servers = int(
        (
            await DatabaseSession.execute(
                select(func.count(Guild.xid)),  # type: ignore[arg-type]
            )
        ).scalar()
        or 0,
    )
    return {"games": games, "players": players, "servers": servers}


async def new_user_bucket_series(
    period: PeriodSpec,
    opts: GuildFilter,
) -> list[dict[str, Any]]:
    """
    Bucketed count of users whose first in-scope play falls in the bucket.

    A user is counted as "new" in the bucket containing the earliest
    `Game.started_at` across all their `Play` rows (within the guild
    filter). Bounded periods restrict the result to users whose first
    in-scope play is within the period.
    """
    inner_filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    first_play = (
        select(
            Play.user_xid.label("user_xid"),
            func.min(Game.started_at).label("first_started"),
        )
        .select_from(Play)
        .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
        .where(*inner_filters)
        .group_by(Play.user_xid)
        .subquery()
    )
    outer_filters: list[ColumnElement[bool]] = []
    if period.start_dt is not None:
        outer_filters.append(first_play.c.first_started >= period.start_dt)
    bucket_col = trunc_date(first_play.c.first_started, period.bucket).label("bucket")
    rows = (
        await DatabaseSession.execute(
            select(bucket_col, func.count(first_play.c.user_xid))
            .where(*outer_filters)
            .group_by(bucket_col)
            .order_by(bucket_col),
        )
    ).all()
    return [{"date": iso_str(row[0]), "count": int(row[1])} for row in rows]


async def active_user_bucket_series(
    period: PeriodSpec,
    bucket: str,
    opts: GuildFilter,
) -> list[dict[str, Any]]:
    """
    Bucketed count of distinct active users.

    Activity is defined as having a `Play` row tied to a `Game` whose
    `started_at` falls in the bucket. `COUNT(DISTINCT user_xid)` per bucket
    gives a true per-period active-user count. Honors the guild filter.
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    bucket_col = trunc_date(Game.started_at, bucket).label("bucket")
    rows = (
        await DatabaseSession.execute(
            select(bucket_col, func.count(distinct(Play.user_xid)))
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
            .where(*filters)
            .group_by(bucket_col)
            .order_by(bucket_col),
        )
    ).all()
    return [{"date": iso_str(row[0]), "count": int(row[1])} for row in rows]


async def dashboard_users_activity(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return user activity series: new users, DAU / WAU / MAU, and DAU:MAU ratio.

    Both `new_users` and the active-user series honor the guild filter; a user
    is counted only if they have a `Play` tied to a `Game` whose `started_at`
    falls within the relevant bucket (and within the guild scope).

    `new_users` is bucketed at `period.bucket` by the user's first in-scope
    `Game.started_at`. `dau` for the chart is bucketed at `period.bucket` so
    long windows render readably. The averages used for the stickiness ratio
    are computed at fixed `day` (DAU) and `month` (MAU) bucket sizes
    regardless of the display bucket, matching the standard "average DAU /
    average MAU" definition. `wau` and `mau` series are returned at fixed
    week / month buckets so the metric cards can average them directly.
    """
    new_users = await new_user_bucket_series(period, opts)
    dau = await active_user_bucket_series(period, period.bucket, opts)

    # The ratio needs DAU at day granularity even when the chart is bucketed
    # weekly or monthly; reuse the already-fetched series when possible.
    dau_daily = (
        dau if period.bucket == "day" else await active_user_bucket_series(period, "day", opts)
    )
    wau = await active_user_bucket_series(period, "week", opts)
    mau = await active_user_bucket_series(period, "month", opts)

    avg_dau = (sum(p["count"] for p in dau_daily) / len(dau_daily)) if dau_daily else 0.0
    avg_mau = (sum(p["count"] for p in mau) / len(mau)) if mau else 0.0
    dau_mau = round(100.0 * avg_dau / avg_mau, 1) if avg_mau else 0.0

    return {
        "new_users": new_users,
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "dau_mau": dau_mau,
    }


async def dashboard_games(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return bucketed counts of started and expired games for the period."""
    guild_clauses = game_guild_filter(opts)

    started_filters = [Game.started_at.isnot(None), *guild_clauses]
    if period.start_dt is not None:
        started_filters.append(Game.created_at >= period.start_dt)
    started_bucket = trunc_date(Game.created_at, period.bucket).label("bucket")
    started_rows = (
        await DatabaseSession.execute(
            select(started_bucket, func.count(Game.id))
            .where(*started_filters)
            .group_by(started_bucket)
            .order_by(started_bucket),
        )
    ).all()

    expired_filters = [Game.deleted_at.isnot(None), *guild_clauses]
    if period.start_dt is not None:
        expired_filters.append(Game.created_at >= period.start_dt)
    expired_bucket = trunc_date(Game.created_at, period.bucket).label("bucket")
    expired_rows = (
        await DatabaseSession.execute(
            select(expired_bucket, func.count(Game.id))
            .where(*expired_filters)
            .group_by(expired_bucket)
            .order_by(expired_bucket),
        )
    ).all()

    return {
        "started": [{"date": iso_str(r[0]), "count": int(r[1])} for r in started_rows],
        "expired": [{"date": iso_str(r[0]), "count": int(r[1])} for r in expired_rows],
    }


async def dashboard_player_growth(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return cumulative unique-player counts bucketed at `period.bucket`.

    Each user is attributed to the bucket containing their first in-scope
    `Game.started_at`; the series accumulates new users across buckets.
    """
    new_users = await new_user_bucket_series(period, opts)
    running = 0
    series: list[dict[str, Any]] = []
    for row in new_users:
        running += int(row["count"])
        series.append({"date": row["date"], "count": running})
    return {"cumulative_players": series}


async def dashboard_casual_vs_cedh(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return bucketed counts of started games classified as Casual vs cEDH.

    A game is classified as **cEDH** when any of the following is true:

    * `Game.guild_xid` is in :data:`CEDH_GUILDS`.
    * The owning guild's name contains "cedh" (case-insensitive).
    * `Game.format` is `GameFormat.CEDH` or `GameFormat.EDH_MAX`.
    * `Game.bracket` is `GameBracket.BRACKET_5`.

    All other started games are classified as **Casual**. The dashboard's
    guild filter is honored, so selecting a single server restricts both
    series to games on that server.
    """
    is_cedh = or_(
        any_of(Game.guild_xid, list(CEDH_GUILDS)),
        func.coalesce(Guild.name, "").ilike("%cedh%"),
        Game.format == GameFormat.CEDH.value,
        Game.format == GameFormat.EDH_MAX.value,
        Game.bracket == GameBracket.BRACKET_5.value,
    )
    classification = case((is_cedh, "cedh"), else_="casual").label("classification")

    bucket_col = trunc_date(Game.created_at, period.bucket).label("bucket")
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.created_at >= period.start_dt)

    rows = (
        await DatabaseSession.execute(
            select(classification, bucket_col, func.count(Game.id))
            .select_from(Game)
            .outerjoin(Guild, Guild.xid == Game.guild_xid)  # type: ignore
            .where(*filters)
            .group_by(classification, bucket_col)
            .order_by(bucket_col),
        )
    ).all()

    series: dict[str, list[dict[str, Any]]] = {"casual": [], "cedh": []}
    for kind, bucket, count in rows:
        series[kind].append({"date": iso_str(bucket), "count": int(count)})
    return series


async def dashboard_server_popularity(
    period: PeriodSpec,
    opts: GuildFilter,
    *,
    top_n: int = 20,
    totals_min: int = 10,
) -> dict[str, Any]:
    """
    Return bucketed game counts for the top `top_n` guilds by total games.

    Also returns `totals`: every guild with at least `totals_min` games under
    the same filters, sorted by count descending. The table on the dashboard
    uses this to show all qualifying servers (a superset of those in the chart).
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        Guild.name.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.created_at >= period.start_dt)

    total_col = func.count(Game.id).label("total")
    all_rows = (
        await DatabaseSession.execute(
            select(Guild.name, total_col)
            .select_from(Game)
            .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
            .where(*filters)
            .group_by(Guild.name)
            .order_by(total_col.desc(), Guild.name),
        )
    ).all()
    totals = [{"name": r[0], "count": int(r[1])} for r in all_rows if int(r[1]) >= totals_min]

    top_names = [r[0] for r in all_rows[:top_n]]
    if not top_names:
        return {"series": [], "totals": totals}

    bucket_col = trunc_date(Game.created_at, period.bucket).label("bucket")
    series_rows = (
        await DatabaseSession.execute(
            select(Guild.name, bucket_col, func.count(Game.id))
            .select_from(Game)
            .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
            .where(*filters, any_of(Guild.name, top_names))
            .group_by(Guild.name, bucket_col)
            .order_by(bucket_col),
        )
    ).all()

    by_name: dict[str, list[dict[str, Any]]] = {name: [] for name in top_names}
    for name, bucket, count in series_rows:
        by_name[name].append({"date": iso_str(bucket), "count": int(count)})

    return {
        "series": [{"name": name, "points": by_name[name]} for name in top_names],
        "totals": totals,
    }


async def dashboard_service_popularity(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return bucketed game counts grouped by game service."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.created_at >= period.start_dt)

    bucket_col = trunc_date(Game.created_at, period.bucket).label("bucket")
    rows = (
        await DatabaseSession.execute(
            select(SERVICE_LABEL, bucket_col, func.count(Game.id))
            .where(*filters)
            .group_by(SERVICE_LABEL, bucket_col)
            .order_by(bucket_col),
        )
    ).all()

    by_service: dict[str, list[dict[str, Any]]] = {}
    for service, bucket, count in rows:
        by_service.setdefault(service, []).append(
            {"date": iso_str(bucket), "count": int(count)},
        )
    series = [{"name": name, "points": pts} for name, pts in by_service.items()]
    series.sort(key=lambda s: sum(p["count"] for p in s["points"]), reverse=True)
    return {"series": series}


async def dashboard_user_languages(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return distinct active-user counts grouped by user locale, descending."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    count_col = func.count(distinct(User.xid))
    rows = (
        await DatabaseSession.execute(
            select(User.locale, count_col)
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore
            .join(User, Play.user_xid == User.xid)
            .where(*filters)
            .group_by(User.locale)
            .order_by(count_col.desc(), User.locale),
        )
    ).all()
    return {"rows": [{"locale": row[0], "count": int(row[1])} for row in rows]}


async def dashboard_game_languages(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return counts of started games grouped by game locale, descending."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    count_col = func.count(Game.id)
    rows = (
        await DatabaseSession.execute(
            select(Game.locale, count_col)
            .where(*filters)
            .group_by(Game.locale)
            .order_by(count_col.desc(), Game.locale),
        )
    ).all()
    return {"rows": [{"locale": row[0], "count": int(row[1])} for row in rows]}


async def dashboard_top_guild_per_game_language(
    period: PeriodSpec,
    opts: GuildFilter,
) -> dict[str, Any]:
    """Return the most active guild for each distinct game locale."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        Guild.name.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    count_col = func.count(Game.id)
    rows = (
        await DatabaseSession.execute(
            select(Game.locale, Guild.xid, Guild.name, count_col)  # type: ignore[arg-type]
            .select_from(Game)
            .join(Guild, Guild.xid == Game.guild_xid)
            .where(*filters)
            .group_by(Game.locale, Guild.xid, Guild.name)
            .order_by(Game.locale, count_col.desc(), Guild.name),
        )
    ).all()

    top_by_locale: dict[str, dict[str, Any]] = {}
    for locale, guild_xid, guild_name, count in rows:
        if locale in top_by_locale:
            continue
        top_by_locale[locale] = {
            "locale": locale,
            "guild_xid": str(int(guild_xid)),
            "guild_name": guild_name,
            "count": int(count),
        }
    ordered = sorted(top_by_locale.values(), key=lambda r: (-r["count"], r["locale"]))
    return {"rows": ordered}


async def dashboard_guild_languages(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return distinct active-guild counts grouped by guild locale, descending."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    count_col = func.count(distinct(Guild.xid))  # type: ignore[arg-type]
    rows = (
        await DatabaseSession.execute(
            select(Guild.locale, count_col)
            .select_from(Game)
            .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore[arg-type]
            .where(*filters)
            .group_by(Guild.locale)
            .order_by(count_col.desc(), Guild.locale),
        )
    ).all()
    return {"rows": [{"locale": row[0], "count": int(row[1])} for row in rows]}


async def dashboard_hour_of_day(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return counts of started games per UTC hour of the day (0-23).

    The histogram is computed in UTC; the client shifts the bucket labels
    by the browser's timezone offset to display local hours.
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    hour_col = extract("hour", Game.started_at).label("hour")
    rows = (
        await DatabaseSession.execute(
            select(hour_col, func.count(Game.id))
            .where(*filters)
            .group_by(hour_col)
            .order_by(hour_col),
        )
    ).all()
    counts = {int(h): int(c) for h, c in rows}
    return {"hours": [{"hour": h, "count": counts.get(h, 0)} for h in range(24)]}


async def dashboard_day_of_week(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return counts of started games per UTC day of the week (0=Sun..6=Sat)."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    dow_col = extract("dow", Game.started_at).label("dow")
    rows = (
        await DatabaseSession.execute(
            select(dow_col, func.count(Game.id))
            .where(*filters)
            .group_by(dow_col)
            .order_by(dow_col),
        )
    ).all()
    counts = {int(d): int(c) for d, c in rows}
    return {"days": [{"dow": d, "count": counts.get(d, 0)} for d in range(7)]}


FORMAT_LABEL = case(
    *((Game.format == f.value, str(f)) for f in GAME_FORMAT_ORDER),
    else_="Unknown",
).label("format")


async def dashboard_popular_formats(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return counts of started games grouped by format, descending."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    count_col = func.count(Game.id)
    rows = (
        await DatabaseSession.execute(
            select(FORMAT_LABEL, count_col)
            .where(*filters)
            .group_by(FORMAT_LABEL)
            .order_by(count_col.desc(), FORMAT_LABEL),
        )
    ).all()
    return {"rows": [{"format": row[0], "count": int(row[1])} for row in rows]}


async def dashboard_popular_seats(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return counts of started games grouped by seat count, descending."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    count_col = func.count(Game.id)
    rows = (
        await DatabaseSession.execute(
            select(Game.seats, count_col)  # type: ignore[arg-type]
            .where(*filters)
            .group_by(Game.seats)
            .order_by(count_col.desc(), Game.seats),
        )
    ).all()
    return {"rows": [{"seats": int(row[0]), "count": int(row[1])} for row in rows]}


async def dashboard_bracket_adoption(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return bucketed bracket adoption rate (percent) among bracketable formats.

    Adoption is `count(games where bracket is set) / count(games)` restricted
    to games whose `format` is in `BRACKETABLE_FORMATS` and which have started.

    Also returns `leaders`: one row per non-`NONE` bracket with the guild that
    has the most games of that bracket under the same filters. Brackets with
    no qualifying games are included with `server=None` and `count=0`.
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        Game.format.in_(BRACKETABLE_FORMATS),  # type: ignore[attr-defined]
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.created_at >= period.start_dt)

    bucket_col = trunc_date(Game.created_at, period.bucket).label("bucket")
    adopted = func.sum(case((Game.bracket != GameBracket.NONE.value, 1), else_=0))
    total = func.count(Game.id)
    rows = (
        await DatabaseSession.execute(
            select(bucket_col, adopted.label("adopted"), total.label("total"))
            .where(*filters)
            .group_by(bucket_col)
            .order_by(bucket_col),
        )
    ).all()

    points: list[dict[str, Any]] = []
    for bucket, adopted_count, total_count in rows:
        total_int = int(total_count or 0)
        rate = (float(adopted_count or 0) / float(total_int)) * 100.0 if total_int > 0 else 0.0
        points.append({"date": iso_str(bucket), "count": round(rate, 2)})

    leader_count = func.count(Game.id).label("count")
    leader_rows = (
        await DatabaseSession.execute(
            select(Game.bracket, Guild.name, leader_count)  # type: ignore
            .select_from(Game)
            .join(Guild, Guild.xid == Game.guild_xid)
            .where(
                *filters,
                Game.bracket != GameBracket.NONE.value,
                Guild.name.isnot(None),
            )
            .group_by(Game.bracket, Guild.name),
        )
    ).all()

    best_per_bracket: dict[int, tuple[str, int]] = {}
    for bracket_value, name, count in leader_rows:
        c = int(count)
        b = int(bracket_value)
        cur = best_per_bracket.get(b)
        if cur is None or c > cur[1] or (c == cur[1] and name < cur[0]):
            best_per_bracket[b] = (name, c)

    leaders: list[dict[str, Any]] = []
    for b in GAME_BRACKET_ORDER:
        if b is GameBracket.NONE:
            continue
        winner = best_per_bracket.get(b.value)
        leaders.append(
            {
                "bracket": b.title,
                "server": winner[0] if winner is not None else None,
                "count": winner[1] if winner is not None else 0,
            },
        )
    return {"rate": points, "leaders": leaders}


async def dashboard_avg_wait_time(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return bucketed average wait time (in minutes) between `created_at` and `started_at`."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    bucket_col = trunc_date(Game.started_at, period.bucket).label("bucket")
    avg_col = func.avg(
        extract("epoch", Game.started_at) - extract("epoch", Game.created_at),
    ).label("avg_seconds")
    rows = (
        await DatabaseSession.execute(
            select(bucket_col, avg_col).where(*filters).group_by(bucket_col).order_by(bucket_col),
        )
    ).all()
    return {
        "series": [
            {"date": iso_str(r[0]), "minutes": round(float(r[1] or 0) / 60.0, 1)} for r in rows
        ],
    }


async def dashboard_top_players(
    period: PeriodSpec,
    opts: GuildFilter,
    *,
    top_n: int = 20,
) -> dict[str, Any]:
    """Return the top `top_n` players by number of started games played."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    count_col = func.count(Play.game_id).label("count")  # type: ignore[arg-type]
    rows = (
        await DatabaseSession.execute(
            select(Play.user_xid, User.name, count_col)
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
            .join(User, User.xid == Play.user_xid)
            .where(*filters)
            .group_by(Play.user_xid, User.name)
            .order_by(count_col.desc())
            .limit(top_n),
        )
    ).all()
    return {
        "rows": [
            {"user_xid": str(int(row[0])), "name": row[1], "count": int(row[2])} for row in rows
        ],
    }


async def dashboard_top_blocked(
    period: PeriodSpec,
    opts: GuildFilter,
    *,
    top_n: int = 20,
) -> dict[str, Any]:
    """
    Return the top `top_n` blocked users globally, ordered by block count.

    Blocks are not guild-scoped and do not have a per-period meaning here,
    so both `period` and `opts` are intentionally ignored: the table
    always shows all-time totals across all servers.
    """
    del period, opts
    count_col = func.count(Block.user_xid).label("count")
    rows = (
        await DatabaseSession.execute(
            select(Block.blocked_user_xid, User.name, count_col)
            .select_from(Block)
            .join(User, User.xid == Block.blocked_user_xid)
            .group_by(Block.blocked_user_xid, User.name)
            .order_by(count_col.desc())
            .limit(top_n),
        )
    ).all()
    return {
        "rows": [
            {"user_xid": str(int(row[0])), "name": row[1], "count": int(row[2])} for row in rows
        ],
    }


async def dashboard_games_per_player(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return the games-per-player histogram with the median marked.

    Counts are bucketed 1..20 with an overflow `21+` bucket for tails.
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    rows = (
        await DatabaseSession.execute(
            select(Play.user_xid, func.count(Game.id).label("count"))
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
            .where(*filters)
            .group_by(Play.user_xid),
        )
    ).all()
    counts = sorted(int(r[1]) for r in rows)
    if counts:
        mid = len(counts) // 2
        median = counts[mid] if len(counts) % 2 else (counts[mid - 1] + counts[mid]) / 2
    else:
        median = 0
    freq = Counter(counts)
    cap = 20
    max_count = max(counts) if counts else 0
    histogram = [
        {"bucket": str(i), "players": freq.get(i, 0)} for i in range(1, min(max_count, cap) + 1)
    ]
    if max_count > cap:
        overflow = sum(v for k, v in freq.items() if k > cap)
        histogram.append({"bucket": f"{cap + 1}+", "players": overflow})
    return {"median": median, "histogram": histogram}


async def dashboard_rules(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return the top game rules and bigram / trigram phrases for a word cloud."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        Game.rules.isnot(None),
        Game.rules != "",
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    rules_rows = (await DatabaseSession.execute(select(Game.rules).where(*filters))).all()
    rules_list = [r[0] for r in rules_rows if r[0]]
    rule_counter: Counter[str] = Counter()
    ngram_counter: Counter[str] = Counter()
    for rule in rules_list:
        normalized = normalize_rule(rule)
        if not normalized:
            continue
        rule_counter[normalized] += 1
        for bigram in extract_ngrams(normalized, 2):
            ngram_counter[bigram] += 1
        for trigram in extract_ngrams(normalized, 3):
            ngram_counter[trigram] += 1
    top_rules = [{"rule": rule, "count": count} for rule, count in rule_counter.most_common(20)]
    rule_ngrams = [
        {"phrase": phrase, "count": count} for phrase, count in ngram_counter.most_common(75)
    ]
    return {"top_rules": top_rules, "rule_ngrams": rule_ngrams}


async def dashboard_cohort_retention(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return weekly cohort retention as `cohorts[cohort][week_offset] -> percent`.

    A user's cohort is the week containing their first in-scope
    `Game.started_at`. For each subsequent week, we report the percent of
    that cohort who played at least one game that week. Week offsets are
    integer multiples of 7 days from the cohort start.

    The result includes one cohort row per distinct first-play week within
    the (optional) period bound, ordered ascending by cohort. `max_weeks`
    is the largest week offset seen across all cohorts (>= 0), useful for
    sizing the heatmap on the client.
    """
    inner_filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    first_play = (
        select(
            Play.user_xid.label("user_xid"),
            func.min(func.date_trunc("week", Game.started_at)).label("cohort"),
        )
        .select_from(Play)
        .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
        .where(*inner_filters)
        .group_by(Play.user_xid)
        .subquery()
    )
    play_weeks = (
        select(
            Play.user_xid.label("user_xid"),
            func.date_trunc("week", Game.started_at).label("play_week"),
        )
        .select_from(Play)
        .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
        .where(*inner_filters)
        .distinct()
        .subquery()
    )
    outer_filters: list[ColumnElement[bool]] = []
    if period.start_dt is not None:
        outer_filters.append(first_play.c.cohort >= period.start_dt)
    rows = (
        await DatabaseSession.execute(
            select(
                first_play.c.cohort,
                play_weeks.c.play_week,
                func.count(distinct(play_weeks.c.user_xid)).label("returners"),
            )
            .select_from(first_play)
            .join(play_weeks, first_play.c.user_xid == play_weeks.c.user_xid)
            .where(*outer_filters)
            .group_by(first_play.c.cohort, play_weeks.c.play_week)
            .order_by(first_play.c.cohort, play_weeks.c.play_week),
        )
    ).all()

    grouped: dict[Any, dict[int, int]] = {}
    max_offset = 0
    for cohort_dt, play_week, returners in rows:
        offset = max(0, (play_week - cohort_dt).days // 7)
        grouped.setdefault(cohort_dt, {})[offset] = int(returners)
        max_offset = max(max_offset, offset)

    cohorts: list[dict[str, Any]] = []
    for cohort_dt in sorted(grouped.keys()):
        offsets = grouped[cohort_dt]
        size = offsets[0]
        weeks = [
            {"offset": off, "count": count, "pct": round(100.0 * count / size, 1)}
            for off, count in sorted(offsets.items())
        ]
        cohorts.append({"cohort": iso_str(cohort_dt), "size": size, "weeks": weeks})
    return {"cohorts": cohorts, "max_weeks": max_offset}


async def dashboard_activity_heatmap(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return started-game counts as a `day-of-week x hour-of-day` matrix.

    Counts are computed in UTC; the client shifts hours by the browser's
    timezone offset to produce a local-time heatmap. `dow` follows Postgres'
    `extract('dow', ...)` convention: 0=Sunday .. 6=Saturday.
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    dow_col = extract("dow", Game.started_at).label("dow")
    hour_col = extract("hour", Game.started_at).label("hour")
    rows = (
        await DatabaseSession.execute(
            select(dow_col, hour_col, func.count(Game.id))
            .where(*filters)
            .group_by(dow_col, hour_col)
            .order_by(dow_col, hour_col),
        )
    ).all()
    return {
        "cells": [{"dow": int(r[0]), "hour": int(r[1]), "count": int(r[2])} for r in rows],
    }


async def dashboard_wait_time_distribution(
    period: PeriodSpec,
    opts: GuildFilter,
) -> dict[str, Any]:
    """
    Return bucketed wait-time percentiles (p50 / p95 / p99) in minutes.

    Wait time per game is `started_at - created_at`. Percentiles are
    computed per bucket using Postgres' `percentile_cont` aggregate.
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    bucket_col = trunc_date(Game.started_at, period.bucket).label("bucket")
    wait_seconds = extract("epoch", Game.started_at) - extract("epoch", Game.created_at)
    p50 = func.percentile_cont(0.5).within_group(wait_seconds).label("p50")
    p95 = func.percentile_cont(0.95).within_group(wait_seconds).label("p95")
    p99 = func.percentile_cont(0.99).within_group(wait_seconds).label("p99")
    rows = (
        await DatabaseSession.execute(
            select(bucket_col, p50, p95, p99)
            .where(*filters)
            .group_by(bucket_col)
            .order_by(bucket_col),
        )
    ).all()

    def to_minutes(value: Any) -> float:
        return round(float(value) / 60.0, 1)

    return {
        "p50": [{"date": iso_str(r[0]), "minutes": to_minutes(r[1])} for r in rows],
        "p95": [{"date": iso_str(r[0]), "minutes": to_minutes(r[2])} for r in rows],
        "p99": [{"date": iso_str(r[0]), "minutes": to_minutes(r[3])} for r in rows],
    }


def bucketed_adoption_rate(
    period: PeriodSpec,
    filters: list[ColumnElement[bool]],
    adopted_predicate: ColumnElement[bool],
) -> Any:
    """Build a `(bucket, adopted_pct)` query for a started-game adoption rate."""
    bucket_col = trunc_date(Game.started_at, period.bucket).label("bucket")
    adopted = func.sum(case((adopted_predicate, 1), else_=0))
    total = func.count(Game.id)
    return (
        select(bucket_col, adopted.label("adopted"), total.label("total"))
        .where(*filters)
        .group_by(bucket_col)
        .order_by(bucket_col)
    )


def adoption_points(rows: Any) -> list[dict[str, Any]]:
    """Convert `(bucket, adopted, total)` rows into `{date, count}` percent points."""
    points: list[dict[str, Any]] = []
    for bucket, adopted, total in rows:
        rate = (float(adopted) / float(total)) * 100.0
        points.append({"date": iso_str(bucket), "count": round(rate, 2)})
    return points


async def dashboard_voice_adoption(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return bucketed adoption rate (percent) of started games with a voice channel."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    rows = (
        await DatabaseSession.execute(
            bucketed_adoption_rate(period, filters, Game.voice_xid.isnot(None)),
        )
    ).all()
    return {"rate": adoption_points(rows)}


async def dashboard_blind_adoption(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """Return bucketed adoption rate (percent) of started games created as blind."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    rows = (
        await DatabaseSession.execute(
            bucketed_adoption_rate(period, filters, Game.blind.is_(True)),
        )
    ).all()
    return {"rate": adoption_points(rows)}


async def dashboard_mythic_verification(
    period: PeriodSpec,
    opts: GuildFilter,
) -> dict[str, Any]:
    """
    Return bucketed Mythic Track verification rate (percent) of plays.

    Restricted to plays on games whose guild has `enable_mythic_track`
    enabled; a play counts as verified when its `verified_at` is set.
    Honors the dashboard's guild filter so a single server can be inspected.
    """
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        Guild.enable_mythic_track.is_(True),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.started_at >= period.start_dt)
    bucket_col = trunc_date(Game.started_at, period.bucket).label("bucket")
    verified = func.sum(case((Play.verified_at.isnot(None), 1), else_=0))
    total = func.count(Play.game_id)  # type: ignore[arg-type]
    rows = (
        await DatabaseSession.execute(
            select(bucket_col, verified.label("verified"), total.label("total"))
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore[arg-type]
            .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore[arg-type]
            .where(*filters)
            .group_by(bucket_col)
            .order_by(bucket_col),
        )
    ).all()
    return {"rate": adoption_points(rows)}


async def dashboard_queue_depth(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return the current number of users waiting in pending games, by format.

    Pending = `Game.started_at IS NULL AND Game.deleted_at IS NULL`. The
    `period` argument is ignored (this is a real-time gauge); `opts` is
    honored so a single server can be inspected.
    """
    del period
    filters: list[ColumnElement[bool]] = [
        Game.started_at.is_(None),
        Game.deleted_at.is_(None),
        *game_guild_filter(opts),
    ]
    total = int(
        (
            await DatabaseSession.execute(
                select(func.count(Queue.user_xid))
                .select_from(Queue)
                .join(Game, Queue.game_id == Game.id)
                .where(*filters),
            )
        ).scalar_one(),
    )
    count_col = func.count(Queue.user_xid).label("count")
    rows = (
        await DatabaseSession.execute(
            select(FORMAT_LABEL, count_col)
            .select_from(Queue)
            .join(Game, Queue.game_id == Game.id)
            .where(*filters)
            .group_by(FORMAT_LABEL)
            .order_by(count_col.desc(), FORMAT_LABEL),
        )
    ).all()
    return {
        "total": total,
        "by_format": [{"format": row[0], "count": int(row[1])} for row in rows],
    }
