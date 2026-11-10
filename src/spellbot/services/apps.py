# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from ddtrace.trace import tracer
from sqlalchemy import select

from spellbot.data import TokenData
from spellbot.database import DatabaseSession
from spellbot.models import Token


def hash_api_key(key: str) -> str:
    """
    Hash an API key for storage and lookup.

    Keys are 256 random bits, so a plain SHA-256 is enough: there's nothing to
    brute-force, and unlike a password hash it stays cheap on every API request.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def parse_scopes(raw: str) -> str | None:
    """Normalize a comma-separated scope list, or return None if it names no scopes."""
    scopes = [scope.strip() for scope in raw.split(",") if scope.strip()]
    return ",".join(scopes) if scopes else None


def granting_scopes(path: str) -> set[str]:
    """
    Return the scopes that grant access to an API path.

    A resource scope grants all of its endpoints, and `resource:action` grants just one, so
    `/api/game/1/record` is open to `game` and to `game:record`. That lets a token be limited
    to the one endpoint it needs, such as `game:verify` without the ability to send DMs.
    """
    parts = path.lstrip("/").split("/")
    if len(parts) < 2:
        return set()
    resource = parts[1]
    scopes = {resource}
    if len(parts) > 3:
        scopes.add(f"{resource}:{parts[3]}")
    return scopes


@tracer.wrap()
async def verify_token(key: str, path: str) -> bool:
    """Verify that the given API key has access to the given path."""
    result = await DatabaseSession.execute(select(Token).where(Token.key_hash == hash_api_key(key)))
    token = result.scalar_one_or_none()
    if not token:
        return False
    if token.deleted_at:
        return False
    if token.scopes == "*":
        return True
    return not granting_scopes(path).isdisjoint(token.scopes.split(","))


async def create_token(*, scopes: str, note: str | None) -> tuple[TokenData, str]:
    """Create an API token, returning it with its key. Only the key's hash is stored."""
    key = secrets.token_urlsafe(32)
    token = Token(key_hash=hash_api_key(key), scopes=scopes, note=note)
    DatabaseSession.add(token)
    await DatabaseSession.commit()
    return TokenData.from_model(token), key


async def list_tokens(*, include_revoked: bool = False) -> list[TokenData]:
    """List API tokens, oldest first."""
    query = select(Token).order_by(Token.id)
    if not include_revoked:
        query = query.where(Token.deleted_at.is_(None))
    result = await DatabaseSession.execute(query)
    return [TokenData.from_model(token) for token in result.scalars()]


async def revoke_token(token_id: int) -> bool:
    """Revoke an API token. Returns False if there's no such token or it's already revoked."""
    token = await DatabaseSession.get(Token, token_id)
    if token is None or token.deleted_at is not None:
        return False
    token.deleted_at = datetime.now(tz=UTC)
    await DatabaseSession.commit()
    return True
