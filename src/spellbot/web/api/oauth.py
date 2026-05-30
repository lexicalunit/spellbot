from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from aiohttp import web
from yarl import URL

from spellbot.settings import settings

logger = logging.getLogger(__name__)

DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"  # noqa: S105
DISCORD_IDENTIFY_URL = "https://discord.com/api/users/@me"


def canonical_host_redirect(request: web.Request) -> web.HTTPFound | None:
    # If `request` arrived on a non-canonical host (e.g. via a vanity domain alias
    # like `queues.spellbot.io`), return a redirect to the same path+query on
    # `settings.API_BASE_URL`. This keeps the session cookie on a single origin so
    # the OAuth callback can read the `state` written by the login handler.
    # Returns `None` when the host already matches or `API_BASE_URL` is unset.
    base = settings.API_BASE_URL
    if not base:
        return None
    base_url = URL(base)
    expected = base_url.host
    if not expected or request.url.host == expected:
        return None
    # Validate the incoming path is a same-origin relative reference before
    # carrying it over to the canonical host, per CWE-601 guidance. Browsers
    # treat backslashes as forward slashes in URLs, so normalize them first,
    # and reject anything that resolves to an explicit scheme or host.
    raw_target = str(request.rel_url).replace("\\", "/")
    parsed = urlparse(raw_target)
    if parsed.scheme or parsed.netloc or raw_target.startswith("//"):
        return web.HTTPFound(str(base_url.with_path("/")))
    return web.HTTPFound(str(base_url.with_path(parsed.path).with_query(parsed.query)))


async def fetch_oauth_identify(code: str, redirect_uri: str) -> dict[str, Any] | None:
    """
    Exchange an OAuth code for an access token and return Discord's identify payload.

    Returns `None` if either the token exchange or the identify call returns a
    non-200 response. Raises `httpx.HTTPError` on transport-level failures so the
    caller can distinguish "OAuth flow failed" from "Discord refused the code".
    """
    data = {
        "client_id": settings.BOT_APPLICATION_ID,
        "client_secret": settings.BOT_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        tok = await client.post(DISCORD_TOKEN_URL, data=data)
        if tok.status_code != 200:
            logger.warning("OAuth token exchange failed: %s", tok.status_code)
            return None
        access_token = tok.json().get("access_token")
        me = await client.get(
            DISCORD_IDENTIFY_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if me.status_code != 200:
            return None
        return me.json()


def parse_user_xid(user: dict[str, Any]) -> int | None:
    """Return the integer Discord ID from an identify payload, or `None` if malformed."""
    try:
        return int(user["id"])
    except KeyError, ValueError, TypeError:
        return None


def display_name(user: dict[str, Any], fallback: int) -> str:
    """Pick the best human-readable name from a Discord identify payload."""
    return user.get("global_name") or user.get("username") or str(fallback)
