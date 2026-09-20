# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, TypedDict

import httpx

from spellbot import __version__, services
from spellbot.enums import GameBracket, GameFormat
from spellbot.integrations.http_errors import describe_http_error, is_terminal_client_error
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from spellbot.data import GameData, PlayerDataDict

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = ["de", "en", "es", "fr", "it", "ja", "pt"]
RETRY_ATTEMPTS = 3
TIMEOUT_S = 3


class ConvokeGameTypes(Enum):
    Commander = "commander"
    Standard = "standard"
    Modern = "modern"
    Planechase = "planechase-commander"
    Horde = "horde-commander"
    Other = "other"


class LiveGuildWar(TypedDict):
    id: str
    title: str
    slug: str
    status: str


# Seat bounds Convoke enforces on Guild War matches. These are the single source of
# truth for the `/war` seat choices, the validation in `LookingForGameAction`, and the
# error message shown when a channel's default seat count falls outside them.
MIN_WAR_SEATS = 2
MAX_WAR_SEATS = 8
DEFAULT_WAR_SEATS = 4


def convoke_game_format(format: GameFormat) -> ConvokeGameTypes:
    match format:
        case (
            GameFormat.COMMANDER
            | GameFormat.EDH_MAX
            | GameFormat.EDH_HIGH
            | GameFormat.EDH_MID
            | GameFormat.EDH_LOW
            | GameFormat.EDH_BATTLECRUISER
            | GameFormat.PRE_CONS
            | GameFormat.CEDH
            | GameFormat.PAUPER_EDH
        ):
            return ConvokeGameTypes.Commander
        case GameFormat.MODERN:
            return ConvokeGameTypes.Modern
        case GameFormat.STANDARD:
            return ConvokeGameTypes.Standard
        case GameFormat.HORDE_MAGIC:
            return ConvokeGameTypes.Horde
        case GameFormat.PLANECHASE:
            return ConvokeGameTypes.Planechase
        case _:
            return ConvokeGameTypes.Other


