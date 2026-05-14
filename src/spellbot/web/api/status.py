from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aiohttp_jinja2
from aiohttp import web
from ddtrace.trace import tracer
from packaging.version import parse as parse_version

from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.shard_status import ShardStatus, get_all_shard_statuses

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# GitHub repository for building release URLs
GITHUB_REPO_URL = "https://github.com/lexicalunit/spellbot"

# Mapping from indicator to (html_status, description)
STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    "unknown": ("unknown", "Status Unknown"),
    "maintenance": ("upgrading", "Upgrade In Progress"),
    "operational": ("healthy", "All Systems Operational"),
    "degraded": ("degraded", "Degraded Performance"),
    "outage": ("down", "Major Outage"),
}


def version_release_url(version: str | None) -> str | None:
    """
    Return the GitHub release page URL for a given version, or None if unavailable.

    The release page shows the release notes and a "Full Changelog" link diffing
    against the previous tag.
    """
    if not version or version == "unknown":
        return None
    return f"{GITHUB_REPO_URL}/releases/tag/v{version}"


@dataclass
class ShardData:
    """Shard status data."""

    shard_id: int
    latency_ms: float | None
    guild_count: int
    is_ready: bool
    last_updated: str
    version: str


@dataclass
class StatusData:
    """Computed status data shared by HTML and JSON endpoints."""

    indicator: str
    total_shards: int
    ready_shards: int
    total_guilds: int
    shards: list[ShardData]
    version: str | None
    upgrade_in_progress: bool
    last_updated: str | None


def format_latency(latency_ms: float | None) -> str:
    """Format latency for display."""
    if latency_ms is None:
        return "N/A"
    return f"{latency_ms:.1f}ms"


