from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Self, cast

from httpx import AsyncClient

from spellbot.data import GameData, UserData
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import ChannelDict, GameStatus

if TYPE_CHECKING:
    from types import TracebackType

from spellbot.integrations.girudo import GirudoGameFormat


class HTTPError(Exception):
    """Mock HTTP error for testing."""


class MockHTTPResponse:
    """Mock HTTP response for testing Girudo integration without network calls."""

    def __init__(self, status_code: int = 200, json_data: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self) -> None:
        """Raise exception for error status codes."""
        if self.status_code >= 400:
            msg = f"HTTP {self.status_code}"
            raise HTTPError(msg)

    def json(self) -> dict[str, Any]:
        """Return JSON data."""
        return self._json_data


class MockHTTPClient(AsyncClient):
    def __init__(self, response: MockHTTPResponse | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.response = response or MockHTTPResponse()
        self.get_calls: list[tuple[str, dict[str, Any]]] = []
        self.post_calls: list[tuple[str, dict[str, Any]]] = []

    async def get(self, url: str, **kwargs: Any) -> MockHTTPResponse:
        """Mock GET request."""
        self.get_calls.append((url, kwargs))
        return self.response

    async def post(self, url: str, **kwargs: Any) -> MockHTTPResponse:
        """Mock POST request."""
        self.post_calls.append((url, kwargs))
        return self.response

    async def __aenter__(self) -> Self:  # pragma: no cover
        return self

    async def __aexit__(  # pragma: no cover
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        await super().__aexit__(exc_type, exc_val, exc_tb)
        return False


# Test Data Constants
class GirudoTestData:
    """Reusable test data for Girudo integration tests."""

    # Authentication
    AUTH_TOKEN = "test-token-123"
    AUTH_EMAIL = "user@example.com"
    AUTH_PASSWORD = "password123"

    # API URLs
    API_BASE_URL = "https://api.example.com"
    GAME_BASE_URL = "https://game.example.com"

    # Game Format IDs and Names
    FORMAT_COMMANDER_UUID = "fmt-commander-uuid"
    FORMAT_COMMANDER_NAME = "Commander/EDH"
    FORMAT_STANDARD_UUID = "fmt-standard-uuid"
    FORMAT_STANDARD_NAME = "Standard"
    FORMAT_DEFAULT_UUID = "fmt-default-uuid"
    FORMAT_DEFAULT_NAME = "Default Format"

    # TCG IDs and Names
    TCG_MAGIC_UUID = "tcg-magic-uuid"
    TCG_MAGIC_NAME = "Magic: The Gathering"
    TCG_POKEMON_UUID = "tcg-pokemon-uuid"
    TCG_POKEMON_NAME = "Pokemon"

    # Game UUIDs
    GAME_UUID = "game-123-uuid"
    LOBBY_UUID_AVAILABLE = "lobby-available-uuid"
    LOBBY_UUID_FULL = "lobby-full-uuid"

    @classmethod
    def auth_response(cls, token: str | None = None) -> dict[str, Any]:
        """Generate authentication success response."""
        return {"data": {"token": token or cls.AUTH_TOKEN}}

    @classmethod
    def formats_response(cls) -> dict[str, Any]:
        """Generate format list success response."""
        return {
            "status": "success",
            "data": [
                {
                    "game_format_id": cls.FORMAT_COMMANDER_UUID,
                    "game_format_name": cls.FORMAT_COMMANDER_NAME,
                },
                {
                    "game_format_id": cls.FORMAT_STANDARD_UUID,
                    "game_format_name": cls.FORMAT_STANDARD_NAME,
                },
            ],
        }

    @classmethod
    def tcg_names_response(cls) -> dict[str, Any]:
        """Generate TCG names success response."""
        return {
            "status": "success",
            "data": {
                "store_games": [
                    {"id": cls.TCG_MAGIC_UUID, "name": cls.TCG_MAGIC_NAME},
                    {"id": cls.TCG_POKEMON_UUID, "name": cls.TCG_POKEMON_NAME},
                ],
            },
        }

    @classmethod
    def create_game_response(cls, game_uuid: str | None = None) -> dict[str, Any]:
        """Generate create game success response."""
        return {"data": {"game_uuid": game_uuid or cls.GAME_UUID}}

    @classmethod
    def lobbies_response(cls) -> dict[str, Any]:
        """Generate lobbies list response."""
        return {
            "data": {
                cls.LOBBY_UUID_AVAILABLE: {
                    "current_player_count": 2,
                    "max_players": 4,
                },
                cls.LOBBY_UUID_FULL: {
                    "current_player_count": 4,
                    "max_players": 4,
                },
            },
        }

    @classmethod
    def formats_cache(cls) -> dict[str, GirudoGameFormat]:
        """Generate pre-populated formats cache."""
        return {
            "commander_edh": GirudoGameFormat(
                uuid=cls.FORMAT_COMMANDER_UUID,
                name=cls.FORMAT_COMMANDER_NAME,
            ),
            "standard": GirudoGameFormat(
                uuid=cls.FORMAT_STANDARD_UUID,
                name=cls.FORMAT_STANDARD_NAME,
            ),
        }

    @classmethod
    def tcg_cache(cls) -> dict[str, str]:
        """Generate pre-populated TCG names cache."""
        return {
            cls.TCG_MAGIC_UUID: cls.TCG_MAGIC_NAME,
            cls.TCG_POKEMON_UUID: cls.TCG_POKEMON_NAME,
        }


def create_mock_game(
    game_id: int = 42,
    game_format: int | None = None,
    service: int | None = None,
    seats: int = 4,
    guild_xid: int = 12345,
    channel_xid: int = 67890,
    bracket: int | None = None,
    **kwargs: Any,
) -> GameData:
    """Create a mock GameData object for testing."""
    now = datetime.now(tz=UTC)
    return GameData(
        id=game_id,
        created_at=now,
        updated_at=now,
        started_at=None,
        deleted_at=None,
        guild_xid=guild_xid,
        guild={  # type: ignore[arg-type]
            "xid": guild_xid,
            "name": "Test Guild",
            "notice": None,
            "motd": None,
            "show_links": True,
            "enable_mythic_track": True,
        },
        channel_xid=channel_xid,
        channel=cast(
            "ChannelDict",
            {
                "xid": channel_xid,
                "name": "test-channel",
                "motd": None,
            },
        ),
        voice_xid=None,
        voice_invite_link=None,
        seats=seats,
        status=GameStatus.PENDING.value,
        format=game_format if game_format is not None else GameFormat.COMMANDER.value,
        bracket=bracket if bracket is not None else GameBracket.NONE.value,
        service=service if service is not None else GameService.CONVOKE.value,
        game_link=None,
        password=None,
        rules=None,
        blind=False,
        players=[],
        posts=[],
        player_pins={},
    )


def create_mock_user(
    xid: int = 123,
    name: str = "TestPlayer",
    banned: bool = False,
) -> UserData:
    """Create a mock UserData object for testing."""
    now = datetime.now(tz=UTC)
    return UserData(
        xid=xid,
        created_at=now,
        updated_at=now,
        name=name,
        banned=banned,
    )
