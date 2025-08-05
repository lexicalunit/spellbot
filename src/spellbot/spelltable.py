from __future__ import annotations

import asyncio
import json
import logging
from enum import Enum
from random import randint
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from aiohttp.client_exceptions import ClientError
from aiohttp_retry import ExponentialRetry, RetryClient
from playwright.async_api import Browser, Page, Route, async_playwright

from spellbot import __version__
from spellbot.enums import GameFormat
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)

LOGIN = (
    "https://myaccounts.wizards.com/login?"
    "redirectTo=https://spelltable.wizards.com/lobby?login=true"
)
TIMEOUT_S = 5  # seconds
TIMEOUT_MS = TIMEOUT_S * 1000  # milliseconds
ROUND_ROBIN = None


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


def route_intercept(route: Route) -> Any:
    # if route.request.resource_type in {"image", "media", "font", "stylesheet"}:
    #     return route.abort()
    parsed_url = urlparse(route.request.url)
    hostname = parsed_url.hostname or ""
    if hostname == "spelltable.api.bi.wizards.com":
        return route.abort()
    if hostname == "spelltable.wizards.com" and parsed_url.path.startswith("/game/"):
        return route.abort()
    return route.continue_()


async def prevent_navigation(page: Page) -> None:
    await page.evaluate(
        """
        () => {
            const originalAssign = window.location.assign;
            const originalReplace = window.location.replace;

            window.location.assign = function(url) {
                if (url.includes('https://spelltable.wizards.com/game/')) {
                    console.log("Blocked navigation via assign to:", url);
                } else {
                    originalAssign.call(window.location, url);
                }
            };

            window.location.replace = function(url) {
                if (url.includes('https://spelltable.wizards.com/game/')) {
                    console.log("Blocked navigation via replace to:", url);
                } else {
                    originalReplace.call(window.location, url);
                }
            };
        }
        """
    )


async def generate_spelltable_link(game: GameDict) -> str | None:  # pragma: no cover
    # In 2024 WotC broke the SpellTable API, so we have to use headless mode now.
    return await generate_spelltable_link_headless(game)


