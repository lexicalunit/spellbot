#!/usr/bin/env python3
"""Generate a static demo analytics HTML page with fake data."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)


def generate_daily_data(
    days: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate daily games, expired, and new users data."""
    games_per_day = []
    expired_per_day = []
    daily_new_users = []
    for day_str in days:
        d = datetime.fromisoformat(day_str).date()
        is_weekend = d.weekday() >= 5
        base = random.randint(80, 150) if is_weekend else random.randint(40, 100)
        games_per_day.append({"day": day_str, "count": base})
        expired_per_day.append({"day": day_str, "count": random.randint(5, 25)})
        daily_new_users.append({"day": day_str, "count": random.randint(3, 20)})
    return games_per_day, expired_per_day, daily_new_users


def generate_brackets_data(days: list[str]) -> list[dict[str, Any]]:
    """Generate games by bracket per day."""
    brackets = [
        "None",
        "Bracket 1: Exhibition",
        "Bracket 2: Core",
        "Bracket 3: Upgraded",
        "Bracket 4: Optimized",
        "Bracket 5: Competitive",
    ]
    result = []
    for day in days:
        for bracket in brackets:
            if bracket == "None":
                count = random.randint(20, 50)
            elif bracket in ("Bracket 2: Core", "Bracket 3: Upgraded"):
                count = random.randint(10, 30)
            else:
                count = random.randint(2, 15)
            result.append({"day": day, "bracket": bracket, "count": count})
    return result


def generate_retention_data(weeks: list[str]) -> list[dict[str, Any]]:
    """Generate player retention data."""
    return [
        {"week": week, "new": random.randint(30, 80), "returning": random.randint(150, 350)}
        for week in weeks
    ]


