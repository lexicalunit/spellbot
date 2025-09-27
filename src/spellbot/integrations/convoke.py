from __future__ import annotations

import logging
import random
from time import time
from typing import TYPE_CHECKING, Any

import httpx

from spellbot import __version__
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
TIMEOUT_S = 3
ADJECTIVES = [
    "ancient",
    "angry",
    "arcane",
    "blazing",
    "cursed",
    "dark",
    "eternal",
    "fierce",
    "giant",
    "grim",
    "hidden",
    "lucky",
    "mighty",
    "mystic",
    "ominous",
    "sacred",
    "shiny",
    "swift",
    "twisted",
    "wild",
]
NOUNS = [
    "angel",
    "beast",
    "bolt",
    "counter",
    "dragon",
    "elf",
    "fetch",
    "goblin",
    "land",
    "mana",
    "merfolk",
    "sliver",
    "sorcery",
    "stack",
    "storm",
    "token",
    "wizard",
    "zombie",
]

cached_token: str | None = None
token_expiry: float | None = None


def passphrase() -> str:  # pragma: no cover
    return f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}"  # noqa: S311


async def get_auth_token(  # pragma: no cover
    client_id: str,
    client_secret: str,
    audience: str,
) -> str | None:
    global cached_token, token_expiry  # noqa: PLW0603

    if cached_token and token_expiry and time() < token_expiry:
        return cached_token

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": audience,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        resp = await client.post(f"{settings.CONVOKE_AUTH_URL}/oauth/token", data=payload)
        resp.raise_for_status()
        data = resp.json()["access_token"]
        cached_token = data["access_token"]
        token_expiry = time.time() + data.get("expires_in", 3600) - 30  # buffer 30s
        return cached_token


async def fetch_convoke_link(  # pragma: no cover
    client: httpx.AsyncClient,
    name: str,
    key: str,
    access_token: str,
) -> dict[str, Any]:
    payload = {
        "name": name,
        "isPublic": False,
        "seatLimit": 4,
        "password": key,
        "format": "commander",
    }
    headers = {
        "user-agent": f"spellbot/{__version__}",
        "Authorization": f"Bearer {access_token}",
    }
    endpoint = f"{settings.CONTENT_ROOT}/game/create-game"
    resp = await client.post(endpoint, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def generate_link(game: GameDict) -> tuple[str | None, str | None]:  # pragma: no cover
    if (
        not settings.CONVOKE_CLIENT_ID
        or not settings.CONVOKE_CLIENT_SECRET
        or not settings.CONVOKE_AUDIENCE
    ):
        return None, None

    client_id = settings.CONVOKE_CLIENT_ID
    client_secret = settings.CONVOKE_CLIENT_SECRET
    audience = settings.CONVOKE_AUDIENCE

    try:
        access_token = await get_auth_token(client_id, client_secret, audience)
    except Exception as ex:
        add_span_error(ex)
        logger.exception("Convoke API failed to get auth token")
        return None, None
    if not access_token:
        logger.error("Convoke API returned no auth token")
        return None, None

    key = passphrase()
    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                data = await fetch_convoke_link(client, f"SB{game['id']}", key, access_token)
            except Exception as ex:
                add_span_error(ex)
                if attempt == RETRY_ATTEMPTS - 1:
                    logger.exception("Convoke API failure (final attempt)")
                    return None, None
                logger.warning(
                    "Convoke API issue (attempt %s)",
                    attempt + 1,
                    exc_info=True,
                )

            if not data:
                return None, None
            game_id = data["id"]
            game_pass = data["password"]
            return f"https://www.convoke.games/en/play/private/{game_id}", game_pass

    return None, None
