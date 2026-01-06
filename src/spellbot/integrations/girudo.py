from __future__ import annotations

import asyncio
import base64
import logging
from random import randint
from typing import TYPE_CHECKING, Any, NamedTuple

import httpx

from spellbot.enums import GameFormat
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)

ROUND_ROBIN: int | None = None
ROUND_ROBIN_LOCK = asyncio.Lock()
USER_LOCKS: dict[str, asyncio.Lock] = {}
USER_LOCKS_LOCK = asyncio.Lock()

class GirudoGameFormat(NamedTuple):
    uuid: str
    name: str

GIRUDO_FORMATS_CACHE: dict[str, GirudoGameFormat] | None = None
TCG_NAMES_CACHE: dict[str, str] | None = None


def get_default_girudo_format() -> GirudoGameFormat:
    uuid = settings.GIRUDO_DEFAULT_FORMAT_UUID or ""
    name = settings.GIRUDO_DEFAULT_FORMAT_NAME or ""
    return GirudoGameFormat(uuid=uuid, name=name)


def get_default_tcg() -> tuple[str, str]:

    uuid = settings.GIRUDO_DEFAULT_TCG_UUID or ""
    name = settings.GIRUDO_DEFAULT_TCG_NAME or ""
    return uuid, name


def _create_timeout() -> httpx.Timeout:

    timeout_s = settings.GIRUDO_TIMEOUT_S
    return httpx.Timeout(timeout_s, connect=timeout_s, read=timeout_s, write=timeout_s)


def get_all_girudo_formats() -> dict[str, GirudoGameFormat]:
    if not GIRUDO_FORMATS_CACHE:
        return {}
    
    return dict(GIRUDO_FORMATS_CACHE)


async def ensure_formats_loaded() -> dict[str, GirudoGameFormat]:

    if GIRUDO_FORMATS_CACHE is not None:
        return dict(GIRUDO_FORMATS_CACHE)
    
    accounts = get_accounts()
    if not accounts:
        logger.warning("No Girudo accounts configured, cannot fetch formats")
        return {}
    
    try:
        email, password = await pick_account(accounts)
        timeout = _create_timeout()
        async with httpx.AsyncClient(timeout=timeout) as client:
            token = await authenticate(client, email=email, password=password)
            if not token:
                logger.warning("Failed to authenticate for format fetch")
                return {}
            
            return await fetch_and_cache_formats(client, token)
    except Exception as ex:
        logger.warning("Failed to ensure formats loaded: %s", ex, exc_info=True)
        return {}


