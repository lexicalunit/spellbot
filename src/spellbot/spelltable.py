from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from random import randint
from typing import TYPE_CHECKING, NamedTuple, cast
from urllib.parse import parse_qs, urlparse

import httpx

from spellbot.enums import GameFormat
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)

ROUND_ROBIN = None
ROUND_ROBIN_LOCK = asyncio.Lock()
USER_LOCKS: dict[str, asyncio.Lock] = {}
USER_LOCKS_LOCK = asyncio.Lock()  # protects USER_LOCKS itself
TIMEOUT_S = 3
RETRY_ATTEMPTS = 2


class SpellTableCSRFError(RuntimeError):
    def __init__(self) -> None:  # pragma: no cover
        super().__init__("No CSRF token in login response")


class SpellTableRedirectError(RuntimeError):
    def __init__(self) -> None:  # pragma: no cover
        super().__init__("No redirect_target in authorize response")


class SpellTableCodeError(RuntimeError):
    def __init__(self) -> None:  # pragma: no cover
        super().__init__("No code in redirect_target query params")


class TokenData(NamedTuple):
    access_token: str
    refresh_token: str
    expires_at: datetime


# Global in-memory token store
user_tokens: dict[str, TokenData] = {}


class SpellTableGameTypes(Enum):
    Commander = "Commander"
    Standard = "Standard"
    Sealed = "Sealed"
    Modern = "Modern"
    Vintage = "Vintage"
    Legacy = "Legacy"
    BrawlTwoPlayer = "Brawl Two Player"
    BrawlMultiplayer = "Brawl Multiplayer"
    TwoHeadedGiant = "Two Headed Giant"
    Pauper = "Pauper"
    PauperEDH = "Pauper EDH"
    Pioneer = "Pioneer"
    Oathbreaker = "Oathbreaker"


def spelltable_game_type(format: GameFormat) -> SpellTableGameTypes:  # noqa: C901
    match format:
        case GameFormat.STANDARD | GameFormat.SEALED:
            return SpellTableGameTypes.Standard
        case GameFormat.MODERN:
            return SpellTableGameTypes.Modern
        case GameFormat.VINTAGE:
            return SpellTableGameTypes.Vintage
        case GameFormat.LEGACY | GameFormat.DUEL_COMMANDER:
            return SpellTableGameTypes.Legacy
        case GameFormat.BRAWL_TWO_PLAYER:
            return SpellTableGameTypes.BrawlTwoPlayer
        case GameFormat.BRAWL_MULTIPLAYER:
            return SpellTableGameTypes.BrawlMultiplayer
        case GameFormat.TWO_HEADED_GIANT:
            return SpellTableGameTypes.TwoHeadedGiant
        case GameFormat.PAUPER:
            return SpellTableGameTypes.Pauper
        case GameFormat.PAUPER_EDH:
            return SpellTableGameTypes.PauperEDH
        case GameFormat.PIONEER:
            return SpellTableGameTypes.Pioneer
        case GameFormat.OATHBREAKER:
            return SpellTableGameTypes.Oathbreaker
        case (
            GameFormat.COMMANDER
            | GameFormat.EDH_MAX
            | GameFormat.EDH_HIGH
            | GameFormat.EDH_MID
            | GameFormat.EDH_LOW
            | GameFormat.EDH_BATTLECRUISER
            | GameFormat.PLANECHASE
            | GameFormat.PRE_CONS
            | GameFormat.CEDH
            | GameFormat.ARCHENEMY
        ):
            return SpellTableGameTypes.Commander


def get_accounts() -> list[tuple[str, str]]:  # pragma: no cover
    assert settings.SPELLTABLE_USERS, "SPELLTABLE_USERS not configured"
    assert settings.SPELLTABLE_PASSES, "SPELLTABLE_PASSES not configured"
    return list(
        zip(
            settings.SPELLTABLE_USERS.split(","),
            settings.SPELLTABLE_PASSES.split(","),
            strict=True,
        ),
    )


async def pick_account(accounts: list[tuple[str, str]]) -> tuple[str, str]:  # pragma: no cover
    global ROUND_ROBIN  # noqa: PLW0603
    async with ROUND_ROBIN_LOCK:
        if ROUND_ROBIN is None:
            ROUND_ROBIN = randint(0, len(accounts) - 1)  # noqa: S311
        username, password = accounts[ROUND_ROBIN % len(accounts)]
        ROUND_ROBIN += 1
        return username, password


async def get_user_lock(username: str) -> asyncio.Lock:  # pragma: no cover
    async with USER_LOCKS_LOCK:
        if username not in USER_LOCKS:
            USER_LOCKS[username] = asyncio.Lock()
        return USER_LOCKS[username]


async def get_csrf(client: httpx.AsyncClient) -> str:  # pragma: no cover
    resp = await client.get(f"{settings.WIZARDS_ROOT}/login")
    resp.raise_for_status()
    csrf_token = client.cookies.get("_csrf")
    if not csrf_token:
        raise SpellTableCSRFError
    return csrf_token


