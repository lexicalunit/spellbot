# Integrations with external services

At the time of this writing SpellBot can create games on [Convoke][convoke], [Girudo][girudo], [Playgroup Live][playgroup], [EDHLAB][edhlab], and [Table Stream][tablestream]. This document explains how to add support for additional services.

## Update the GameService enum

In `src/spellbot/enums.py` add a new entry to the `GameService` enum. Each entry is a tuple of `(title, translation_key, fallback_url, max_seats)`:

```python
class GameService(Enum):
    ...

    # DO NOT REORDER -- IT WOULD INVALIDATE EXISTING DATABASE ENTRIES!
    TTS = "TabletopSim", "tts", None, 10
    TABLE_STREAM = "Table Stream", "table_stream", "https://table-stream.com/", 6
    # Add your new service here:
    NEW_SERVICE = "Your New Service", "new_service", "https://your-new-service.com/", 6
```

The `translation_key` is looked up under `service.<key>` in the translation files (see below). The `fallback_url` is used when SpellBot is unable to create a link for the game. The `max_seats` is the maximum number of players the service can host in a single game.

Then update the `GAME_SERVICE_ORDER` list to include the new service. This list controls the order in which services are presented to the user. Entries may be conditionally included based on configuration (for example, `PLAYGROUP_LIVE` is only listed when `PLAYGROUP_LIVE_API_KEY` is set).

## Add translations for the pending message

In `src/spellbot/translations/<locale>.yaml` add an entry under the `service:` key matching the `translation_key` you used above. For example in `en.yaml`:

```yaml
en:
  service:
    new_service: "_A %{emoji}[Your New Service](https://your-new-service.com/) link will be created when all players have joined._"
```

This message is shown in the game embed while the game is waiting for players. Add an entry for each supported locale (`da`, `de`, `el`, `en`, `es`, …).

## Add configuration settings

In `src/spellbot/settings.py` add any settings your integration requires, such as API keys or endpoint URLs. For example:

```python
# New Service
NEW_SERVICE_API_KEY: str | None = None
NEW_SERVICE_ROOT: str = "https://api.your-new-service.com"
```

## Implement the generate_link() function

Create a new file `src/spellbot/integrations/new_service.py` and implement a `generate_link()` function. It should return a `tuple[str | None, str | None]` of `(link, password)`, returning `(None, None)` on failure. Use `httpx.AsyncClient` for all requests.

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from spellbot import __version__
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.data import GameData

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
TIMEOUT_S = 3


async def generate_link(game_data: GameData) -> tuple[str | None, str | None]:
    if not settings.NEW_SERVICE_API_KEY:
        return None, None
    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as client:
        ...
    return link, password
```

> **IMPORTANT**: Ensure that all requests are made asynchronously! If you do not do this you will block the event loop and the bot will become unresponsive.

## Update the create_game_link() function

In `src/spellbot/client.py` there is a `create_game_link()` function. Import your new integration module and add a `case` for it:

```python
from .integrations import convoke, edhlab, girudo, new_service, playgroup_live, tablestream

async def create_game_link(
    self,
    game_data: GameData,
    pins: list[str] | None = None,
    original_seats: int | None = None,
) -> GameLinkDetails:
    ...
    match service:
        ...
        case GameService.NEW_SERVICE.value:
            details = await new_service.generate_link(game_data)
            return GameLinkDetails(*details)
```

`GameLinkDetails` (defined in `src/spellbot/data/game_data.py` and re-exported from `spellbot.data`) currently only supports `link` and optionally `password`. If your service requires additional information you will need to update the `GameLinkDetails` dataclass to include it. You will also need to update the `Game` model in `src/spellbot/models/game.py` to persist that information on the database side so that it can be included in the game embed.

## Handle your service in the Game model

In `src/spellbot/models/game.py` there is a `Game` model which represents games managed by SpellBot. The corresponding `GameData` dataclass in `src/spellbot/data/game_data.py` exposes embed-building methods such as `to_embed()`, `embed_description_link_info()`, and `embed_description_extras()` — these may need to be updated to properly handle your new service, especially if you added additional information to the `GameLinkDetails` class.

## Update the test suite

Add a `tests/integrations/test_new_service.py` file mirroring the existing ones (`test_convoke.py`, `test_girudo.py`, `test_edhlab.py`, `test_tablestream.py`, `test_playgroup_live.py`). Please try to maintain the test coverage as best as you can. However, please do not add any tests that require network access. To maintain coverage you can utilize mocks to simulate network requests (preferred) or (if you're lazy like me) add `# pragma: no cover` to skip coverage checks.

[convoke]: https://www.convoke.games/
[edhlab]: https://edhlab.gg/
[girudo]: https://www.girudo.com/
[playgroup]: https://playgroup.gg/
[tablestream]: https://table-stream.com/
