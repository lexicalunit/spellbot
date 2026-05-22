from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, distinct, extract, func, or_, select

from spellbot.database import DatabaseSession, any_of
from spellbot.enums import GAME_FORMAT_ORDER, GameBracket, GameFormat, GameService
from spellbot.models import Block, Game, Guild, Play, User
from spellbot.services.plays import extract_ngrams, normalize_rule

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

# Curated guild classification lists used by `dashboard_casual_vs_cedh`.
# These mirror the lists in the historical Grafana dashboard and are
# intentionally imperfect: some servers host both casual and competitive play.
# In addition to the lists, games marked `GameFormat.CEDH` or
# `GameBracket.BRACKET_5` are always counted as cEDH regardless of guild.
CASUAL_GUILDS: frozenset[int] = frozenset(
    {
        304276578005942272,  # PlayEDH
        574711449566445603,  # TCC
        531209216443154443,  # Nitpicking Nerds
        815001383979450368,  # EDH Fight Club
        793590120049672242,  # IHYD
        750696719905456189,  # Tambayan
        752261529390284870,  # DE
        840959507747569715,  # Combat Step
        817867020837584906,  # CTC
        757455940009328670,  # Gaywatch
        1229388601113051198,  # Fight Club Royal
        924643928844673045,  # Turbo
        1176073262078378004,  # Breakfast Club
        689674672240984067,  # MTG@Home
    },
)
CEDH_GUILDS: frozenset[int] = frozenset(
    {
        113555415446413312,  # Competitive EDH
        1321026027337547817,  # CriticalEDH
        1225118416298315857,  # r/cEDH Discord
        682734915846275184,  # Play to Win
        530219227924267008,  # PWP
        954838268275470367,  # ka0s Tournaments
        763138565231345665,  # WreckRoomCedh
        1206898724266319882,  # Espanola cEDH
        1036729704180355202,  # Training Grounds
        799686008811290626,  # cEDH PT
        1061492498402394132,  # cEDH Training Grounds
        966025312368463922,  # cEDH DE
        629303378685460530,  # AUS cEDH
        1110129065152745505,  # UK cEDH
        749653914839679057,  # cEDH Quebec
        947983400483033148,  # PDX cEDH
    },
)

if TYPE_CHECKING:
    from sqlalchemy.sql import ColumnElement

    from spellbot.web.dashboard_filters import GuildFilter, PeriodSpec


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
    """
    Return the headline totals shown across the top of the dashboard.

    Games and players are restricted by `period` and `opts`. The `servers` count
    reflects guilds whose `updated_at` falls within the period; this metric is global
    and intentionally ignores the guild filter.
    """
    game_filters = [Game.started_at.isnot(None), *game_guild_filter(opts)]
    if period.start_dt is not None:
        game_filters.append(Game.started_at >= period.start_dt)

    games = int(
        (await DatabaseSession.execute(select(func.count(Game.id)).where(*game_filters))).scalar()
        or 0,
    )

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


async def dashboard_casual_vs_cedh(period: PeriodSpec, opts: GuildFilter) -> dict[str, Any]:
    """
    Return bucketed counts of started games classified as Casual vs cEDH.

    Classification mirrors the historical Grafana dashboard:

    * **Casual** — games in :data:`CASUAL_GUILDS` whose `format` is not
      `GameFormat.CEDH` and whose `bracket` is not `GameBracket.BRACKET_5`.
    * **cEDH** — games in :data:`CEDH_GUILDS`, OR any game whose `format` is
      `GameFormat.CEDH`, OR any game whose `bracket` is
      `GameBracket.BRACKET_5`.

    The classification is global and intentionally ignores the dashboard's
    guild filter; `opts` is accepted for API symmetry. Games outside both
    lists (and without the cEDH format/bracket markers) are not counted in
    either series.
    """
    del opts
    cedh_format = GameFormat.CEDH.value
    cedh_bracket = GameBracket.BRACKET_5.value
    casual_clause = and_(
        any_of(Game.guild_xid, list(CASUAL_GUILDS)),
        Game.format != cedh_format,
        Game.bracket != cedh_bracket,
    )
    cedh_clause = or_(
        any_of(Game.guild_xid, list(CEDH_GUILDS)),
        Game.format == cedh_format,
        Game.bracket == cedh_bracket,
    )

    bucket_col = trunc_date(Game.created_at, period.bucket).label("bucket")
    common: list[ColumnElement[bool]] = [Game.started_at.isnot(None)]
    if period.start_dt is not None:
        common.append(Game.created_at >= period.start_dt)

    async def run(clause: ColumnElement[bool]) -> list[dict[str, Any]]:
        rows = (
            await DatabaseSession.execute(
                select(bucket_col, func.count(Game.id))
                .where(*common, clause)
                .group_by(bucket_col)
                .order_by(bucket_col),
            )
        ).all()
        return [{"date": iso_str(r[0]), "count": int(r[1])} for r in rows]

    return {
        "casual": await run(casual_clause),
        "cedh": await run(cedh_clause),
    }


async def dashboard_server_popularity(
    period: PeriodSpec,
    opts: GuildFilter,
    *,
    top_n: int = 20,
) -> dict[str, Any]:
    """Return bucketed game counts for the top `top_n` guilds by total games."""
    filters: list[ColumnElement[bool]] = [
        Game.started_at.isnot(None),
        Guild.name.isnot(None),
        *game_guild_filter(opts),
    ]
    if period.start_dt is not None:
        filters.append(Game.created_at >= period.start_dt)

    top_rows = (
        await DatabaseSession.execute(
            select(Guild.name, func.count(Game.id).label("total"))
            .select_from(Game)
            .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
            .where(*filters)
            .group_by(Guild.name)
            .order_by(func.count(Game.id).desc())
            .limit(top_n),
        )
    ).all()
    top_names = [r[0] for r in top_rows]
    if not top_names:
        return {"series": []}

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

    return {"series": [{"name": name, "points": by_name[name]} for name in top_names]}


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
    return {"rate": points}


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
