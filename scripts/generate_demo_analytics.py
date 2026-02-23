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


def generate_fake_data() -> dict[str, Any]:  # noqa: PLR0915
    """Generate realistic-looking fake analytics data."""
    today = datetime.now(tz=UTC).date()
    thirty_days_ago = today - timedelta(days=30)

    # Generate daily data for last 30 days
    days = [(thirty_days_ago + timedelta(days=i)).isoformat() for i in range(31)]

    # Games per day - realistic curve with weekends higher
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

    # Total stats
    total_games = sum(d["count"] for d in games_per_day) + random.randint(5000, 15000)
    total_expired = sum(d["count"] for d in expired_per_day) + random.randint(500, 2000)
    fill_rate = round(100 * total_games / (total_games + total_expired), 1)
    unique_players = random.randint(2000, 5000)
    monthly_active_users = random.randint(400, 800)
    repeat_player_rate = round(random.uniform(45, 75), 1)

    # Average wait time per day
    avg_wait_per_day = [{"day": day, "minutes": round(random.uniform(2, 15), 1)} for day in days]

    # Games by bracket per day
    brackets = [
        "None",
        "Bracket 1: Exhibition",
        "Bracket 2: Core",
        "Bracket 3: Upgraded",
        "Bracket 4: Optimized",
        "Bracket 5: Competitive",
    ]
    games_by_bracket_per_day = []
    for day in days:
        for bracket in brackets:
            if bracket == "None":
                count = random.randint(20, 50)
            elif bracket in ("Bracket 2: Core", "Bracket 3: Upgraded"):
                count = random.randint(10, 30)
            else:
                count = random.randint(2, 15)
            games_by_bracket_per_day.append({"day": day, "bracket": bracket, "count": count})

    # Player retention (12 weeks)
    twelve_weeks = [(today - timedelta(weeks=i)).isoformat() for i in range(12, 0, -1)]
    player_retention = [
        {"week": week, "new": random.randint(30, 80), "returning": random.randint(150, 350)}
        for week in twelve_weeks
    ]

    # Cumulative player growth (over ~2 years)
    growth_start = today - timedelta(days=730)
    cumulative_players = []
    running_total = 0
    for i in range(0, 730, 7):  # Weekly samples
        day = (growth_start + timedelta(days=i)).isoformat()
        running_total += random.randint(20, 60)
        cumulative_players.append({"day": day, "total": running_total})

    # Games histogram
    games_histogram = [{"bucket": str(i), "players": int(1000 / (i**0.8))} for i in range(1, 21)]
    games_histogram.append({"bucket": "21+", "players": 45})
    median_games = 3

    # Popular formats
    formats = ["Commander", "Standard", "Modern", "Legacy", "Pioneer", "Pauper", "Vintage", "Draft"]
    popular_formats = [
        {
            "format": fmt,
            "count": random.randint(100, 5000) if fmt == "Commander" else random.randint(50, 800),
        }
        for fmt in formats
    ]
    popular_formats.sort(key=lambda x: x["count"], reverse=True)

    # Busiest channels
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
    busiest_channels = [
        {"name": name, "count": random.randint(200, 3000)} for name in channel_names
    ]
    busiest_channels.sort(key=lambda x: x["count"], reverse=True)

    # Popular services
    popular_services = [
        {"service": "Convoke", "count": random.randint(8000, 12000)},
        {"service": "SpellTable", "count": random.randint(3000, 6000)},
    ]
    popular_services_30d = [
        {"service": "Convoke", "count": random.randint(800, 1200)},
        {"service": "SpellTable", "count": random.randint(200, 500)},
    ]

    # Top players
    def gen_players(count_range: tuple[int, int]):
        return [
            {
                "user_xid": str(random.randint(100000000000000000, 999999999999999999)),
                "name": fake.user_name(),
                "count": random.randint(*count_range),
            }
            for _ in range(10)
        ]

    top_players = sorted(gen_players((50, 500)), key=lambda x: x["count"], reverse=True)
    top_players_30d = sorted(gen_players((10, 80)), key=lambda x: x["count"], reverse=True)

    return {
        "guild_name": "Planeswalker's Guild",
        "total_games": total_games,
        "fill_rate": fill_rate,
        "unique_players": unique_players,
        "monthly_active_users": monthly_active_users,
        "repeat_player_rate": repeat_player_rate,
        "games_per_day": games_per_day,
        "avg_wait_per_day": avg_wait_per_day,
        "expired_per_day": expired_per_day,
        "daily_new_users": daily_new_users,
        "games_by_hour": [],
        "expired_by_hour": [],
        "new_users_by_hour": [],
        "games_by_bracket_per_day": games_by_bracket_per_day,
        "player_retention": player_retention,
        "cumulative_players": cumulative_players,
        "median_games": median_games,
        "games_histogram": games_histogram,
        "popular_formats": popular_formats,
        "busiest_channels": busiest_channels,
        "popular_services": popular_services,
        "popular_services_30d": popular_services_30d,
        "top_players": top_players,
        "top_players_30d": top_players_30d,
    }


