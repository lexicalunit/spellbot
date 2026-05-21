from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from aiohttp import web
from sqlalchemy import text

from spellbot.database import DatabaseSession, db_session_manager
from spellbot.redis_client import get_redis
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


# Not traced because it's called often for health checks.
@routes.get("/")
async def endpoint(_: web.Request) -> web.Response:
    return web.Response(text="ok")


@routes.get("/health")
async def health_endpoint(_: web.Request) -> web.Response:
    """Health check endpoint that verifies database and Redis connectivity."""
    checks: dict[str, Any] = {
        "status": "healthy",
        "database": {"status": "unknown"},
        "redis": {"status": "unknown"},
    }

    # Check database connectivity
    try:
        async with db_session_manager():
            result = await DatabaseSession.execute(text("SELECT 1"))
            result.scalar()
        checks["database"] = {"status": "healthy"}
    except Exception as ex:
        checks["database"] = {"status": "unhealthy", "error": str(ex)}
        checks["status"] = "unhealthy"

    # Check Redis connectivity (if configured)
    if settings.REDIS_URL:
        try:
            redis = await get_redis()
            await cast("Awaitable[bool]", redis.ping())
            checks["redis"] = {"status": "healthy"}
        except Exception as ex:
            checks["redis"] = {"status": "unhealthy", "error": str(ex)}
            checks["status"] = "unhealthy"
    else:
        checks["redis"] = {"status": "disabled"}

    status_code = 200 if checks["status"] == "healthy" else 503
    return web.json_response(checks, status=status_code)
