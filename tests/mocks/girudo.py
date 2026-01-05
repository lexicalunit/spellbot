from __future__ import annotations

from typing import Any

from spellbot.integrations.girudo import GirudoGameFormat, GirudoLinkDetails


class MockHTTPResponse:
    """Mock HTTP response for testing Girudo integration without network calls."""

    def __init__(self, status_code: int = 200, json_data: dict | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self) -> None:
        """Raise exception for error status codes."""
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self) -> dict:
        """Return JSON data."""
        return self._json_data


class MockHTTPClient:
    """Mock HTTP client for testing Girudo integration without network calls."""

    def __init__(self, response: MockHTTPResponse | None = None):
        self.response = response or MockHTTPResponse()
        self.get_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []

    async def get(self, url: str, **kwargs: Any) -> MockHTTPResponse:
        """Mock GET request."""
        self.get_calls.append((url, kwargs))
        return self.response

    async def post(self, url: str, **kwargs: Any) -> MockHTTPResponse:
        """Mock POST request."""
        self.post_calls.append((url, kwargs))
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
    def auth_response(cls, token: str | None = None) -> dict:
        """Generate authentication success response."""
        return {"data": {"token": token or cls.AUTH_TOKEN}}

    @classmethod
    def formats_response(cls) -> dict:
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
    def tcg_names_response(cls) -> dict:
        """Generate TCG names success response."""
        return {
            "status": "success",
            "data": {
                "store_games": [
                    {"id": cls.TCG_MAGIC_UUID, "name": cls.TCG_MAGIC_NAME},
                    {"id": cls.TCG_POKEMON_UUID, "name": cls.TCG_POKEMON_NAME},
                ]
            },
        }

    @classmethod
    def create_game_response(cls, game_uuid: str | None = None) -> dict:
        """Generate create game success response."""
        return {"data": {"game_uuid": game_uuid or cls.GAME_UUID}}

    @classmethod
    def lobbies_response(cls) -> dict:
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
            }
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


def create_mock_game(game_id: int = 42, game_format: int = 1) -> dict:
    """Create a mock game dictionary for testing."""
    return {
        "id": game_id,
        "format": game_format,
    }


def mock_girudo_link_result(
    link: str | None = None,
    password: str | None = None,
) -> GirudoLinkDetails:
    """Create a GirudoLinkDetails instance for testing."""
    return GirudoLinkDetails(link=link, password=password)