def generate_html(data: dict[str, Any]) -> str:
    """Generate the static HTML with embedded data."""
    # Read the template
    template_path = Path(__file__).parent.parent / "src/spellbot/web/templates/analytics.html.j2"
    template = template_path.read_text()

    # Replace Jinja2 variables for the shell page
    guild_name = data["guild_name"]
    html = template.replace("{{ guild_name }}", guild_name)

    # For the demo, we don't need signature/expiration - embed data directly
    # Remove the countdown since it's a static page
    html = html.replace(
        '<div class="expires">Expires in <span id="countdown"></span></div>',
        (
            '<div class="expires" style="background:#1e3a5f">'
            '<span style="color:#60a5fa">Demo Mode</span></div>'
        ),
    )

    # Replace the AJAX fetch with inline data
    data_json = json.dumps(data, indent=2)

    # Find the fetch section by markers instead of hardcoding the exact string
    start_marker = "/* ── Fetch data via AJAX ── */"
    end_marker = "});"
    start_idx = html.find(start_marker)
    end_idx = html.find(end_marker, start_idx) + len(end_marker)

    assert start_idx != -1, "Could not find fetch start marker"

    inline_script = f"""/* ── Demo data loaded inline ── */
    (function() {{
        const data = {data_json};
        renderCharts(data);
        document.getElementById("mainContainer").classList.add("loaded");
        document.getElementById("loadingOverlay").classList.add("hidden");
    }})();"""

    html = html[:start_idx] + inline_script + html[end_idx:]

    # Remove the DATA_URL and EXPIRES constants (not needed for static)
    config_script = (
        "/* ── Config from server ── */\n"
        '    const DATA_URL = "/g/{{ guild_xid }}/analytics/data?'
        'expires={{ expires }}&sig={{ sig }}";\n'
        "    const EXPIRES = {{ expires }};"
    )
    html = html.replace(config_script, "/* ── Demo mode - data embedded inline ── */")

    # Remove countdown timer (it references EXPIRES)
    countdown_script = """/* ── Countdown timer ── */
    (function() {
        const el = document.getElementById("countdown");
        function tick() {
            const left = Math.max(0, EXPIRES - Math.floor(Date.now() / 1000));
            const m = Math.floor(left / 60);
            const s = left % 60;
            el.textContent = m + ":" + (s < 10 ? "0" : "") + s;
            if (left <= 0) { el.textContent = "expired"; return; }
            requestAnimationFrame(tick);
        }
        tick(); setInterval(tick, 1000);
    })();"""
    return html.replace(countdown_script, "/* Countdown disabled for demo */")


def main() -> None:
    """Generate the demo analytics page."""
    data = generate_fake_data()
    html = generate_html(data)
    output_path = Path(__file__).parent.parent / "demo_analytics.html"
    output_path.write_text(html)


if __name__ == "__main__":
    main()