async def generate_spelltable_link_headless(  # noqa: C901,PLR0912,PLR0915 # pragma: no cover
    game: GameDict,
) -> str | None:
    """
    Generate a SpellTable link using a headless browser.

    This method of generating a SpellTable link was pioneered and initially implemented
    in node using Puppeteer by @nathvnt (https://github.com/nathvnt). Using this idea
    I then implemented it in Python using Playwright. See the original implementation at:
    https://github.com/nathvnt/spelltable_automation/blob/main/stb-v1.js
    """
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
    if ROUND_ROBIN is None:
        ROUND_ROBIN = randint(0, len(accounts) - 1)  # noqa: S311
    username, password = accounts[ROUND_ROBIN % len(accounts)]
    ROUND_ROBIN += 1

    format_option = spelltable_game_type(GameFormat(game["format"]))

    browser: Browser | None = None
    link: str | None = None
    try:
        async with async_playwright() as p:
            try:
                # launch a headless browser
                browser = await p.chromium.launch(timeout=TIMEOUT_MS)
                page = await browser.new_page()

                # intercept unnecessary requests and prevent navigation to the game,
                # this prevents the bot from joining the game itself
                await prevent_navigation(page)
                await page.route("**/*", route_intercept)

                # load the login page
                await page.goto(LOGIN, timeout=TIMEOUT_MS)

                # attempt to accept cookies if there is a prompt to do so
                try:
                    await page.wait_for_selector("button[type='submit']", timeout=TIMEOUT_MS)
                    await page.locator("button").get_by_text("Accept All").click(timeout=TIMEOUT_MS)
                except Exception:
                    logger.warning("failed to accept cookies, continuing: (user: %s)", username)

                # login
                await page.fill("input[name='email']", username, timeout=TIMEOUT_MS)
                await page.fill("input[name='password']", password, timeout=TIMEOUT_MS)
                await page.click("button[type='submit']", timeout=TIMEOUT_MS * 2)
                await page.wait_for_selector("text=Create Game", timeout=TIMEOUT_MS)

                # attempt to accept cookies if there is a prompt to do so
                try:
                    # await page.wait_for_selector("button[type='submit']", timeout=TIMEOUT_MS)
                    await page.locator("button").get_by_text("Accept All").click(timeout=TIMEOUT_MS)
                except Exception:
                    logger.warning("failed to accept cookies, continuing: (user: %s)", username)

                # bring up the create game modal
                retries = 0
                while retries < 10:
                    try:
                        button = page.locator("button").get_by_text("Create Game", exact=False)
                        await button.click(timeout=1000)
                        break
                    except Exception:
                        retries += 1
                        if retries >= 10:
                            raise
                        await asyncio.sleep(1)

                # check that the create button is clickable (that we're not rate limited)
                button = page.locator("button").get_by_text("Create", exact=True)
                button_class = await button.get_attribute("class") or ""
                if "hover" not in button_class:
                    logger.warning("spelltable user is rate limited: (user: %s)", username)
                    return None

                # attempt to set the format drop down
                if format_option != SpellTableGameTypes.Commander:
                    try:
                        await page.select_option(
                            "#modal-container select",
                            format_option.value,
                            timeout=TIMEOUT_MS,
                        )
                    except Exception:
                        logger.warning("failed to set format, continuing: (user: %s)", username)

                # attempt to set the room name
                try:
                    await page.wait_for_selector("input[placeholder='Name']", timeout=TIMEOUT_MS)
                    await page.fill(
                        "input[placeholder='Name']",
                        f"SB{game['id']}",
                        timeout=TIMEOUT_MS,
                    )
                except Exception:
                    logger.warning("failed to set room name, continuing: (user: %s)", username)

                # intercept the request to create the game from the SpellTable API
                async with page.expect_response("**/createGame", timeout=TIMEOUT_MS) as info:
                    await (
                        page.locator("button")
                        .get_by_text("Create", exact=True)
                        .click(timeout=TIMEOUT_MS)
                    )

                # pull out the game link from the intercepted response
                resp = await info.value
                data = await resp.json()
                link = f"https://spelltable.wizards.com/game/{data['id']}"
            except Exception as ex:
                add_span_error(ex)
                logger.exception("error: unexpected exception: (user: %s)", username)
            finally:
                if browser:
                    await browser.close()
    except Exception as ex:
        add_span_error(ex)
        logger.exception("error: unexpected exception: (user: %s)", username)
    return link


async def generate_spelltable_link_api(game: GameDict) -> str | None:
    assert settings.SPELLTABLE_AUTH_KEY

    headers = {
        "user-agent": f"spellbot/{__version__}",
        "key": settings.SPELLTABLE_AUTH_KEY,
    }

    data: dict[str, Any] | None = None
    raw_data: bytes | None = None
    try:
        async with (
            RetryClient(
                raise_for_status=False,
                retry_options=ExponentialRetry(attempts=5),
            ) as client,
            client.post(settings.SPELLTABLE_CREATE, headers=headers) as resp,
        ):
            # Rather than use `resp.json()`, which respects mimetype, let's just
            # grab the data and try to decode it ourselves.
            # https://github.com/inyutin/aiohttp_retry/issues/55
            raw_data = await resp.read()
            data = json.loads(raw_data)
            if not data or "gameUrl" not in data:
                logger.warning(
                    "warning: gameUrl missing from SpellTable API response (%s): %s",
                    resp.status,
                    data,
                )
                return None
            assert data is not None
            returned_url = str(data["gameUrl"])
            return returned_url.replace(
                "www.spelltable.com",
                "spelltable.wizards.com",
            )
    except ClientError as ex:
        add_span_error(ex)
        logger.warning(
            "warning: SpellTable API failure: %s, data: %s, raw: %s",
            ex,
            data,
            raw_data,
            exc_info=True,
        )
        return None
    except Exception as ex:
        if raw_data == b"upstream request timeout":
            return None

        add_span_error(ex)
        logger.exception("error: unexpected exception: data: %s, raw: %s", data, raw_data)
        return None
