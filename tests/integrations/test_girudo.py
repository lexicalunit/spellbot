from __future__ import annotations

import asyncio
import base64
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

import pytest

from spellbot.enums import GameFormat
from spellbot.integrations import girudo
from spellbot.integrations.girudo import GirudoGameFormat
from tests.mocks.girudo import GirudoTestData, MockHTTPClient, MockHTTPResponse, create_mock_game

if TYPE_CHECKING:
    from collections.abc import Generator

    from spellbot.models import GameDict


@pytest.fixture(autouse=True)
def reset_girudo_state() -> Generator[None, None, None]:
    """Reset module-level state between tests."""
    # Store original values
    original_formats = girudo.GIRUDO_FORMATS_CACHE
    original_tcg = girudo.TCG_NAMES_CACHE
    original_rr = girudo.ROUND_ROBIN
    original_locks = dict(girudo.USER_LOCKS)

    # Reset to None
    girudo.GIRUDO_FORMATS_CACHE = None
    girudo.TCG_NAMES_CACHE = None
    girudo.ROUND_ROBIN = None
    girudo.USER_LOCKS.clear()

    yield

    # Restore (cleanup)
    girudo.GIRUDO_FORMATS_CACHE = original_formats
    girudo.TCG_NAMES_CACHE = original_tcg
    girudo.ROUND_ROBIN = original_rr
    girudo.USER_LOCKS = original_locks


class TestGirudoDefaults:
    """Test default getters and utilities."""

    def test_get_default_girudo_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_FORMAT_UUID",
            GirudoTestData.FORMAT_DEFAULT_UUID,
        )
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_FORMAT_NAME",
            GirudoTestData.FORMAT_DEFAULT_NAME,
        )

        result = girudo.get_default_girudo_format()
        assert result.uuid == GirudoTestData.FORMAT_DEFAULT_UUID
        assert result.name == GirudoTestData.FORMAT_DEFAULT_NAME

    def test_get_default_tcg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_TCG_UUID",
            GirudoTestData.TCG_MAGIC_UUID,
        )
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_TCG_NAME",
            GirudoTestData.TCG_MAGIC_NAME,
        )

        uuid, name = girudo.get_default_tcg()
        assert uuid == GirudoTestData.TCG_MAGIC_UUID
        assert name == GirudoTestData.TCG_MAGIC_NAME

    def test_create_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 10)

        timeout = girudo._create_timeout()
        assert timeout.connect == 10
        assert timeout.read == 10
        assert timeout.write == 10

    def test_get_all_girudo_formats_empty(self) -> None:
        girudo.GIRUDO_FORMATS_CACHE = None
        result = girudo.get_all_girudo_formats()
        assert result == {}

    def test_get_all_girudo_formats_with_cache(self) -> None:
        girudo.GIRUDO_FORMATS_CACHE = GirudoTestData.formats_cache()
        result = girudo.get_all_girudo_formats()
        assert "commander_edh" in result
        assert result["commander_edh"].uuid == GirudoTestData.FORMAT_COMMANDER_UUID


