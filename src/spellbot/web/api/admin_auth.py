from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx
from aiohttp import web
from aiohttp_session import Session, get_session, new_session
from aiohttp_session import setup as session_setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import Fernet

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.settings import settings
from spellbot.web.api.oauth import (
    DISCORD_AUTHORIZE_URL,
    canonical_host_redirect,
    display_name,
    fetch_oauth_identify,
    parse_user_xid,
)

if TYPE_CHECKING:
    from aiohttp.typedefs import Handler

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

SESSION_COOKIE_NAME = "spellbot_admin"
SESSION_MAX_AGE_S = 60 * 60 * 24  # 24 hours

# Routes inside /admin/* that do not require an authenticated session.
PUBLIC_ADMIN_PATHS: frozenset[str] = frozenset(
    ("/admin/login", "/admin/oauth/callback"),
)


def resolve_session_key() -> Fernet:
    """
    Build the Fernet cipher used to encrypt admin session cookies.

    `SESSION_SECRET_KEY` must be a url-safe base64-encoded 32-byte key as produced by
    `cryptography.fernet.Fernet.generate_key()`. If unset (e.g. in tests), a fresh key
    is generated; sessions issued under that key won't survive a process restart.

    Raises `ValueError` with a clear message if `SESSION_SECRET_KEY` is set but is
    not a valid Fernet key (wrong length, missing padding, etc.).
    """
    raw = settings.SESSION_SECRET_KEY
    if not raw:
        return Fernet(Fernet.generate_key())
    cleaned = raw.strip().strip('"').strip("'")
    try:
        return Fernet(cleaned.encode("utf-8"))
    except ValueError as ex:
        msg = (
            "SESSION_SECRET_KEY is set but is not a valid Fernet key. "
            "It must be a url-safe base64-encoded 32-byte key (44 chars ending in '='). "
            "Generate one with `make session-key`."
        )
        raise ValueError(msg) from ex


def oauth_redirect_uri() -> str:
    return f"{settings.API_BASE_URL.rstrip('/')}/admin/oauth/callback"


def setup_admin_sessions(app: web.Application) -> None:
    """Install `EncryptedCookieStorage` on the aiohttp app."""
    storage = EncryptedCookieStorage(
        resolve_session_key(),
        cookie_name=SESSION_COOKIE_NAME,
        max_age=SESSION_MAX_AGE_S,
        httponly=True,
        samesite="Lax",
        secure=settings.API_BASE_URL.startswith("https://"),
    )
    session_setup(app, storage)


async def get_admin_user_xid(request: web.Request) -> int | None:
    """
    Return the Discord xid of the authenticated admin, or `None`.

    Trust the session: any xid present in the cookie was admitted by
    `admin_oauth_callback` at login. Revocations via `!demote` take effect
    at the user's next login (bounded by `SESSION_MAX_AGE_S`).
    """
    session = await get_session(request)
    xid = session.get("xid")
    if not isinstance(xid, int):
        return None
    return xid


def is_owner_session(session: Session) -> bool:
    """Return True when the admin session belongs to the configured bot owner."""
    xid = session.get("xid")
    return settings.OWNER_XID is not None and xid == settings.OWNER_XID


async def is_owner_request(request: web.Request) -> bool:
    """Return True when the request carries an authenticated owner session."""
    return is_owner_session(await get_session(request))


@web.middleware
async def admin_auth_middleware(
    request: web.Request,
    handler: Handler,
) -> web.StreamResponse:
    """Gate `/admin/*` routes behind a valid admin session."""
    path = request.path
    if not path.startswith("/admin/") and path != "/admin":
        return await handler(request)
    if path in PUBLIC_ADMIN_PATHS:
        return await handler(request)
    if await get_admin_user_xid(request) is None:
        return web.HTTPFound("/admin/login")
    return await handler(request)


@routes.get("/admin/login")
async def admin_login(request: web.Request) -> web.StreamResponse:
    """Redirect the user to Discord's OAuth2 authorize page."""
    if not settings.BOT_APPLICATION_ID or not settings.BOT_CLIENT_SECRET:
        return web.Response(status=503, text="Admin dashboard is not configured.")
    if (canonical := canonical_host_redirect(request)) is not None:
        return canonical
    state = secrets.token_urlsafe(32)
    session = await new_session(request)
    session["oauth_state"] = state
    params = {
        "client_id": settings.BOT_APPLICATION_ID,
        "response_type": "code",
        "scope": "identify",
        "redirect_uri": oauth_redirect_uri(),
        "state": state,
    }
    return web.HTTPFound(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")


@routes.get("/admin/oauth/callback")
async def admin_oauth_callback(request: web.Request) -> web.StreamResponse:
    """Exchange the OAuth2 code for an access token and start a session."""
    if not settings.BOT_APPLICATION_ID or not settings.BOT_CLIENT_SECRET:
        return web.Response(status=503, text="Admin dashboard is not configured.")
    code = request.query.get("code")
    state = request.query.get("state")
    session = await get_session(request)
    expected_state = session.get("oauth_state")
    if not code or not state or state != expected_state:
        logger.warning(
            "Invalid OAuth state: has_code=%s has_state=%s session_new=%s "
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
        user = await fetch_oauth_identify(code, oauth_redirect_uri())
    except httpx.HTTPError as ex:
        logger.warning("OAuth flow failed: %s", ex)
        return web.Response(status=502, text="OAuth flow failed.")
    if user is None:
        return web.Response(status=401, text="Could not identify Discord user.")

    xid = parse_user_xid(user)
    if xid is None:
        return web.Response(status=401, text="Could not identify Discord user.")

    if xid != settings.OWNER_XID:
        async with db_session_manager():
            if not await services.users.is_admin(xid):
                return web.Response(
                    status=403,
                    text="You are not authorized to access this page.",
                )

    session.invalidate()
    session = await new_session(request)
    session["xid"] = xid
    session["name"] = display_name(user, xid)
    return web.HTTPFound("/admin/dashboard")


@routes.post("/admin/logout")
async def admin_logout(request: web.Request) -> web.StreamResponse:
    """Clear the admin session."""
    session = await get_session(request)
    session.invalidate()
    return web.HTTPFound("/admin/login")
