from __future__ import annotations

import json
import logging
from random import randint
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from aiohttp.client_exceptions import ClientError
from aiohttp_retry import ExponentialRetry, RetryClient
from playwright.async_api import Route, async_playwright

from spellbot import __version__
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


def route_intercept(route: Route) -> Any:
    parsed_url = urlparse(route.request.url)
    if parsed_url.hostname == "spelltable.api.bi.wizards.com":
        return route.abort()
    return route.continue_()


async def generate_spelltable_link(game: GameDict) -> str | None:  # pragma: no cover
    # In 2024 WotC broke the SpellTable API, so we have to use headless mode now.
    return await generate_spelltable_link_headless(game)


async def generate_spelltable_link_headless(game: GameDict) -> str | None:  # pragma: no cover
    """
    Generate a SpellTable link using a headless browser.

    This method of generating a SpellTable link was pioneered and initially implemented
    in node using Puppeteer by @nathvnt (https://github.com/nathvnt). Using this idea
    I then implemented it in Python using Playwright.
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

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(timeout=TIMEOUT_MS)
            page = await browser.new_page()
            await page.route("**/*", route_intercept)
            await page.goto(LOGIN, timeout=TIMEOUT_MS)
            await page.wait_for_selector("button[type='submit']", timeout=TIMEOUT_MS)
            await page.locator("button").get_by_text("Accept All").click(timeout=TIMEOUT_MS)
            await page.fill("input[name='email']", username, timeout=TIMEOUT_MS)
            await page.fill("input[name='password']", password, timeout=TIMEOUT_MS)
            await page.click("button[type='submit']", timeout=TIMEOUT_MS)
            await page.wait_for_selector("text=Create Game", timeout=TIMEOUT_MS)
            await page.click("text=Create Game", timeout=TIMEOUT_MS)
            await page.wait_for_selector("input[placeholder='Name']", timeout=TIMEOUT_MS)
            await page.fill("input[placeholder='Name']", f"SB{game['id']}", timeout=TIMEOUT_MS)
            await page.locator("button").get_by_text("Create", exact=True).click(timeout=TIMEOUT_MS)
            await page.wait_for_selector("text=Join Now", timeout=TIMEOUT_MS)
            link = page.url
            await browser.close()
            return link
    except Exception as ex:
        add_span_error(ex)
        logger.exception("error: unexpected exception: (user: %s)", username)
        return None


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
