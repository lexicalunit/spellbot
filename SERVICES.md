# External Services

At the time of this writing SpellBot can create games on SpellTable and TableStream. This document explains how to add support for additional services.

## Update the GameService enum

In `src/spellbot/enums.py` add a new entry to the `GameService` enum. For example:

```python
class GameService(Enum):
    ...

    TTS = "TabletopSim"
    TABLE_STREAM = "Table Stream"
    NEW_SERVICE = "Your New Service"  # <-- add this line
```

Then update the `GAME_SERVICE_ORDER` list to include the new service. This list controls the order in which services are presented to the user.

## Update the create_game_link() function

In `src/spellbot/client.py` there is a `create_game_link()` function. Add a new `case` statement to the function to handle the new service. For example:

```python
from . import new_service  # <-- add this import (you will need to create this file)

def create_game_link(self, game: Game) -> str:
    ...
    match service:
        ...
        case GameService.NEW_SERVICE.value:
            info = await new_service.generate_link(game)
            return GameLinkDetails(link=info.link, password=info.password)
```

At the time of this writing the `GameLinkDetails` only supports `link` and optionally `password`. If your service requires additional information you will need to update the `GameLinkDetails` class to include it.

## Implement the generate_link() function

Create a new file in `src/spellbot/` for your service. For example `src/spellbot/new_service.py`. In that file implement the `generate_link()` function. Please use `httpx.AsyncClient` for all requests.

> **IMPORTANT**: Ensure that all requests are made asynchronously! If you do not do this you will block the event loop and the bot will become unresponsive.

## Handle your service in the Game model

In `src/spellbot/models/game.py` there is a `Game` model which represents games managed by SpellBot. Of particular interest is the `embed_description()` function which you will need to update to properly handle your new service. There are a number of custom messages that depend on the service; This could probably be refactored to be more generic.

## Update the test suite

There are a number of tests that you will need to either extend or create. Please try to maintain the test coverage as best as you can. However, please do not add any tests that require network access. To maintain coverage you can utilize mocks to simulate network requests (preferred) or (if you're lazy like me) add `# pragma: no cover` to skip coverage checks.
