# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging

from aiohttp import web
from ddtrace.trace import tracer

from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.public_stats import get_public_stats

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# Browser/CDN cache lifetime. The backing task refreshes on its own schedule, so
# serving a value up to a minute old costs nothing and keeps the static site from
# generating a request per visitor.
CACHE_MAX_AGE = 60


@routes.get("/stats.json")
@tracer.wrap(name="web", resource="stats_json")
async def stats_json_endpoint(_: web.Request) -> web.Response:
    """
    Return cached public activity counts as JSON.

    Reads only from Redis, never the database: this endpoint is called by the
    static marketing site at spellbot.io, whose traffic should not translate into
    database load. `update_public_stats()` refreshes the cache on a task loop.

    Responds 503 when no cached value is available so consumers can tell "no data
    right now" apart from "genuinely zero activity".
    """
    add_span_request_id(generate_request_id())
    stats = await get_public_stats()
    if stats is None:
        return web.json_response(
            {"error": "stats unavailable"},
            status=503,
            headers={"Cache-Control": "no-store"},
        )
    return web.json_response(
        stats.to_dict(),
        headers={"Cache-Control": f"public, max-age={CACHE_MAX_AGE}"},
    )