async def fetch_live_guild_wars(client: httpx.AsyncClient) -> list[LiveGuildWar]:
    """Return Guild Wars currently open for matchmaking on Convoke."""
    endpoint = f"{settings.CONVOKE_ROOT}/guild-wars/live"
    headers = {"user-agent": f"spellbot/{__version__}"}
    resp = await client.get(endpoint, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    wars_raw = data.get("wars") if isinstance(data, dict) else None
    if not isinstance(wars_raw, list):
        return []

    wars: list[LiveGuildWar] = []
    for row in wars_raw:
        if not isinstance(row, dict):
            continue
        war_id = row.get("id")
        title = row.get("title")
        slug = row.get("slug")
        status = row.get("status")
        if not isinstance(war_id, str) or not isinstance(title, str):
            continue
        wars.append(
            {
                "id": war_id,
                "title": title,
                "slug": slug if isinstance(slug, str) else war_id,
                "status": status if isinstance(status, str) else "active",
            },
        )
    return wars


async def get_live_guild_wars() -> list[LiveGuildWar]:
    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            return await fetch_live_guild_wars(client)
        except Exception as ex:
            add_span_error(ex)
            logger.exception("Failed to fetch live Convoke Guild Wars")
            return []


async def resolve_live_guild_war(war_id: str) -> LiveGuildWar | None:
    wars = await get_live_guild_wars()
    for war in wars:
        if war["id"] == war_id or war["slug"] == war_id:
            return war
    return None


def roster_payload(
    players: list[PlayerDataDict],
    pins: dict[int, str] | None,
) -> dict[str, Any]:
    """Build the Discord players and their pins, which Convoke pairs up by list index."""
    payload: dict[str, Any] = {
        "discordPlayers": [{"id": str(p["xid"]), "name": p["name"]} for p in players],
    }
    if pins:
        payload["spellbotGamePins"] = [pins[p["xid"]] for p in players]
    return payload


def request_headers() -> dict[str, str]:
    return {
        "user-agent": f"spellbot/{__version__}",
        "x-api-key": settings.CONVOKE_API_KEY or "",
    }


async def request_with_retries[T](request: Callable[[httpx.AsyncClient], Awaitable[T]]) -> T | None:
    """Run a Convoke API request, retrying on failure. Returns `None` if every attempt fails."""
    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                return await request(client)
            except Exception as ex:
                details = describe_http_error(ex)
                is_final_attempt = attempt == RETRY_ATTEMPTS - 1
                if is_final_attempt or is_terminal_client_error(ex):
                    add_span_error(ex)
                    logger.exception("Convoke API failure. %s", details)
                    return None
                logger.warning(
                    "Convoke API issue (attempt %s). %s",
                    attempt + 1,
                    details,
                    exc_info=True,
                )
    return None


async def fetch_convoke_link(
    client: httpx.AsyncClient,
    game_data: GameData,
    pins: dict[int, str] | None,
) -> dict[str, Any]:
    name = f"SB{game_data.id}"
    sb_game_format = GameFormat(game_data.format)
    format = convoke_game_format(sb_game_format).value
    players = await services.games.player_convoke_data(game_data.id)
    game_language = "en"
    for supported_locale in SUPPORTED_LOCALES:
        if game_data.locale.startswith(supported_locale):
            game_language = supported_locale
            break
    payload: dict[str, Any] = {
        "isPublic": False,
        "name": name,
        "spellbotGameId": str(game_data.id),
        "seatLimit": game_data.seats,
        "format": format,
        "discordGuild": str(game_data.guild_xid),
        "discordChannel": str(game_data.channel_xid),
        **roster_payload(players, pins),
        "language": game_language,
    }
    if game_data.bracket != GameBracket.NONE.value:
        payload["bracketLevel"] = f"B{game_data.bracket - 1}"
    if game_data.format == GameFormat.PRE_CONS.value:
        payload["bracketLevel"] = "PRECON"  # Convoke uses Bracket to indicate "pre-cons"
    if game_data.channel.competitive_mode:
        # Only sent when the channel opts in. Convoke defaults this to on for B5 games, so
        # sending `False` for an opted-out channel would suppress that behavior.
        payload["competitiveMode"] = True
    if game_data.war_id:
        # Open seating: Convoke infers guild splits from who sits.
        payload["warId"] = game_data.war_id
    endpoint = f"{settings.CONVOKE_ROOT}/game/create-game"
    resp = await client.post(endpoint, json=payload, headers=request_headers())
    resp.raise_for_status()
    return resp.json()


async def generate_link(
    game_data: GameData,
    pins: dict[int, str] | None,
) -> tuple[str | None, str | None]:
    if not settings.CONVOKE_API_KEY:
        return None, None

    data = await request_with_retries(
        lambda client: fetch_convoke_link(client, game_data, pins),
    )
    if not data:
        return None, None
    return data["url"], data.get("password")


def convoke_game_id(game_link: str) -> str:
    """Convoke game links look like `https://www.convoke.games/en/play/<id>`."""
    return game_link.rstrip("/").rsplit("/", 1)[-1]


async def put_convoke_players(
    client: httpx.AsyncClient,
    game_data: GameData,
    pins: dict[int, str],
) -> None:
    assert game_data.game_link
    players = await services.games.player_convoke_data(game_data.id)
    game_id = convoke_game_id(game_data.game_link)
    endpoint = f"{settings.CONVOKE_ROOT}/game/{game_id}/spellbot-players"
    payload = roster_payload(players, pins)
    resp = await client.put(endpoint, json=payload, headers=request_headers())
    resp.raise_for_status()


async def update_players(game_data: GameData, pins: dict[int, str]) -> None:
    """
    Send Convoke the final roster and pins for a game whose link was created early.

    Guild War tables are opened on Convoke before the SpellBot queue fills, so the roster sent
    to create-game only has the players who had joined by then.
    """
    if not settings.CONVOKE_API_KEY or not game_data.game_link:
        return
    await request_with_retries(lambda client: put_convoke_players(client, game_data, pins))
