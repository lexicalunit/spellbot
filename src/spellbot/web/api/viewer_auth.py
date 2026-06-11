from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import httpx
from aiohttp import web
from aiohttp_session import get_session

from spellbot.settings import settings
from spellbot.web.api.admin_auth import ADMIN_NAME_KEY, ADMIN_XID_KEY
from spellbot.web.api.oauth import (
    DISCORD_AUTHORIZE_URL,
    canonical_host_redirect,
    display_name,
    fetch_oauth_identify,
    parse_user_xid,
    safe_relative_path,
)

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# Session keys are deliberately distinct from the admin-side keys so that completing
# this flow can never grant access to `/admin/*` routes.
VIEWER_XID_KEY = "viewer_xid"
VIEWER_NAME_KEY = "viewer_name"
VIEWER_STATE_KEY = "viewer_oauth_state"
VIEWER_NEXT_KEY = "viewer_oauth_next"

VIEWER_REDIRECT_AFTER_LOGIN = "/queues?my=1"
VIEWER_REDIRECT_AFTER_LOGOUT = "/queues"


def viewer_oauth_redirect_uri() -> str:
    return f"{settings.API_BASE_URL.rstrip('/')}/queues/oauth/callback"


async def get_viewer(request: web.Request) -> tuple[int | None, str | None]:
    """
    Return the current viewer's `(xid, name)` from the session, or `(None, None)`.

    A dedicated viewer session (set by the `/queues` OAuth flow) takes precedence.
    Absent that, we fall back to an authenticated *admin* session: the admin's
    Discord identity was already verified at `/admin/login`, and an admin is a
    strictly higher-privilege identity than a viewer, so honoring it here unifies
    login across the admin and `/queues` pages without expanding access. The
    reverse direction is NOT symmetric — a viewer session never writes the admin
    keys, so it can never unlock `/admin/*` (see the admin auth middleware).
    """
    session = await get_session(request)
    xid = session.get(VIEWER_XID_KEY)
    if isinstance(xid, int):
        name = session.get(VIEWER_NAME_KEY)
        return xid, name if isinstance(name, str) else None
    admin_xid = session.get(ADMIN_XID_KEY)
    if isinstance(admin_xid, int):
        admin_name = session.get(ADMIN_NAME_KEY)
        return admin_xid, admin_name if isinstance(admin_name, str) else None
    return None, None


async def has_viewer_session(request: web.Request) -> bool:
    """
    Return True only when a dedicated viewer session exists.

    Distinguishes a real viewer login from an admin session recognized via the
    fallback in `get_viewer`. The `/queues` logout button (which clears only the
    viewer keys) is meaningful exactly when this is True.
    """
    session = await get_session(request)
    return isinstance(session.get(VIEWER_XID_KEY), int)


@routes.get("/queues/login")
async def viewer_login(request: web.Request) -> web.StreamResponse:
    """Redirect the user to Discord's OAuth2 authorize page (public viewer flow)."""
    if not settings.BOT_APPLICATION_ID or not settings.BOT_CLIENT_SECRET:
        return web.Response(status=503, text="Viewer login is not configured.")
    if (canonical := canonical_host_redirect(request)) is not None:
        return canonical
    state = secrets.token_urlsafe(32)
    session = await get_session(request)
    session[VIEWER_STATE_KEY] = state
    # Remember where to send the viewer back to after login, when a safe path is given.
    next_path = safe_relative_path(request.query.get("next"))
    if next_path:
        session[VIEWER_NEXT_KEY] = next_path
    else:
        session.pop(VIEWER_NEXT_KEY, None)
    params = {
        "client_id": settings.BOT_APPLICATION_ID,
        "response_type": "code",
        "scope": "identify",
        "redirect_uri": viewer_oauth_redirect_uri(),
        "state": state,
    }
    return web.HTTPFound(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")


@routes.get("/queues/oauth/callback")
async def viewer_oauth_callback(request: web.Request) -> web.StreamResponse:
    """Exchange the OAuth2 code for a viewer session that filters `/queues` only."""
    if not settings.BOT_APPLICATION_ID or not settings.BOT_CLIENT_SECRET:
        return web.Response(status=503, text="Viewer login is not configured.")
    code = request.query.get("code")
    state = request.query.get("state")
    session = await get_session(request)
    expected_state = session.get(VIEWER_STATE_KEY)
    if not code or not state or state != expected_state:
        logger.warning(
            "Invalid viewer OAuth state: has_code=%s has_state=%s session_new=%s "
            "has_expected=%s state_match=%s ua=%s",
            bool(code),
            bool(state),
            session.new,
            expected_state is not None,
            bool(state) and state == expected_state,
            request.headers.get("User-Agent", "")[:80],
        )
        return web.Response(status=400, text="Invalid OAuth state.")

    try:
        user = await fetch_oauth_identify(code, viewer_oauth_redirect_uri())
    except httpx.HTTPError as ex:
        logger.warning("Viewer OAuth flow failed: %s", ex)
        return web.Response(status=502, text="OAuth flow failed.")
    if user is None:
        return web.Response(status=401, text="Could not identify Discord user.")

    xid = parse_user_xid(user)
    if xid is None:
        return web.Response(status=401, text="Could not identify Discord user.")

    # Preserve any admin session that already exists by only writing to the viewer
    # keys. We deliberately do NOT set "xid" or "name" (the admin-side keys).
    session.pop(VIEWER_STATE_KEY, None)
    session[VIEWER_XID_KEY] = xid
    session[VIEWER_NAME_KEY] = display_name(user, xid)
    # Return to the page the viewer started from, when one was safely recorded.
    next_path = safe_relative_path(session.pop(VIEWER_NEXT_KEY, None))
    return web.HTTPFound(next_path or VIEWER_REDIRECT_AFTER_LOGIN)


@routes.post("/queues/logout")
async def viewer_logout(request: web.Request) -> web.StreamResponse:
    """Clear the viewer session without disturbing any concurrent admin session."""
    session = await get_session(request)
    session.pop(VIEWER_XID_KEY, None)
    session.pop(VIEWER_NAME_KEY, None)
    session.pop(VIEWER_STATE_KEY, None)
    return web.HTTPFound(VIEWER_REDIRECT_AFTER_LOGOUT)
