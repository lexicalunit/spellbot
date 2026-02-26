from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from aiohttp.web_response import Response as WebResponse

logger = logging.getLogger(__name__)


# Not traced because it's called often for health checks.
async def endpoint(_: web.Request) -> WebResponse:
    # add_span_request_id(generate_request_id())
    return web.Response(text="ok")