async def fetch_and_cache_formats(
    client: httpx.AsyncClient,
    token: str,
) -> dict[str, GirudoGameFormat]:
    global GIRUDO_FORMATS_CACHE
    
    if GIRUDO_FORMATS_CACHE is not None:
        return GIRUDO_FORMATS_CACHE
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = await client.get(
            f"{settings.GIRUDO_BASE_URL}/game-service/v1/game/format-list",
            headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "success":
            logger.warning("Girudo format-list returned non-success status: %s", data.get("status"))
            GIRUDO_FORMATS_CACHE = {}
            return GIRUDO_FORMATS_CACHE
        
        formats = {}
        for fmt in data.get("data", []):
            fmt_id = fmt.get("game_format_id")
            fmt_name = fmt.get("game_format_name")
            if fmt_id and fmt_name:
                normalized_key = fmt_name.lower().replace(" / ", "_").replace(" ", "_").replace("-", "_")
                formats[normalized_key] = GirudoGameFormat(uuid=fmt_id, name=fmt_name)
        
        if not formats:
            logger.warning("Girudo format-list returned empty data")
            GIRUDO_FORMATS_CACHE = {}
            return GIRUDO_FORMATS_CACHE
        
        logger.info("Successfully cached %d Girudo game formats", len(formats))
        GIRUDO_FORMATS_CACHE = formats
        return formats
        
    except Exception as ex:
        logger.warning("Failed to fetch Girudo formats from API: %s", ex, exc_info=True)
        GIRUDO_FORMATS_CACHE = {}
        return GIRUDO_FORMATS_CACHE


async def fetch_and_cache_tcg_names(
    client: httpx.AsyncClient,
    token: str,
) -> dict[str, str]:
    global TCG_NAMES_CACHE
    
    if TCG_NAMES_CACHE is not None:
        return TCG_NAMES_CACHE
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = await client.get(settings.GIRUDO_STORE_DATA_URL, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "success":
            logger.warning("Girudo store-data returned non-success status: %s", data.get("status"))
            TCG_NAMES_CACHE = {}
            return TCG_NAMES_CACHE
        
        tcg_names = {}
        store_games = (data.get("data") or {}).get("store_games", [])
        
        for game in store_games:
            game_id = game.get("id")
            game_name = game.get("name")
            if game_id and game_name:
                tcg_names[game_id] = game_name
        
        if not tcg_names:
            logger.warning("Girudo store-data returned empty store_games")
            TCG_NAMES_CACHE = {}
            return TCG_NAMES_CACHE
        
        logger.info("Successfully cached %d TCG names", len(tcg_names))
        TCG_NAMES_CACHE = tcg_names
        return tcg_names
        
    except Exception as ex:
        logger.warning("Failed to fetch Girudo TCG names from API: %s", ex, exc_info=True)
        TCG_NAMES_CACHE = {}
        return TCG_NAMES_CACHE


def girudo_game_format(game_format: GameFormat) -> GirudoGameFormat:
    formats = GIRUDO_FORMATS_CACHE or {}
    default = get_default_girudo_format()
    
    format_map = {
        GameFormat.STANDARD: "standard",
        GameFormat.SEALED: "sealed",
        GameFormat.MODERN: "modern",
        GameFormat.LEGACY: "legacy",
        GameFormat.VINTAGE: "vintage",
        GameFormat.PIONEER: "pioneer",
        GameFormat.PAUPER: "pauper",
        GameFormat.PAUPER_EDH: "pauper_edh",
        GameFormat.DUEL_COMMANDER: "duel_commander",
        GameFormat.OATHBREAKER: "oathbreaker",
    }
    
    if game_format in format_map:
        return formats.get(format_map[game_format], default)
    
    if game_format in (GameFormat.BRAWL_TWO_PLAYER, GameFormat.BRAWL_MULTIPLAYER):
        return formats.get("brawl", default)
    
    commander_formats = {
        GameFormat.COMMANDER,
        GameFormat.EDH_MAX,
        GameFormat.EDH_HIGH,
        GameFormat.EDH_MID,
        GameFormat.EDH_LOW,
        GameFormat.EDH_BATTLECRUISER,
        GameFormat.PLANECHASE,
        GameFormat.PRE_CONS,
        GameFormat.CEDH,
        GameFormat.ARCHENEMY,
        GameFormat.TWO_HEADED_GIANT,
        GameFormat.HORDE_MAGIC,
    }
    
    if game_format in commander_formats:
        return formats.get("commander_edh", default)
    
    logger.info(
        "No Girudo format mapping for %s, using fallback format %s",
        game_format.name,
        default.name,
    )
    return default

class GirudoLinkDetails(NamedTuple):
    link: str | None = None
    password: str | None = None

class GirudoAuthError(RuntimeError):
    def __init__(self, message: str = "Failed to authenticate to Girudo") -> None:
        super().__init__(message)

class GirudoGameCreateError(RuntimeError):
    def __init__(self, message: str = "Failed to create game on Girudo") -> None:
        super().__init__(message)

def encode_password(raw_password: str) -> str:
    try:
        return base64.b64encode(raw_password.encode("utf-8")).decode("utf-8")
    except Exception:
        return raw_password

def get_accounts() -> list[tuple[str, str]]:
    emails = settings.GIRUDO_EMAILS
    passwords = settings.GIRUDO_PASSWORDS
    if not emails or not passwords:
        return []
    return list(
        zip(
            emails.split(","),
            passwords.split(","),
            strict=True,
        ),
    )


async def pick_account(accounts: list[tuple[str, str]]) -> tuple[str, str]:
    global ROUND_ROBIN
    async with ROUND_ROBIN_LOCK:
        if ROUND_ROBIN is None:
            ROUND_ROBIN = randint(0, len(accounts) - 1)
        email, password = accounts[ROUND_ROBIN % len(accounts)]
        ROUND_ROBIN += 1
        return email, password

async def get_user_lock(email: str) -> asyncio.Lock:
    async with USER_LOCKS_LOCK:
        if email not in USER_LOCKS:
            USER_LOCKS[email] = asyncio.Lock()
        return USER_LOCKS[email]


async def authenticate(
    client: httpx.AsyncClient,
    email: str | None = None,
    password: str | None = None,
) -> str | None:
    email = email
    raw_password = password or ""
    encoded_password = encode_password(raw_password)


    payload = {
        "email": email,
        "username": "",
        "password": encoded_password,
        "provider": "",
        "token": "",
        "code_verifier": "",
        "latitude": None,
        "longitude": None,
    }

    try:
        resp = await client.post(settings.GIRUDO_AUTH_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        token = (
            (data.get("data") or {}).get("token")
            or data.get("token")
            or data.get("access_token")
            or (data.get("data") or {}).get("access_token")
        )
        return token
    except Exception as ex:
        logger.warning("Girudo authentication failed: %s", ex, exc_info=True)
        return None


async def authenticate_with_token(
    client: httpx.AsyncClient,
    token: str | None = None,
    email: str | None = None,
    password: str | None = None,
) -> str | None:
    if token:
        return token
    return await authenticate(client, email=email, password=password)

async def create_game(
    client: httpx.AsyncClient,
    token: str,
    game: GameDict,
    *,
    game_title: str | None = None,
    trading_card_game_uuid: str | None = None,
    player_count: int | None = None,
    format_uuid: str | None = None,
    format_name: str | None = None,
) -> str | None:
    headers = {"Authorization": f"Bearer {token}"}
    
    if format_uuid and format_name:
        girudo_format = GirudoGameFormat(uuid=format_uuid, name=format_name)
    else:
        sb_game_format = GameFormat(game["format"])
        girudo_format = girudo_game_format(sb_game_format)
    
    tcg_uuid = trading_card_game_uuid or settings.GIRUDO_DEFAULT_TCG_MAGIC_UUID
    tcg_name = (TCG_NAMES_CACHE or {}).get(tcg_uuid, get_default_tcg()[1])
    
    payload: dict[str, Any] = {
        "game_title": game_title or f"SB{game['id']}",
        "game_format_uuid": girudo_format.uuid,
        "game_format_name": girudo_format.name,
        "player_count": player_count or GameFormat(game["format"]).players,
        "privacy": "public",
        "tagline": "game",
        "trading_card_game_uuid": tcg_uuid,
        "trading_card_game_name": tcg_name,
    }

    try:
        resp = await client.post(settings.GIRUDO_CREATE_URL, json=payload, headers=headers)
        data = resp.json()
        status = resp.status_code

        # Expecting HTTP 201 for created
        if status == 201:
            game_uuid = (data.get("data") or {}).get("game_uuid")
            if game_uuid:
                return f"{settings.GIRUDO_BASE_URL.replace('api.', 'game.')}/join-game/{game_uuid}?type=player"
            logger.warning("Girudo game created but no game_uuid returned")
            return None

        msg = data.get("message") if isinstance(data, dict) else None
        logger.warning("Girudo create game failed (status=%s): %s", status, msg)
        return None

    except Exception as ex:
        logger.warning("Girudo create game error: %s", ex, exc_info=True)
        return None


async def fetch_lobbies(
    client: httpx.AsyncClient,
    token: str,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = await client.get(settings.GIRUDO_LOBBY_URL, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data") or {}
    except Exception as ex:
        logger.warning("Girudo fetch lobbies failed: %s", ex, exc_info=True)
        return {}

async def get_available_lobby(
    client: httpx.AsyncClient,
    token: str,
) -> str | None:
    lobbies = await fetch_lobbies(client, token)

    for game_uuid, info in lobbies.items():
        try:
            curr = int(info.get("current_player_count", 0))
            maxp = int(info.get("max_players", 0))
        except (ValueError, TypeError):
            continue
        if curr < maxp:
            return f"{settings.GIRUDO_BASE_URL.replace('api.', 'game.')}/join-game/{game_uuid}?type=player"

    return None


async def generate_link(
    game: GameDict,
    *,
    game_title: str | None = None,
    trading_card_game_uuid: str | None = None,
    player_count: int | None = None,
) -> GirudoLinkDetails:
    accounts = get_accounts()
    if not accounts:
        logger.error("No Girudo accounts configured (GIRUDO_EMAILS/GIRUDO_PASSWORDS)")
        return GirudoLinkDetails()

    timeout = _create_timeout()
    retry_attempts = settings.GIRUDO_RETRY_ATTEMPTS

    for attempt in range(retry_attempts):
        email, password = await pick_account(accounts)
        user_lock = await get_user_lock(email)

        async with user_lock, httpx.AsyncClient(timeout=timeout) as client:
            try:
                auth_token = await authenticate(client, email=email, password=password)
                if not auth_token:
                    logger.warning(
                        "Girudo auth failed (attempt %s/%s, email=%s)",
                        attempt + 1,
                        retry_attempts,
                        email,
                    )
                    continue
                
                if attempt == 0:
                    if GIRUDO_FORMATS_CACHE is None:
                        await fetch_and_cache_formats(client, auth_token)
                    if TCG_NAMES_CACHE is None:
                        await fetch_and_cache_tcg_names(client, auth_token)

                link = await create_game(
                    client,
                    auth_token,
                    game,
                    game_title=game_title,
                    trading_card_game_uuid=trading_card_game_uuid,
                    player_count=player_count,
                )
                if link:
                    return GirudoLinkDetails(link=link)

            except Exception as ex:
                add_span_error(ex)
                is_final_attempt = attempt == retry_attempts - 1
                if is_final_attempt:
                    logger.exception("Girudo API failure (final attempt, email=%s):", email)
                    return GirudoLinkDetails()
                
                logger.warning(
                    "Girudo API issue (attempt %s/%s, email=%s):",
                    attempt + 1,
                    retry_attempts,
                    email,
                    exc_info=True,
                )

    return GirudoLinkDetails()
