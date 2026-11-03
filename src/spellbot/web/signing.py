# Copyright (c) 2026 spellbot@lexicalunit.com

"""HMAC-signed links that grant temporary access to a guild's analytics page."""

from __future__ import annotations

import hashlib
import hmac
import time

from spellbot.settings import settings


def generate_signed_url(guild_xid: int, expires_in_minutes: int = 15) -> str:
    """Generate an HMAC-signed analytics URL for a guild."""
    expires = int(time.time()) + (expires_in_minutes * 60)
    message = f"{guild_xid}:{expires}"
    secret = (settings.SECRET_TOKEN or "").encode()
    sig = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
    return f"{settings.API_BASE_URL}/g/{guild_xid}/analytics?expires={expires}&sig={sig}"


def validate_signature(guild_xid: int, expires: int, sig: str) -> bool:
    """Validate an HMAC-signed analytics URL."""
    if not settings.CHECK_SIGNATURE:
        return True
    if time.time() > expires:
        return False
    message = f"{guild_xid}:{expires}"
    secret = (settings.SECRET_TOKEN or "").encode()
    expected = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)
