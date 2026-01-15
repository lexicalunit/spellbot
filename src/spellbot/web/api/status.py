from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp_jinja2
from packaging.version import parse as parse_version

from spellbot.shard_status import get_all_shard_statuses

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.web_response import Response as WebResponse

logger = logging.getLogger(__name__)


def _format_latency(latency_ms: float | None) -> str:
    """Format latency for display."""
    if latency_ms is None:
        return "N/A"
    return f"{latency_ms:.1f}ms"


def _format_time_ago(iso_timestamp: str) -> str:
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


async def endpoint(request: web.Request) -> WebResponse:
    """Render the shard status page."""
    statuses, metadata = await get_all_shard_statuses()

    # Calculate overall health
    total_shards = metadata.get("shard_count", 0) if metadata else 0
    ready_shards = sum(1 for s in statuses if s.is_ready)
    total_guilds = metadata.get("total_guilds", 0) if metadata else 0
    version = metadata.get("version") if metadata else None

    # Detect if upgrade is in progress (multiple versions among shards)
    shard_versions = {s.version for s in statuses if s.version != "unknown"}
    upgrade_in_progress = len(shard_versions) > 1

    # Sort versions and determine old/new versions
    version_info: dict[str, list[int]] = {}  # version -> list of shard_ids
    for s in statuses:
        if s.version not in version_info:
            version_info[s.version] = []
        version_info[s.version].append(s.shard_id)

    # Sort versions (newest first)
    sorted_versions = sorted(
        version_info.keys(),
        key=lambda v: parse_version(v) if v != "unknown" else parse_version("0.0.0"),
        reverse=True,
    )

    # Determine overall status
    if not statuses:
        overall_status = "unknown"
        overall_status_class = "status-unknown"
    elif upgrade_in_progress:
        overall_status = "upgrading"
        overall_status_class = "status-upgrading"
    elif ready_shards == total_shards:
        overall_status = "healthy"
        overall_status_class = "status-healthy"
    elif ready_shards > 0:
        overall_status = "degraded"
        overall_status_class = "status-degraded"
    else:
        overall_status = "down"
        overall_status_class = "status-down"

    # Format shard data for template
    shard_data = [
        {
            "shard_id": status.shard_id,
            "latency": _format_latency(status.latency_ms),
            "latency_class": _get_latency_class(status.latency_ms),
            "guild_count": status.guild_count,
            "is_ready": status.is_ready,
            "status_class": "status-healthy" if status.is_ready else "status-down",
            "status_text": "Ready" if status.is_ready else "Not Ready",
            "last_updated": _format_time_ago(status.last_updated),
            "version": status.version,
        }
        for status in statuses
    ]

    # Build version groups for display during upgrades
    version_groups = [
        {
            "version": v,
            "shard_ids": sorted(version_info[v]),
            "is_newest": v == sorted_versions[0] if sorted_versions else False,
        }
        for v in sorted_versions
    ]

    context = {
        "overall_status": overall_status,
        "overall_status_class": overall_status_class,
        "total_shards": total_shards,
        "ready_shards": ready_shards,
        "total_guilds": total_guilds,
        "shards": shard_data,
        "version": version,
        "upgrade_in_progress": upgrade_in_progress,
        "version_groups": version_groups,
        "last_updated": (
            _format_time_ago(str(metadata.get("last_updated", ""))) if metadata else "never"
        ),
    }

    return aiohttp_jinja2.render_template("status.html.j2", request, context)


def _get_latency_class(latency_ms: float | None) -> str:
    """Get CSS class based on latency value."""
    if latency_ms is None:
        return "latency-unknown"
    if latency_ms < 100:
        return "latency-good"
    if latency_ms < 250:
        return "latency-ok"
    return "latency-bad"
