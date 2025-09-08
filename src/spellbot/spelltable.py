from __future__ import annotations

import asyncio
import logging
from enum import Enum
from random import randint
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import requests

from spellbot.enums import GameFormat
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)

ROUND_ROBIN = None
TIMEOUT_S = 3


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


async def generate_spelltable_link(  # pragma: no cover  # noqa: PLR0915
    game: GameDict,
) -> str | None:
    global ROUND_ROBIN  # noqa: PLW0603

    assert settings.SPELLTABLE_USERS is not None
    assert settings.SPELLTABLE_PASSES is not None

    accounts = list(
        zip(
            settings.SPELLTABLE_USERS.split(","),
            settings.SPELLTABLE_PASSES.split(","),
            strict=True,
        )
    )

    # if we haven't started round robin, pick a random starting point
    if ROUND_ROBIN is None:
        ROUND_ROBIN = randint(0, len(accounts) - 1)  # noqa: S311

    retries = 3
    link: str | None = None
    for attempt in range(retries):
        session = requests.Session()

        # round robin through the accounts, pick a new account each time
        username, password = accounts[ROUND_ROBIN % len(accounts)]
        ROUND_ROBIN += 1

        try:
            # Step 1: Get CSRF token (set in session cookies)
            csrf_resp = session.get("https://myaccounts.wizards.com/login", timeout=TIMEOUT_S)
            csrf_resp.raise_for_status()
            csrf_token = session.cookies.get("_csrf")
            if not csrf_token:
                logger.warning("warning: no csrf token found in login response")
                continue

            # Step 2: Login
            login_url = "https://myaccounts.wizards.com/api/login"
            login_payload = {
                "username": username,
                "password": password,
                "referringClientID": settings.SPELLTABLE_CLIENT_ID,
                "remember": False,
                "_csrf": csrf_token,
            }
            login_resp = session.post(login_url, json=login_payload, timeout=TIMEOUT_S)
            login_resp.raise_for_status()

            # Step 2: Get client info
            client_url = "https://myaccounts.wizards.com/api/client"
            client_payload = {
                "clientID": settings.SPELLTABLE_CLIENT_ID,
                "language": "en-US",
                "_csrf": csrf_token,
            }
            client_resp = session.post(client_url, json=client_payload, timeout=TIMEOUT_S)
            client_resp.raise_for_status()

            # Step 3: Authorize client (SpellTable)
            auth_url = "https://myaccounts.wizards.com/api/authorize"
            auth_payload = {
                "clientInput": {
                    "clientID": settings.SPELLTABLE_CLIENT_ID,
                    "redirectURI": "https://spelltable.wizards.com/auth/authorize",
                    "scope": "email",
                    "state": "",
                    "version": "2",
                },
                "_csrf": csrf_token,
            }
            auth_resp = session.post(
                auth_url,
                json=auth_payload,
                allow_redirects=False,
                timeout=TIMEOUT_S,
            )
            auth_resp.raise_for_status()

            # Step 4: Extract code from JSON response
            redirect_target = auth_resp.json().get("data", {}).get("redirect_target")
            if not redirect_target:
                logger.warning("No redirect_target found in authorize response")
                continue

            parsed = urlparse(redirect_target)
            query_params = parse_qs(parsed.query)
            code = query_params.get("code", [None])[0]
            if not code:
                logger.warning("No code found in redirect_target query params")
                continue

            # Step 5: Exchange code for access token
            ex_url = "https://xgaqvxzggl.execute-api.us-west-2.amazonaws.com/prod/exchangeCode"
            ex_payload = {"code": code}
            ex_headers = {"x-api-key": settings.SPELLTABLE_API_KEY}
            ex_resp = session.post(ex_url, json=ex_payload, headers=ex_headers, timeout=TIMEOUT_S)
            ex_resp.raise_for_status()
            access_token = ex_resp.json()["access_token"]

            # Step 7: Create the game
            format = spelltable_game_type(GameFormat(game["format"])).value
            create_url = "https://xgaqvxzggl.execute-api.us-west-2.amazonaws.com/prod/createGame"
            create_headers = {"x-api-key": settings.SPELLTABLE_API_KEY}
            create_payload = {
                "token": access_token,
                "name": f"SB{game['id']}",
                "description": "",
                "format": format,
                "isPublic": False,
                "tags": {},
            }
            create_resp = session.post(
                create_url,
                headers=create_headers,
                json=create_payload,
                timeout=TIMEOUT_S,
            )
            create_resp.raise_for_status()
            create_data = create_resp.json()
            link = f"https://spelltable.wizards.com/game/{create_data['id']}"
            break

        except Exception as ex:
            add_span_error(ex)
            if attempt + 1 == retries:
                logger.exception("error: SpellTable API issue (final attempt, user: %s):")
                return None

            logger.warning(
                "warning: SpellTable API issue (attempt %s, user: %s):",
                attempt + 1,
                username,
                exc_info=True,
            )
            await asyncio.sleep(TIMEOUT_S)

        finally:
            session.close()

    return link
