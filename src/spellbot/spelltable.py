from __future__ import annotations

import json
import logging
from typing import Any, Optional

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

    data: Optional[dict[str, Any]] = None
    raw_data: Optional[bytes] = None
    try:
        async with RetryClient(
            raise_for_status=False,
            retry_options=ExponentialRetry(attempts=5),
        ) as client:
            async with client.post(settings.SPELLTABLE_CREATE, headers=headers) as resp:
                # Rather than use `resp.json()`, which respects minetype, let's just
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
                wizards_url = returned_url.replace(
                    "www.spelltable.com",
                    "spelltable.wizards.com",
                )
                return wizards_url
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
        add_span_error(ex)
        logger.error(
            "error: unexpected exception: %s, data: %s, raw: %s",
            ex,
            data,
            raw_data,
            exc_info=True,
        )
        return None
