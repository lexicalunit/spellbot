from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web

from spellbot.logs import get_logger

if TYPE_CHECKING:
    from aiohttp.web_response import Response as WebResponse

logger = get_logger(__name__)


async def endpoint(_: web.Request) -> WebResponse:
    return web.Response(text="ok")
