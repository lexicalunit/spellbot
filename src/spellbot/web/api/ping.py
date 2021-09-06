import logging

from aiohttp import web
from aiohttp.web_response import Response as WebResponse

logger = logging.getLogger(__name__)


async def endpoint(request: web.Request) -> WebResponse:
    return web.Response(text="ok")
