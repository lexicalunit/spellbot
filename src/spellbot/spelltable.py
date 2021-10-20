import logging
from typing import Optional

from aiohttp.client_exceptions import ClientError
from aiohttp_retry import ExponentialRetry, RetryClient

from spellbot._version import __version__
from spellbot.settings import Settings

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
                return str(data["gameUrl"])
    except ClientError as ex:
        logger.warning("warning: SpellTable API failure: %s", ex, exc_info=True)
        return None