class TestGirudoEncoding:
    """Test password encoding."""

    def test_encode_password_success(self) -> None:
        result = girudo.encode_password("mypassword")
        expected = base64.b64encode(b"mypassword").decode("utf-8")
        assert result == expected

    def test_encode_password_unicode(self) -> None:
        result = girudo.encode_password("pássw0rd™")
        expected = base64.b64encode("pássw0rd™".encode()).decode("utf-8")
        assert result == expected

    def test_encode_password_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test encode_password returns raw password on exception."""
        monkeypatch.setattr(
            base64,
            "b64encode",
            lambda _: (_ for _ in ()).throw(ValueError("fail")),
        )
        result = girudo.encode_password("mypassword")
        assert result == "mypassword"


class TestGirudoAccounts:
    """Test account management."""

    def test_get_accounts_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_EMAILS", None)
        monkeypatch.setattr(girudo.settings, "GIRUDO_PASSWORDS", None)

        result = girudo.get_accounts()
        assert result == []

    def test_get_accounts_single(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_EMAILS", GirudoTestData.AUTH_EMAIL)
        monkeypatch.setattr(girudo.settings, "GIRUDO_PASSWORDS", GirudoTestData.AUTH_PASSWORD)

        result = girudo.get_accounts()
        assert result == [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)]

    def test_get_accounts_multiple(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_EMAILS", "user1@example.com,user2@example.com")
        monkeypatch.setattr(girudo.settings, "GIRUDO_PASSWORDS", "pass1,pass2")

        result = girudo.get_accounts()
        assert result == [("user1@example.com", "pass1"), ("user2@example.com", "pass2")]

    @pytest.mark.asyncio
    async def test_pick_account(self) -> None:
        accounts = [("user1@example.com", "pass1"), ("user2@example.com", "pass2")]

        email, password = await girudo.pick_account(accounts)
        assert (email, password) in accounts

    @pytest.mark.asyncio
    async def test_get_user_lock(self) -> None:
        lock1 = await girudo.get_user_lock(GirudoTestData.AUTH_EMAIL)
        assert isinstance(lock1, asyncio.Lock)

        # Should return same lock for same user
        lock2 = await girudo.get_user_lock(GirudoTestData.AUTH_EMAIL)
        assert lock1 is lock2


class TestGirudoAuthentication:
    """Test authentication functions."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_AUTH_URL",
            f"{GirudoTestData.API_BASE_URL}/auth",
        )

        response = MockHTTPResponse(200, GirudoTestData.auth_response())
        client = MockHTTPClient(response)

        token = await girudo.authenticate(
            client,
            email=GirudoTestData.AUTH_EMAIL,
            password=GirudoTestData.AUTH_PASSWORD,
        )
        assert token == GirudoTestData.AUTH_TOKEN
        assert len(client.post_calls) == 1

    @pytest.mark.asyncio
    async def test_authenticate_token_in_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_AUTH_URL",
            f"{GirudoTestData.API_BASE_URL}/auth",
        )

        response = MockHTTPResponse(200, {"token": "root-token"})
        client = MockHTTPClient(response)

        token = await girudo.authenticate(
            client,
            email=GirudoTestData.AUTH_EMAIL,
            password=GirudoTestData.AUTH_PASSWORD,
        )
        assert token == "root-token"

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_AUTH_URL",
            f"{GirudoTestData.API_BASE_URL}/auth",
        )

        response = MockHTTPResponse(401, {"error": "unauthorized"})
        client = MockHTTPClient(response)

        token = await girudo.authenticate(
            client,
            email=GirudoTestData.AUTH_EMAIL,
            password="wrong-password",  # noqa: S106
        )
        assert token is None

    @pytest.mark.asyncio
    async def test_authenticate_no_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test authenticate when GIRUDO_AUTH_URL not configured."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_AUTH_URL", None)
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        token = await girudo.authenticate(client, email="test@test.com", password="pass")  # noqa: S106
        assert token is None


