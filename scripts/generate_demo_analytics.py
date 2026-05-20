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
    active_players = random.randint(400, 800) if period == "30d" else random.randint(2000, 5000)
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

    # Hour of day
    games_by_hour = [{"hour": h, "count": random.randint(20, 200)} for h in range(24)]
    # Make evening hours more popular
    for h in range(18, 23):
        games_by_hour[h]["count"] = random.randint(150, 300)

    # Day of week
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    games_by_day = [
        {"day": day, "count": random.randint(200, 400) if i >= 5 else random.randint(100, 250)}
        for i, day in enumerate(day_names)
    ]

    # Channel players (unique players per channel)
    channel_players = sorted(
        [{"name": name, "players": random.randint(50, 500)} for name in channel_names],
        key=lambda x: x["players"],
        reverse=True,
    )

    # Rules
    rule_phrases = [
        "no proxies",
        "proxies ok",
        "no mox",
        "mox ok",
        "rule 0 discussion",
        "casual only",
        "no infinites",
        "infinites ok",
        "no stax",
        "webcam required",
    ]
    top_rules = sorted(
        [{"rule": rule, "count": random.randint(50, 800)} for rule in rule_phrases],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    ngram_phrases = [
        "no proxies",
        "proxies ok",
        "no mox",
        "mox ok",
        "rule 0",
        "casual games",
        "no infinites",
        "infinites allowed",
        "webcam on",
        "mic required",
        "chill vibes",
        "competitive ok",
        "budget decks",
        "no stax",
        "stax ok",
        "precons only",
        "upgraded precons",
        "high power",
        "low power",
        "mid power",
    ]
    rule_ngrams = [{"phrase": phrase, "count": random.randint(10, 500)} for phrase in ngram_phrases]

    # Languages
    locales = ["en-US", "en-GB", "es-ES", "pt-BR", "de", "fr", "ja", "ko", "it", "pl"]
    top_languages = sorted(
        [
            {
                "locale": loc,
                "count": random.randint(500, 8000) if loc == "en-US" else random.randint(20, 800),
            }
            for loc in locales
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return {
        "summary": {
            "total_games": total_games,
            "fill_rate": fill_rate,
            "active_players": active_players,
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
        "hour-of-day": {"games_by_hour": games_by_hour},
        "day-of-week": {"games_by_day": games_by_day},
        "formats": {"popular_formats": popular_formats},
        "channels": {"busiest_channels": busiest_channels},
        "channel-players": {"channel_players": channel_players},
        "services": {"popular_services": popular_services},
        "players": {"top_players": top_players},
        "blocked": {"top_blocked": top_blocked},
        "rules": {"top_rules": top_rules, "rule_ngrams": rule_ngrams},
        "languages": {"top_languages": top_languages},
    }


def generate_html(data_30d: dict[str, Any], data_all: dict[str, Any]) -> str:
    """
    Generate the static HTML with embedded data for both periods.

    Strategy: Keep the JS file unmodified. Instead:
    1. Provide window.ANALYTICS_CONFIG so the JS initializes
    2. Override window.fetch to return demo data instead of making network requests
    3. Hide the countdown timer via CSS (it will show "expired" but that's fine)
    """
    template_path = Path(__file__).parent.parent / "src/spellbot/web/templates/analytics.html.j2"
    js_path = Path(__file__).parent.parent / "src/spellbot/web/templates/analytics.js"
    template = template_path.read_text()
    js_content = js_path.read_text()

    # Replace Jinja2 variables
    html = template.replace("{{ guild_name }}", "Planeswalker's Guild")

    # Replace the "Expires in" countdown with "Demo Mode" indicator
    # Keep a hidden countdown span so the JS timer doesn't crash
    html = html.replace(
        '<div class="expires">Expires in <span id="countdown"></span></div>',
        '<div class="expires" style="background:#1e3a5f">'
        '<span style="color:#60a5fa">Demo Mode</span>'
        '<span id="countdown" style="display:none"></span></div>',
    )

    # Build demo data JSON
    demo_data = {"30d": data_30d, "all": data_all}
    demo_data_json = json.dumps(demo_data)

    # Create the demo bootstrap script that:
    # 1. Sets up ANALYTICS_CONFIG
    # 2. Sets CHART_AVAILABLE flag
    # 3. Overrides fetch() to return demo data
    demo_bootstrap = f"""<script>
    // Demo mode: provide config and override fetch
    window.ANALYTICS_CONFIG = {{
        baseUrl: "/demo/analytics",
        query: "?demo=true",
        expires: Math.floor(Date.now() / 1000) + 3600  // 1 hour from now
    }};

    // Check if Chart.js loaded successfully
    window.CHART_AVAILABLE = typeof Chart !== 'undefined';

    // Pre-loaded demo data
    const DEMO_DATA = {demo_data_json};

    // Override fetch to return demo data
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {{
        // Extract endpoint name from URL (e.g., "/demo/analytics/summary" -> "summary")
        const match = url.match(/\\/analytics\\/([^?]+)/);
        if (match) {{
            const endpoint = match[1];
            // Extract period from URL params
            const urlParams = new URLSearchParams(url.split('?')[1] || '');
            const period = urlParams.get('period') || '30d';
            const data = DEMO_DATA[period]?.[endpoint];
            if (data) {{
                return Promise.resolve({{
                    ok: true,
                    json: () => Promise.resolve(data)
                }});
            }}
        }}
        // Fall back to original fetch for other requests (like Chart.js CDN)
        return originalFetch.apply(this, arguments);
    }};
    </script>"""

    # Replace the config script block with our demo bootstrap
    config_start = html.find("/* Config passed to external analytics.js */")
    config_end = html.find("</script>", config_start) + len("</script>")
    html = html[: config_start - len("    <script>\n")] + demo_bootstrap + html[config_end:]

    # Replace external JS reference with inline JS (to work as a standalone file)
    return html.replace(
        '<script src="/analytics.js"></script>',
        f"<script>\n{js_content}\n    </script>",
    )


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