def generate_endpoint_data(period: str) -> dict[str, Any]:
    """Generate data for all endpoints for a given period (30d or all)."""
    today = datetime.now(tz=UTC).date()

    if period == "30d":
        start = today - timedelta(days=30)
        days = [(start + timedelta(days=i)).isoformat() for i in range(31)]
        weeks = [(today - timedelta(weeks=i)).isoformat() for i in range(12, 0, -1)]
        growth_days = 90
    else:  # all time - 2 years of data
        start = today - timedelta(days=730)
        days = [(start + timedelta(days=i)).isoformat() for i in range(731)]
        weeks = [(today - timedelta(weeks=i)).isoformat() for i in range(104, 0, -1)]
        growth_days = 730

    # Activity data
    games_per_day, expired_per_day, daily_new_users = generate_daily_data(days)

    # Summary stats
    total_games = sum(d["count"] for d in games_per_day)
    total_expired = sum(d["count"] for d in expired_per_day)
    fill_rate = round(100 * total_games / (total_games + total_expired), 1)
    unique_players = random.randint(2000, 5000) if period == "30d" else random.randint(15000, 25000)
    monthly_active_users = random.randint(400, 800)
    repeat_player_rate = round(random.uniform(45, 75), 1)

    # Wait time
    avg_wait_per_day = [{"day": day, "minutes": round(random.uniform(2, 15), 1)} for day in days]

    # Brackets
    games_by_bracket_per_day = generate_brackets_data(days)

    # Retention
    player_retention = generate_retention_data(weeks)

    # Growth
    growth_start = today - timedelta(days=growth_days)
    cumulative_players = []
    running_total = 0
    step = 7 if period == "30d" else 14
    for i in range(0, growth_days, step):
        day = (growth_start + timedelta(days=i)).isoformat()
        running_total += random.randint(20, 60)
        cumulative_players.append({"day": day, "total": running_total})

    # Histogram
    games_histogram = [{"bucket": str(i), "players": int(1000 / (i**0.8))} for i in range(1, 21)]
    games_histogram.append({"bucket": "21+", "players": 45})
    median_games = 3

    # Formats
    formats = ["Commander", "Standard", "Modern", "Legacy", "Pioneer", "Pauper", "Vintage", "Draft"]
    popular_formats = sorted(
        [
            {
                "format": fmt,
                "count": random.randint(100, 5000)
                if fmt == "Commander"
                else random.randint(50, 800),
            }
            for fmt in formats
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    # Channels
    channel_names = [
        "lfg-edh",
        "looking-for-game",
        "commander-games",
        "cedh-queue",
        "casual-edh",
        "standard-queue",
        "modern-games",
        "legacy-lfg",
        "pauper-games",
        "events",
    ]
    busiest_channels = sorted(
        [{"name": name, "count": random.randint(200, 3000)} for name in channel_names],
        key=lambda x: x["count"],
        reverse=True,
    )

    # Services
    popular_services = [
        {"service": "Convoke", "count": random.randint(800, 12000)},
        {"service": "SpellTable", "count": random.randint(200, 6000)},
    ]

    # Players
    top_players = sorted(
        [
            {
                "user_xid": str(random.randint(100000000000000000, 999999999999999999)),
                "name": fake.user_name(),
                "count": random.randint(10, 500),
            }
            for _ in range(10)
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    # Blocked
    top_blocked = sorted(
        [
            {
                "user_xid": str(random.randint(100000000000000000, 999999999999999999)),
                "name": fake.user_name(),
                "count": random.randint(1, 15),
            }
            for _ in range(10)
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "summary": {
            "total_games": total_games,
            "fill_rate": fill_rate,
            "unique_players": unique_players,
            "monthly_active_users": monthly_active_users,
            "repeat_player_rate": repeat_player_rate,
        },
        "activity": {
            "games_per_day": games_per_day,
            "expired_per_day": expired_per_day,
            "daily_new_users": daily_new_users,
        },
        "wait-time": {"avg_wait_per_day": avg_wait_per_day},
        "brackets": {"games_by_bracket_per_day": games_by_bracket_per_day},
        "retention": {"player_retention": player_retention},
        "growth": {"cumulative_players": cumulative_players},
        "histogram": {"games_histogram": games_histogram, "median_games": median_games},
        "formats": {"popular_formats": popular_formats},
        "channels": {"busiest_channels": busiest_channels},
        "services": {"popular_services": popular_services},
        "players": {"top_players": top_players},
        "blocked": {"top_blocked": top_blocked},
    }


def generate_html(data_30d: dict[str, Any], data_all: dict[str, Any]) -> str:
    """Generate the static HTML with embedded data for both periods."""
    # Read the template
    template_path = Path(__file__).parent.parent / "src/spellbot/web/templates/analytics.html.j2"
    template = template_path.read_text()

    # Replace Jinja2 variables for the shell page
    html = template.replace("{{ guild_name }}", "Planeswalker's Guild")

    # Replace the "Expires in" countdown with "Demo Mode" indicator
    html = html.replace(
        '<div class="expires">Expires in <span id="countdown"></span></div>',
        '<div class="expires" style="background:#1e3a5f">'
        '<span style="color:#60a5fa">Demo Mode</span></div>',
    )

    # Replace the config section with demo data cache
    config_marker = "/* ── Config from server ── */"
    config_end = "const EXPIRES = {{ expires }};"
    config_start = html.find(config_marker)
    config_end_idx = html.find(config_end, config_start) + len(config_end)

    data_cache_json = json.dumps({"30d": data_30d, "all": data_all})
    demo_config = f"""/* ── Demo mode - data pre-loaded ── */
    const BASE_URL = "";  // Not used in demo
    const QUERY = "";     // Not used in demo
    const DEMO_DATA = {data_cache_json};"""

    html = html[:config_start] + demo_config + html[config_end_idx:]

    # Remove the countdown timer section
    countdown_start = html.find("/* ── Countdown timer ── */")
    countdown_end = html.find("})();", countdown_start) + len("})();")
    html = html[:countdown_start] + "/* Countdown disabled for demo */" + html[countdown_end:]

    # Replace fetchEndpoint to use cached data instead of network
    # Find the function start
    fetch_marker = "function fetchEndpoint({ name, sectionId, render }) {"
    fetch_start = html.find(fetch_marker)

    # Find the next function definition to know where this function ends
    next_function_marker = "function refreshAll()"
    fetch_end = html.find(next_function_marker, fetch_start)

    demo_fetch = """function fetchEndpoint({ name, sectionId, render }) {
        // Demo mode: use pre-loaded data from DEMO_DATA
        const cache = dataCache[currentPeriod];
        if (cache[name]) {
            render(cache[name]);
            return;
        }
        // Load from embedded demo data
        const demoData = DEMO_DATA[currentPeriod][name];
        if (demoData) {
            dataCache[currentPeriod][name] = demoData;
            render(demoData);
        } else {
            showError(sectionId, "No demo data");
        }
    }

    """

    return html[:fetch_start] + demo_fetch + html[fetch_end:]


def main() -> None:
    """Generate the demo analytics page."""
    # Reset seeds for consistent data
    Faker.seed(42)
    random.seed(42)
    data_30d = generate_endpoint_data("30d")

    # Reset seeds again for different but consistent "all time" data
    Faker.seed(123)
    random.seed(123)
    data_all = generate_endpoint_data("all")

    html = generate_html(data_30d, data_all)
    output_path = Path(__file__).parent.parent / "demo_analytics.html"
    output_path.write_text(html)
    print(f"Generated: {output_path}")  # noqa: T201


if __name__ == "__main__":
    main()
