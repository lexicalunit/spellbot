import logging
from typing import Optional

from aiohttp.client_exceptions import ClientError
from aiohttp_retry import ExponentialRetry, RetryClient

from . import __version__
from .metrics import add_span_error
from .settings import Settings

logger = logging.getLogger(__name__)


async def generate_link() -> Optional[str]:
    settings = Settings()
    assert settings.SPELLTABLE_AUTH_KEY

    headers = {
        "user-agent": f"spellbot/{__version__}",
        "key": settings.SPELLTABLE_AUTH_KEY,
    }

    try:
        async with RetryClient(
            raise_for_status=False,
            retry_options=ExponentialRetry(attempts=5),
        ) as client:
            async with client.post(settings.SPELLTABLE_CREATE, headers=headers) as resp:
                data = await resp.json()
                if "gameUrl" not in data:
                    logger.warning(
                        "warning: gameUrl missing from SpellTable API response (%s): %s",
                        resp.status,
                        data,
                    )
                    return None
                returned_url = str(data["gameUrl"])
                wizards_url = returned_url.replace(
                    "www.spelltable.com",
                    "spelltable.wizards.com",
                )
                return wizards_url
    except ClientError as ex:
        add_span_error(ex)
        logger.warning("warning: SpellTable API failure: %s", ex, exc_info=True)
        return None