def format_time_ago(iso_timestamp: str) -> str:
    """Format a timestamp as 'X seconds/minutes ago'."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        now = datetime.now(tz=UTC)
        delta = now - dt
        seconds = int(delta.total_seconds())

        if seconds < 60:
            result = f"{seconds}s ago"
        elif seconds < 3600:
            minutes = seconds // 60
            result = f"{minutes}m ago"
        else:
            hours = seconds // 3600
            result = f"{hours}h ago"
    except Exception:
        return "unknown"
    else:
        return result


def get_latency_class(latency_ms: float | None) -> str:
    """Get CSS class based on latency value."""
    if latency_ms is None:
        return "latency-unknown"
    if latency_ms < 100:
        return "latency-good"
    if latency_ms < 250:
        return "latency-ok"
    return "latency-bad"


def get_int(metadata: dict[str, Any], key: str, default: int = 0) -> int:
    """Safely extract an int from metadata."""
    val = metadata.get(key, default)
    if isinstance(val, int):
        return val
    return int(str(val)) if val is not None else default


def get_str(metadata: dict[str, Any], key: str) -> str | None:
    """Safely extract a string from metadata."""
    val = metadata.get(key)
    return str(val) if val is not None else None


def compute_status(
    statuses: list[ShardStatus],
    metadata: dict[str, Any] | None,
) -> StatusData:
    """Compute overall status and shard data."""
    total_shards = get_int(metadata, "shard_count") if metadata else 0
    ready_shards = sum(1 for s in statuses if s.is_ready)
    total_guilds = get_int(metadata, "total_guilds") if metadata else 0
    version = get_str(metadata, "version") if metadata else None
    last_updated = get_str(metadata, "last_updated") if metadata else None

    # Detect if upgrade is in progress
    shard_versions = {s.version for s in statuses if s.version != "unknown"}
    upgrade_in_progress = len(shard_versions) > 1

    # Determine overall status indicator
    if not statuses:
        indicator = "unknown"
    elif upgrade_in_progress:
        indicator = "maintenance"
    elif ready_shards == total_shards:
        indicator = "operational"
    elif ready_shards > 0:
        indicator = "degraded"
    else:
        indicator = "outage"

    # Build shard data
    shards = [
        ShardData(
            shard_id=s.shard_id,
            latency_ms=s.latency_ms,
            guild_count=s.guild_count,
            is_ready=s.is_ready,
            last_updated=s.last_updated,
            version=s.version,
        )
        for s in statuses
    ]

    return StatusData(
        indicator=indicator,
        total_shards=total_shards,
        ready_shards=ready_shards,
        total_guilds=total_guilds,
        shards=shards,
        version=version,
        upgrade_in_progress=upgrade_in_progress,
        last_updated=last_updated,
    )


def format_status_for_html(data: StatusData) -> dict[str, Any]:
    """Add HTML-specific formatting to status data for template rendering."""
    overall_status, _ = STATUS_DISPLAY.get(data.indicator, ("unknown", "Unknown"))

    # Build version groups for display during upgrades
    version_info: dict[str, list[int]] = {}
    for shard in data.shards:
        ver = shard.version
        if ver not in version_info:
            version_info[ver] = []
        version_info[ver].append(shard.shard_id)

    sorted_versions = sorted(
        version_info.keys(),
        key=lambda v: parse_version(v) if v != "unknown" else parse_version("0.0.0"),
        reverse=True,
    )

    version_groups = [
        {
            "version": v,
            "shard_ids": sorted(version_info[v]),
            "is_newest": v == sorted_versions[0] if sorted_versions else False,
        }
        for v in sorted_versions
    ]

    # Format shard data for template
    shard_data = [
        {
            "shard_id": shard.shard_id,
            "latency": format_latency(shard.latency_ms),
            "latency_class": get_latency_class(shard.latency_ms),
            "guild_count": shard.guild_count,
            "is_ready": shard.is_ready,
            "status_class": "status-healthy" if shard.is_ready else "status-down",
            "status_text": "Ready" if shard.is_ready else "Not Ready",
            "last_updated": format_time_ago(shard.last_updated),
            "version": shard.version,
        }
        for shard in data.shards
    ]

    return {
        "overall_status": overall_status,
        "overall_status_class": f"status-{overall_status}",
        "total_shards": data.total_shards,
        "ready_shards": data.ready_shards,
        "total_guilds": data.total_guilds,
        "shards": shard_data,
        "version": data.version,
        "version_url": version_release_url(data.version),
        "upgrade_in_progress": data.upgrade_in_progress,
        "version_groups": version_groups,
        "last_updated": format_time_ago(data.last_updated) if data.last_updated else "never",
    }


@routes.get("/status")
@tracer.wrap(name="web", resource="status")
async def endpoint(request: web.Request) -> web.Response:
    """Render the shard status page."""
    add_span_request_id(generate_request_id())
    statuses, metadata = await get_all_shard_statuses()
    data = compute_status(statuses, metadata)
    context = format_status_for_html(data)
    return aiohttp_jinja2.render_template("status.html.j2", request, context)


def format_status_for_json(data: StatusData) -> dict[str, Any]:
    """Format status data for JSON API response."""
    _, description = STATUS_DISPLAY.get(data.indicator, ("unknown", "Unknown"))

    # Use "degraded_performance" and "major_outage" for JSON API (like Discord)
    json_indicator = data.indicator
    if data.indicator == "degraded":
        json_indicator = "degraded_performance"
    elif data.indicator == "outage":
        json_indicator = "major_outage"

    shards = [
        {
            "shard_id": shard.shard_id,
            "latency_ms": shard.latency_ms,
            "guild_count": shard.guild_count,
            "is_ready": shard.is_ready,
            "last_updated": shard.last_updated,
            "version": shard.version,
        }
        for shard in data.shards
    ]

    return {
        "status": {
            "indicator": json_indicator,
            "description": description,
        },
        "shards": {
            "total": data.total_shards,
            "ready": data.ready_shards,
            "data": shards,
        },
        "guilds": data.total_guilds,
        "version": data.version,
        "upgrade_in_progress": data.upgrade_in_progress,
        "last_updated": data.last_updated,
    }


@routes.get("/status.json")
@tracer.wrap(name="web", resource="status_json")
async def json_endpoint(_: web.Request) -> web.Response:
    """Return SpellBot status as JSON."""
    add_span_request_id(generate_request_id())
    statuses, metadata = await get_all_shard_statuses()
    data = compute_status(statuses, metadata)
    response = format_status_for_json(data)
    return web.json_response(response)