class TestGirudoFormats:
    """Test format fetching and caching."""

    @pytest.mark.asyncio
    async def test_fetch_and_cache_formats_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)
        response = MockHTTPResponse(200, GirudoTestData.formats_response())
        client = MockHTTPClient(response)
        result = await girudo.fetch_and_cache_formats(client, GirudoTestData.AUTH_TOKEN)
        assert "commander/edh" in result
        assert "standard" in result
        assert result["commander/edh"].uuid == GirudoTestData.FORMAT_COMMANDER_UUID

    @pytest.mark.asyncio
    async def test_fetch_and_cache_formats_already_cached(self) -> None:
        """Test fetch_and_cache_formats returns cached value when already set."""
        cached = {"test": GirudoGameFormat(uuid="cached-uuid", name="Cached")}
        girudo.GIRUDO_FORMATS_CACHE = cached
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        result = await girudo.fetch_and_cache_formats(client, GirudoTestData.AUTH_TOKEN)
        assert result == cached

    @pytest.mark.asyncio
    async def test_fetch_and_cache_formats_missing_id_or_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test formats with missing id or name are skipped."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)
        response = MockHTTPResponse(
            200,
            {
                "status": "success",
                "data": [
                    {"game_format_id": "id1", "game_format_name": None},
                    {"game_format_id": None, "game_format_name": "Name"},
                    {"game_format_id": "id2", "game_format_name": "Valid"},
                ],
            },
        )
        client = MockHTTPClient(response)
        result = await girudo.fetch_and_cache_formats(client, GirudoTestData.AUTH_TOKEN)
        assert len(result) == 1
        assert "valid" in result

    @pytest.mark.asyncio
    async def test_fetch_and_cache_formats_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test fetch_and_cache_formats handles exception gracefully."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        client.get = AsyncMock(side_effect=RuntimeError("Network error"))
        result = await girudo.fetch_and_cache_formats(client, GirudoTestData.AUTH_TOKEN)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_and_cache_formats_non_success_status(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)

        response = MockHTTPResponse(200, {"status": "error", "data": []})
        client = MockHTTPClient(response)

        result = await girudo.fetch_and_cache_formats(client, GirudoTestData.AUTH_TOKEN)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_and_cache_formats_empty_data(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)

        response = MockHTTPResponse(200, {"status": "success", "data": []})
        client = MockHTTPClient(response)

        result = await girudo.fetch_and_cache_formats(client, GirudoTestData.AUTH_TOKEN)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_and_cache_tcg_names_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_STORE_DATA_URL",
            f"{GirudoTestData.API_BASE_URL}/store",
        )

        response = MockHTTPResponse(200, GirudoTestData.tcg_names_response())
        client = MockHTTPClient(response)

        result = await girudo.fetch_and_cache_tcg_names(client, GirudoTestData.AUTH_TOKEN)
        assert result[GirudoTestData.TCG_MAGIC_UUID] == GirudoTestData.TCG_MAGIC_NAME
        assert result[GirudoTestData.TCG_POKEMON_UUID] == GirudoTestData.TCG_POKEMON_NAME

    @pytest.mark.asyncio
    async def test_fetch_and_cache_tcg_names_already_cached(self) -> None:
        """Test fetch_and_cache_tcg_names returns cached value when already set."""
        cached = {"cached-uuid": "Cached TCG"}
        girudo.TCG_NAMES_CACHE = cached
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        result = await girudo.fetch_and_cache_tcg_names(client, GirudoTestData.AUTH_TOKEN)
        assert result == cached

    @pytest.mark.asyncio
    async def test_fetch_and_cache_tcg_names_no_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fetch_and_cache_tcg_names when GIRUDO_STORE_DATA_URL not configured."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_STORE_DATA_URL", None)
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        result = await girudo.fetch_and_cache_tcg_names(client, GirudoTestData.AUTH_TOKEN)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_and_cache_tcg_names_non_success_status(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test fetch_and_cache_tcg_names when API returns non-success status."""
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_STORE_DATA_URL",
            f"{GirudoTestData.API_BASE_URL}/store",
        )
        response = MockHTTPResponse(200, {"status": "error", "data": {}})
        client = MockHTTPClient(response)
        result = await girudo.fetch_and_cache_tcg_names(client, GirudoTestData.AUTH_TOKEN)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_and_cache_tcg_names_missing_id_or_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test TCG games with missing id or name are skipped."""
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_STORE_DATA_URL",
            f"{GirudoTestData.API_BASE_URL}/store",
        )
        response = MockHTTPResponse(
            200,
            {
                "status": "success",
                "data": {
                    "store_games": [
                        {"id": "id1", "name": None},
                        {"id": None, "name": "Name"},
                        {"id": "id2", "name": "Valid"},
                    ],
                },
            },
        )
        client = MockHTTPClient(response)
        result = await girudo.fetch_and_cache_tcg_names(client, GirudoTestData.AUTH_TOKEN)
        assert len(result) == 1
        assert result["id2"] == "Valid"

    @pytest.mark.asyncio
    async def test_fetch_and_cache_tcg_names_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test fetch_and_cache_tcg_names handles exception gracefully."""
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_STORE_DATA_URL",
            f"{GirudoTestData.API_BASE_URL}/store",
        )
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        client.get = AsyncMock(side_effect=RuntimeError("Network error"))
        result = await girudo.fetch_and_cache_tcg_names(client, GirudoTestData.AUTH_TOKEN)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_and_cache_tcg_names_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_STORE_DATA_URL",
            f"{GirudoTestData.API_BASE_URL}/store",
        )

        response = MockHTTPResponse(200, {"status": "success", "data": {"store_games": []}})
        client = MockHTTPClient(response)

        result = await girudo.fetch_and_cache_tcg_names(client, GirudoTestData.AUTH_TOKEN)
        assert result == {}

    @pytest.mark.asyncio
    async def test_ensure_formats_loaded_no_accounts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo, "get_accounts", list)

        result = await girudo.ensure_formats_loaded()
        assert result == {}

    @pytest.mark.asyncio
    async def test_ensure_formats_loaded_cached(self) -> None:
        girudo.GIRUDO_FORMATS_CACHE = {"test": GirudoGameFormat(uuid="u1", name="Test")}

        result = await girudo.ensure_formats_loaded()
        assert "test" in result

    @pytest.mark.asyncio
    async def test_ensure_formats_loaded_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ensure_formats_loaded handles exception gracefully."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )

        async def mock_pick_account(accounts: Any) -> tuple[str, str]:
            raise RuntimeError("Simulated failure")

        monkeypatch.setattr(girudo, "pick_account", mock_pick_account)

        result = await girudo.ensure_formats_loaded()
        assert result == {}

    @pytest.mark.asyncio
    async def test_ensure_formats_loaded_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ensure_formats_loaded successfully fetches and returns formats."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        async def mock_auth(client: Any, **kwargs: Any) -> str:
            return GirudoTestData.AUTH_TOKEN

        expected_formats = {"test": GirudoGameFormat(uuid="test-uuid", name="Test")}

        async def mock_fetch_formats(client: Any, token: str) -> dict[str, GirudoGameFormat]:
            return expected_formats

        monkeypatch.setattr(girudo, "authenticate", mock_auth)
        monkeypatch.setattr(girudo, "fetch_and_cache_formats", mock_fetch_formats)

        result = await girudo.ensure_formats_loaded()
        assert result == expected_formats

    @pytest.mark.asyncio
    async def test_ensure_formats_loaded_auth_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test ensure_formats_loaded when authentication fails."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_AUTH_URL",
            f"{GirudoTestData.API_BASE_URL}/auth",
        )

        # Return None for auth failure
        async def mock_auth(client: Any, **kwargs: Any) -> None:
            return None

        monkeypatch.setattr(girudo, "authenticate", mock_auth)

        result = await girudo.ensure_formats_loaded()
        assert result == {}


class TestGirudoFormatMapping:
    """Test game format mapping."""

    def test_girudo_game_format_standard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        girudo.GIRUDO_FORMATS_CACHE = GirudoTestData.formats_cache()

        result = girudo.girudo_game_format(GameFormat.STANDARD)
        assert result.uuid == GirudoTestData.FORMAT_STANDARD_UUID

    def test_girudo_game_format_commander(self, monkeypatch: pytest.MonkeyPatch) -> None:
        girudo.GIRUDO_FORMATS_CACHE = GirudoTestData.formats_cache()

        result = girudo.girudo_game_format(GameFormat.COMMANDER)
        assert result.uuid == GirudoTestData.FORMAT_COMMANDER_UUID

    def test_girudo_game_format_brawl(self) -> None:
        """Test Brawl format mapping."""
        girudo.GIRUDO_FORMATS_CACHE = {"brawl": GirudoGameFormat(uuid="brawl-uuid", name="Brawl")}
        result = girudo.girudo_game_format(GameFormat.BRAWL_TWO_PLAYER)
        assert result.uuid == "brawl-uuid"

    def test_girudo_game_format_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_FORMAT_UUID",
            GirudoTestData.FORMAT_DEFAULT_UUID,
        )
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_FORMAT_NAME",
            GirudoTestData.FORMAT_DEFAULT_NAME,
        )

        girudo.GIRUDO_FORMATS_CACHE = {}

        result = girudo.girudo_game_format(GameFormat.MODERN)
        assert result.uuid == GirudoTestData.FORMAT_DEFAULT_UUID


class TestGirudoErrors:
    """Test error classes."""

    def test_girudo_auth_error(self) -> None:
        error = girudo.GirudoAuthError()
        assert str(error) == "Failed to authenticate to Girudo"

    def test_girudo_game_create_error(self) -> None:
        error = girudo.GirudoGameCreateError()
        assert str(error) == "Failed to create game on Girudo"


class TestGirudoGameCreation:
    """Test game creation."""

    @pytest.mark.asyncio
    async def test_create_game_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_CREATE_URL",
            f"{GirudoTestData.API_BASE_URL}/create",
        )
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_TCG_MAGIC_UUID",
            GirudoTestData.TCG_MAGIC_UUID,
        )

        girudo.TCG_NAMES_CACHE = GirudoTestData.tcg_cache()

        response = MockHTTPResponse(201, GirudoTestData.create_game_response())
        client = MockHTTPClient(response)

        game = cast("GameDict", create_mock_game())
        link = await girudo.create_game(client, GirudoTestData.AUTH_TOKEN, game)

        assert link is not None
        assert f"join-game/{GirudoTestData.GAME_UUID}" in link
        assert "type=player" in link

    @pytest.mark.asyncio
    async def test_create_game_no_uuid_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_CREATE_URL",
            f"{GirudoTestData.API_BASE_URL}/create",
        )
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_TCG_MAGIC_UUID",
            GirudoTestData.TCG_MAGIC_UUID,
        )

        response = MockHTTPResponse(201, {"data": {}})
        client = MockHTTPClient(response)

        game = cast("GameDict", create_mock_game())
        link = await girudo.create_game(client, GirudoTestData.AUTH_TOKEN, game)
        assert link is None

    @pytest.mark.asyncio
    async def test_create_game_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_CREATE_URL",
            f"{GirudoTestData.API_BASE_URL}/create",
        )
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_TCG_MAGIC_UUID",
            GirudoTestData.TCG_MAGIC_UUID,
        )

        response = MockHTTPResponse(400, {"message": "bad request"})
        client = MockHTTPClient(response)

        game = cast("GameDict", create_mock_game())
        link = await girudo.create_game(client, GirudoTestData.AUTH_TOKEN, game)
        assert link is None

    @pytest.mark.asyncio
    async def test_create_game_with_custom_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test create_game with custom format_uuid and format_name."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_CREATE_URL",
            f"{GirudoTestData.API_BASE_URL}/create",
        )
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_DEFAULT_TCG_MAGIC_UUID",
            GirudoTestData.TCG_MAGIC_UUID,
        )
        girudo.TCG_NAMES_CACHE = GirudoTestData.tcg_cache()

        response = MockHTTPResponse(201, GirudoTestData.create_game_response())
        client = MockHTTPClient(response)

        game = cast("GameDict", create_mock_game())
        link = await girudo.create_game(
            client,
            GirudoTestData.AUTH_TOKEN,
            game,
            format_uuid="custom-uuid",
            format_name="Custom Format",
        )
        assert link is not None

    @pytest.mark.asyncio
    async def test_create_game_no_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test create_game when GIRUDO_CREATE_URL not configured."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_CREATE_URL", None)
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        game = cast("GameDict", create_mock_game())
        link = await girudo.create_game(client, GirudoTestData.AUTH_TOKEN, game)
        assert link is None

    @pytest.mark.asyncio
    async def test_create_game_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test create_game handles exception gracefully."""
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_CREATE_URL",
            f"{GirudoTestData.API_BASE_URL}/create",
        )
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        client.post = AsyncMock(side_effect=RuntimeError("Network error"))
        game = cast("GameDict", create_mock_game())
        link = await girudo.create_game(client, GirudoTestData.AUTH_TOKEN, game)
        assert link is None