async def login(  # pragma: no cover
    client: httpx.AsyncClient,
    username: str,
    password: str,
    csrf: str,
) -> None:
    url = f"{settings.WIZARDS_ROOT}/api/login"
    payload = {
        "username": username,
        "password": password,
        "referringClientID": settings.SPELLTABLE_CLIENT_ID,
        "remember": False,
        "_csrf": csrf,
    }
    resp = await client.post(url, json=payload)
    resp.raise_for_status()


async def client_info(client: httpx.AsyncClient, csrf: str) -> None:  # pragma: no cover
    url = f"{settings.WIZARDS_ROOT}/api/client"
    payload = {
        "clientID": settings.SPELLTABLE_CLIENT_ID,
        "language": "en-US",
        "_csrf": csrf,
    }
    resp = await client.post(url, json=payload)
    resp.raise_for_status()


async def authorize(client: httpx.AsyncClient, csrf: str) -> str:  # pragma: no cover
    url = f"{settings.WIZARDS_ROOT}/api/authorize"
    payload = {
        "clientInput": {
            "clientID": settings.SPELLTABLE_CLIENT_ID,
            "redirectURI": settings.SPELLTABLE_AUTH_REDIRECT,
            "scope": "email",
            "state": "",
            "version": "2",
        },
        "_csrf": csrf,
    }
    resp = await client.post(url, json=payload, follow_redirects=False)
    resp.raise_for_status()
    redirect_target = resp.json().get("data", {}).get("redirect_target")
    if not redirect_target:
        raise SpellTableRedirectError

    parsed = urlparse(redirect_target)
    code = parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        raise SpellTableCodeError
    return code


async def exchange_code(client: httpx.AsyncClient, code: str) -> TokenData:  # pragma: no cover
    url = f"{settings.SPELLTABLE_ROOT}/prod/exchangeCode"
    payload = {"code": code}
    headers = {"x-api-key": cast("str", settings.SPELLTABLE_API_KEY)}
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return TokenData(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.now(tz=UTC) + timedelta(seconds=data["expires_in"]),
    )


async def refresh_access_token(  # pragma: no cover
    client: httpx.AsyncClient,
    refresh_token: str,
) -> TokenData | None:
    headers = {"x-api-key": cast("str", settings.SPELLTABLE_API_KEY)}
    url = f"{settings.SPELLTABLE_ROOT}/prod/refreshToken"
    try:
        resp = await client.post(url, headers=headers, json={"refreshToken": refresh_token})
        resp.raise_for_status()
        data = resp.json()
        return TokenData(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=data["expires_in"]),
        )
    except Exception as ex:
        logger.warning("Token refresh failed: %s", ex, exc_info=True)
        return None


async def create_game(  # pragma: no cover
    client: httpx.AsyncClient,
    token: str,
    game: GameDict,
) -> str:
    url = f"{settings.SPELLTABLE_ROOT}/prod/createGame"
    headers = {"x-api-key": cast("str", settings.SPELLTABLE_API_KEY)}
    format = spelltable_game_type(GameFormat(game["format"])).value
    payload = {
        "token": token,
        "name": f"SB{game['id']}",
        "description": "",
        "format": format,
        "isPublic": False,
        "tags": {},
    }
    resp = await client.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return f"https://spelltable.wizards.com/game/{data['id']}"


async def generate_link(game: GameDict) -> str | None:  # pragma: no cover
    accounts = get_accounts()
    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)

    for attempt in range(RETRY_ATTEMPTS):
        username, password = await pick_account(accounts)
        user_lock = await get_user_lock(username)

        async with user_lock, httpx.AsyncClient(timeout=timeout) as client:
            try:
                now = datetime.now(tz=UTC)
                token_data = user_tokens.get(username)
                access_token: str | None = None
                if token_data and token_data.access_token and token_data.expires_at > now:
                    access_token = token_data.access_token
                elif token_data and token_data.refresh_token and token_data.expires_at <= now:
                    refreshed = await refresh_access_token(client, token_data.refresh_token)
                    if refreshed:
                        user_tokens[username] = refreshed
                        access_token = refreshed.access_token

                if not access_token:
                    csrf = await get_csrf(client)
                    await login(client, username, password, csrf)
                    await client_info(client, csrf)
                    code = await authorize(client, csrf)
                    new_token = await exchange_code(client, code)
                    user_tokens[username] = new_token
                    access_token = new_token.access_token

                return await create_game(client, access_token, game)

            except Exception as ex:
                add_span_error(ex)
                if attempt == RETRY_ATTEMPTS - 1:
                    logger.exception(
                        "SpellTable API failure (final attempt, user=%s):",
                        username,
                    )
                    return None
                logger.warning(
                    "SpellTable API issue (attempt %s, user=%s):",
                    attempt + 1,
                    username,
                    exc_info=True,
                )

    return None
