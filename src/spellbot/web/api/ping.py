from __future__ import annotations

import logging

from aiohttp import web

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


# Not traced because it's called often for health checks.
@routes.get("/")
async def endpoint(_: web.Request) -> web.Response:
    return web.Response(text="ok")