class TestGirudoLobbies:
    """Test lobby fetching."""

    @pytest.mark.asyncio
    async def test_fetch_lobbies_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_LOBBY_URL",
            f"{GirudoTestData.API_BASE_URL}/lobbies",
        )

        response = MockHTTPResponse(200, GirudoTestData.lobbies_response())
        client = MockHTTPClient(response)

        lobbies = await girudo.fetch_lobbies(client, GirudoTestData.AUTH_TOKEN)
        assert GirudoTestData.LOBBY_UUID_AVAILABLE in lobbies
        assert GirudoTestData.LOBBY_UUID_FULL in lobbies
        assert lobbies[GirudoTestData.LOBBY_UUID_AVAILABLE]["current_player_count"] == 2
        assert lobbies[GirudoTestData.LOBBY_UUID_AVAILABLE]["max_players"] == 4

    @pytest.mark.asyncio
    async def test_fetch_lobbies_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_LOBBY_URL",
            f"{GirudoTestData.API_BASE_URL}/lobbies",
        )

        response = MockHTTPResponse(500, {})
        client = MockHTTPClient(response)

        lobbies = await girudo.fetch_lobbies(client, GirudoTestData.AUTH_TOKEN)
        assert lobbies == {}

    @pytest.mark.asyncio
    async def test_get_available_lobby_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_LOBBY_URL",
            f"{GirudoTestData.API_BASE_URL}/lobbies",
        )

        response = MockHTTPResponse(200, GirudoTestData.lobbies_response())
        client = MockHTTPClient(response)

        link = await girudo.get_available_lobby(client, GirudoTestData.AUTH_TOKEN)
        assert link is not None
        assert f"join-game/{GirudoTestData.LOBBY_UUID_AVAILABLE}" in link

    @pytest.mark.asyncio
    async def test_get_available_lobby_none_available(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_LOBBY_URL",
            f"{GirudoTestData.API_BASE_URL}/lobbies",
        )

        response = MockHTTPResponse(
            200,
            {
                "data": {
                    GirudoTestData.LOBBY_UUID_FULL: {"current_player_count": 4, "max_players": 4},
                },
            },
        )
        client = MockHTTPClient(response)

        link = await girudo.get_available_lobby(client, GirudoTestData.AUTH_TOKEN)
        assert link is None

    @pytest.mark.asyncio
    async def test_fetch_lobbies_no_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fetch_lobbies when GIRUDO_LOBBY_URL not configured."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_LOBBY_URL", None)
        client = MockHTTPClient(MockHTTPResponse(200, {}))
        lobbies = await girudo.fetch_lobbies(client, GirudoTestData.AUTH_TOKEN)
        assert lobbies == {}

    @pytest.mark.asyncio
    async def test_get_available_lobby_invalid_player_counts(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_available_lobby skips lobbies with invalid player counts."""
        monkeypatch.setattr(girudo.settings, "GIRUDO_BASE_URL", GirudoTestData.API_BASE_URL)
        monkeypatch.setattr(
            girudo.settings,
            "GIRUDO_LOBBY_URL",
            f"{GirudoTestData.API_BASE_URL}/lobbies",
        )
        response = MockHTTPResponse(
            200,
            {
                "data": {
                    "lobby1": {"current_player_count": "invalid", "max_players": 4},
                    "lobby2": {"current_player_count": 2, "max_players": "invalid"},
                },
            },
        )
        client = MockHTTPClient(response)
        link = await girudo.get_available_lobby(client, GirudoTestData.AUTH_TOKEN)
        assert link is None


class TestGirudoGenerateLink:
    """Test the main generate_link function."""

    @pytest.mark.asyncio
    async def test_generate_link_no_accounts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(girudo, "get_accounts", list)

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is None
        assert result.password is None

    @pytest.mark.asyncio
    async def test_generate_link_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_RETRY_ATTEMPTS", 1)
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        # Mock authenticate to return a token
        async def mock_auth(client: Any, **kwargs: Any) -> str:
            return GirudoTestData.AUTH_TOKEN

        # Mock create_game to return a link
        async def mock_create(client: Any, token: str, game: Any, **kwargs: Any) -> str:
            return (
                f"{GirudoTestData.GAME_BASE_URL}/join-game/{GirudoTestData.GAME_UUID}?type=player"
            )

        monkeypatch.setattr(girudo, "authenticate", mock_auth)
        monkeypatch.setattr(girudo, "create_game", mock_create)

        mock_func_cahce_formats = AsyncMock(return_value={})
        mock_func_cahce_tcg_names = AsyncMock(return_value={})

        monkeypatch.setattr(girudo, "fetch_and_cache_formats", mock_func_cahce_formats)
        monkeypatch.setattr(girudo, "fetch_and_cache_tcg_names", mock_func_cahce_tcg_names)

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is not None
        assert f"join-game/{GirudoTestData.GAME_UUID}" in result.link

    @pytest.mark.asyncio
    async def test_generate_link_auth_failure_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_RETRY_ATTEMPTS", 2)
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        call_count = 0

        # Mock authenticate to fail first, succeed second
        async def mock_auth(client: Any, **kwargs: Any) -> str | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None
            return GirudoTestData.AUTH_TOKEN

        async def mock_create(client: Any, token: str, game: Any, **kwargs: Any) -> str:
            return (
                f"{GirudoTestData.GAME_BASE_URL}/join-game/{GirudoTestData.GAME_UUID}?type=player"
            )

        monkeypatch.setattr(girudo, "authenticate", mock_auth)
        monkeypatch.setattr(girudo, "create_game", mock_create)
        monkeypatch.setattr(girudo, "fetch_and_cache_formats", lambda c, t: {})
        monkeypatch.setattr(girudo, "fetch_and_cache_tcg_names", lambda c, t: {})

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is not None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_generate_link_exception_then_recovery(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test generate_link handles exception on first attempt but succeeds on retry."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_RETRY_ATTEMPTS", 2)
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        attempt_count = 0

        async def mock_auth(client: Any, **kwargs: Any) -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise RuntimeError("Simulated failure")
            return GirudoTestData.AUTH_TOKEN

        async def mock_create(client: Any, token: str, game: Any, **kwargs: Any) -> str:
            return (
                f"{GirudoTestData.GAME_BASE_URL}/join-game/{GirudoTestData.GAME_UUID}?type=player"
            )

        monkeypatch.setattr(girudo, "authenticate", mock_auth)
        monkeypatch.setattr(girudo, "create_game", mock_create)
        monkeypatch.setattr(girudo, "fetch_and_cache_formats", AsyncMock(return_value={}))
        monkeypatch.setattr(girudo, "fetch_and_cache_tcg_names", AsyncMock(return_value={}))

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is not None
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_generate_link_final_attempt_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test generate_link logs final attempt exception and returns empty."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_RETRY_ATTEMPTS", 1)
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        async def mock_auth(client: Any, **kwargs: Any) -> str:
            raise RuntimeError("Final failure")

        monkeypatch.setattr(girudo, "authenticate", mock_auth)

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is None
        assert result.password is None

    @pytest.mark.asyncio
    async def test_generate_link_create_game_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test generate_link when create_game returns None (all retries exhausted)."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_RETRY_ATTEMPTS", 2)
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        async def mock_auth(client: Any, **kwargs: Any) -> str:
            return GirudoTestData.AUTH_TOKEN

        async def mock_create(client: Any, token: str, game: Any, **kwargs: Any) -> None:
            return None

        monkeypatch.setattr(girudo, "authenticate", mock_auth)
        monkeypatch.setattr(girudo, "create_game", mock_create)
        monkeypatch.setattr(girudo, "fetch_and_cache_formats", AsyncMock(return_value={}))
        monkeypatch.setattr(girudo, "fetch_and_cache_tcg_names", AsyncMock(return_value={}))

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is None

    @pytest.mark.asyncio
    async def test_generate_link_caches_on_first_attempt(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test generate_link fetches and caches formats/tcg on first attempt only."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_RETRY_ATTEMPTS", 2)
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        auth_count = 0

        async def mock_auth(client: Any, **kwargs: Any) -> str:
            nonlocal auth_count
            auth_count += 1
            return GirudoTestData.AUTH_TOKEN

        create_count = 0

        async def mock_create(client: Any, token: str, game: Any, **kwargs: Any) -> str | None:
            nonlocal create_count
            create_count += 1
            if create_count == 1:
                return None  # First attempt fails
            return (
                f"{GirudoTestData.GAME_BASE_URL}/join-game/{GirudoTestData.GAME_UUID}?type=player"
            )

        format_calls = 0
        tcg_calls = 0

        async def mock_formats(client: Any, token: str) -> dict[str, Any]:
            nonlocal format_calls
            format_calls += 1
            return {}

        async def mock_tcg(client: Any, token: str) -> dict[str, Any]:
            nonlocal tcg_calls
            tcg_calls += 1
            return {}

        monkeypatch.setattr(girudo, "authenticate", mock_auth)
        monkeypatch.setattr(girudo, "create_game", mock_create)
        monkeypatch.setattr(girudo, "fetch_and_cache_formats", mock_formats)
        monkeypatch.setattr(girudo, "fetch_and_cache_tcg_names", mock_tcg)

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is not None
        # Caching only happens on first attempt (attempt == 0)
        assert format_calls == 1
        assert tcg_calls == 1

    @pytest.mark.asyncio
    async def test_generate_link_skips_cache_when_populated(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test generate_link skips fetching when caches are already populated."""
        monkeypatch.setattr(
            girudo,
            "get_accounts",
            lambda: [(GirudoTestData.AUTH_EMAIL, GirudoTestData.AUTH_PASSWORD)],
        )
        monkeypatch.setattr(girudo.settings, "GIRUDO_RETRY_ATTEMPTS", 1)
        monkeypatch.setattr(girudo.settings, "GIRUDO_TIMEOUT_S", 5)

        # Pre-populate the caches
        monkeypatch.setattr(
            girudo,
            "GIRUDO_FORMATS_CACHE",
            {"commander_edh": girudo.GirudoGameFormat(uuid="test-uuid", name="Commander")},
        )
        monkeypatch.setattr(girudo, "TCG_NAMES_CACHE", {"mtg": "Magic: The Gathering"})

        async def mock_auth(client: Any, **kwargs: Any) -> str:
            return GirudoTestData.AUTH_TOKEN

        async def mock_create(client: Any, token: str, game: Any, **kwargs: Any) -> str | None:
            return (
                f"{GirudoTestData.GAME_BASE_URL}/join-game/{GirudoTestData.GAME_UUID}?type=player"
            )

        format_calls = 0
        tcg_calls = 0

        async def mock_formats(client: Any, token: str) -> dict[str, Any]:  # pragma: no cover
            nonlocal format_calls
            format_calls += 1
            return {}

        async def mock_tcg(client: Any, token: str) -> dict[str, Any]:  # pragma: no cover
            nonlocal tcg_calls
            tcg_calls += 1
            return {}

        monkeypatch.setattr(girudo, "authenticate", mock_auth)
        monkeypatch.setattr(girudo, "create_game", mock_create)
        monkeypatch.setattr(girudo, "fetch_and_cache_formats", mock_formats)
        monkeypatch.setattr(girudo, "fetch_and_cache_tcg_names", mock_tcg)

        game = cast("GameDict", create_mock_game())
        result = await girudo.generate_link(game)

        assert result.link is not None
        # Caches were already populated, so no fetch calls
        assert format_calls == 0
        assert tcg_calls == 0
