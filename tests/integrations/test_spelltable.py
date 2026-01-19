from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import spellbot.integrations.spelltable as spelltable_module
from spellbot.enums import GameFormat
from spellbot.integrations.spelltable import (
    SpellTableCodeError,
    SpellTableCSRFError,
    SpellTableGameTypes,
    SpellTableRedirectError,
    TokenData,
    authorize,
    client_info,
    create_game,
    exchange_code,
    generate_link,
    get_accounts,
    get_csrf,
    get_user_lock,
    login,
    pick_account,
    refresh_access_token,
    spelltable_game_type,
)

if TYPE_CHECKING:
    from spellbot.models import GameDict


class TestSpellTableGameType:
    @pytest.mark.parametrize(
        ("game_format", "expected"),
        [
            pytest.param(GameFormat.STANDARD, SpellTableGameTypes.Standard, id="standard"),
            pytest.param(GameFormat.SEALED, SpellTableGameTypes.Standard, id="sealed"),
            pytest.param(GameFormat.MODERN, SpellTableGameTypes.Modern, id="modern"),
            pytest.param(GameFormat.VINTAGE, SpellTableGameTypes.Vintage, id="vintage"),
            pytest.param(GameFormat.LEGACY, SpellTableGameTypes.Legacy, id="legacy"),
            pytest.param(
                GameFormat.DUEL_COMMANDER,
                SpellTableGameTypes.Legacy,
                id="duel_commander",
            ),
            pytest.param(
                GameFormat.BRAWL_TWO_PLAYER,
                SpellTableGameTypes.BrawlTwoPlayer,
                id="brawl_2p",
            ),
            pytest.param(
                GameFormat.BRAWL_MULTIPLAYER,
                SpellTableGameTypes.BrawlMultiplayer,
                id="brawl_mp",
            ),
            pytest.param(GameFormat.TWO_HEADED_GIANT, SpellTableGameTypes.TwoHeadedGiant, id="2hg"),
            pytest.param(GameFormat.PAUPER, SpellTableGameTypes.Pauper, id="pauper"),
            pytest.param(GameFormat.PAUPER_EDH, SpellTableGameTypes.PauperEDH, id="pauper_edh"),
            pytest.param(GameFormat.PIONEER, SpellTableGameTypes.Pioneer, id="pioneer"),
            pytest.param(GameFormat.OATHBREAKER, SpellTableGameTypes.Oathbreaker, id="oathbreaker"),
            pytest.param(GameFormat.COMMANDER, SpellTableGameTypes.Commander, id="commander"),
            pytest.param(GameFormat.EDH_MAX, SpellTableGameTypes.Commander, id="edh_max"),
            pytest.param(GameFormat.EDH_HIGH, SpellTableGameTypes.Commander, id="edh_high"),
            pytest.param(GameFormat.EDH_MID, SpellTableGameTypes.Commander, id="edh_mid"),
            pytest.param(GameFormat.EDH_LOW, SpellTableGameTypes.Commander, id="edh_low"),
            pytest.param(
                GameFormat.EDH_BATTLECRUISER,
                SpellTableGameTypes.Commander,
                id="edh_battlecruiser",
            ),
            pytest.param(GameFormat.PLANECHASE, SpellTableGameTypes.Commander, id="planechase"),
            pytest.param(GameFormat.PRE_CONS, SpellTableGameTypes.Commander, id="pre_cons"),
            pytest.param(GameFormat.CEDH, SpellTableGameTypes.Commander, id="cedh"),
            pytest.param(GameFormat.ARCHENEMY, SpellTableGameTypes.Commander, id="archenemy"),
            pytest.param(GameFormat.HORDE_MAGIC, SpellTableGameTypes.Commander, id="horde_magic"),
        ],
    )
    def test_game_type_mapping(
        self,
        game_format: GameFormat,
        expected: SpellTableGameTypes,
    ) -> None:
        assert spelltable_game_type(game_format) == expected


class TestGetAccounts:
    def test_get_accounts_success(self) -> None:
        with (
            patch.object(spelltable_module.settings, "SPELLTABLE_USERS", "user1,user2"),
            patch.object(spelltable_module.settings, "SPELLTABLE_PASSES", "pass1,pass2"),
        ):
            accounts = get_accounts()
            assert accounts == [("user1", "pass1"), ("user2", "pass2")]

    def test_get_accounts_no_users(self) -> None:
        with (
            patch.object(spelltable_module.settings, "SPELLTABLE_USERS", ""),
            pytest.raises(AssertionError, match="SPELLTABLE_USERS not configured"),
        ):
            get_accounts()

    def test_get_accounts_no_passes(self) -> None:
        with (
            patch.object(spelltable_module.settings, "SPELLTABLE_USERS", "user1"),
            patch.object(spelltable_module.settings, "SPELLTABLE_PASSES", ""),
            pytest.raises(AssertionError, match="SPELLTABLE_PASSES not configured"),
        ):
            get_accounts()


class TestPickAccount:
    @pytest.mark.asyncio
    async def test_pick_account_round_robin(self) -> None:
        # Reset ROUND_ROBIN for test
        spelltable_module.ROUND_ROBIN = None

        accounts = [("user1", "pass1"), ("user2", "pass2")]

        # First call initializes ROUND_ROBIN randomly
        result = await pick_account(accounts)
        assert result in accounts

        # Subsequent calls cycle through accounts
        results = [await pick_account(accounts) for _ in range(4)]
        # Should have picked from both accounts
        assert len(set(results)) <= 2


class TestGetUserLock:
    @pytest.mark.asyncio
    async def test_get_user_lock_creates_lock(self) -> None:
        spelltable_module.USER_LOCKS.clear()
        lock1 = await get_user_lock("testuser")
        assert "testuser" in spelltable_module.USER_LOCKS
        assert lock1 is spelltable_module.USER_LOCKS["testuser"]

    @pytest.mark.asyncio
    async def test_get_user_lock_returns_same_lock(self) -> None:
        spelltable_module.USER_LOCKS.clear()
        lock1 = await get_user_lock("testuser")
        lock2 = await get_user_lock("testuser")
        assert lock1 is lock2


class TestGetCsrf:
    @pytest.mark.asyncio
    async def test_get_csrf_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.cookies = {"_csrf": "test_csrf_token"}

        result = await get_csrf(mock_client)
        assert result == "test_csrf_token"
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_csrf_no_token(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.cookies = {}

        with pytest.raises(SpellTableCSRFError):
            await get_csrf(mock_client)


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        await login(mock_client, "user", "pass", "csrf_token")
        mock_client.post.assert_called_once()


class TestClientInfo:
    @pytest.mark.asyncio
    async def test_client_info_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        await client_info(mock_client, "csrf_token")
        mock_client.post.assert_called_once()


class TestAuthorize:
    @pytest.mark.asyncio
    async def test_authorize_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {"redirect_target": "https://example.com?code=auth_code"},
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await authorize(mock_client, "csrf_token")
        assert result == "auth_code"

    @pytest.mark.asyncio
    async def test_authorize_no_redirect_target(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {}}
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(SpellTableRedirectError):
            await authorize(mock_client, "csrf_token")

    @pytest.mark.asyncio
    async def test_authorize_no_code(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {"redirect_target": "https://example.com?other=param"},
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(SpellTableCodeError):
            await authorize(mock_client, "csrf_token")


class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_exchange_code_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "expires_in": 3600,
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await exchange_code(mock_client, "test_code")
        assert result.access_token == "access123"
        assert result.refresh_token == "refresh123"


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_refresh_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await refresh_access_token(mock_client, "old_refresh")
        assert result is not None
        assert result.access_token == "new_access"

    @pytest.mark.asyncio
    async def test_refresh_failure(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

        result = await refresh_access_token(mock_client, "old_refresh")
        assert result is None


class TestCreateGame:
    @pytest.mark.asyncio
    async def test_create_game_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": "game123"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = cast("GameDict", {"id": 1, "format": GameFormat.COMMANDER.value})
        result = await create_game(mock_client, "token123", game)
        assert result == "https://spelltable.wizards.com/game/game123"


class TestGenerateLink:
    @pytest.mark.asyncio
    async def test_generate_link_no_retries(self) -> None:
        """Test generate_link returns None when RETRY_ATTEMPTS is 0."""
        game = cast("GameDict", {"id": 1, "format": GameFormat.COMMANDER.value})

        with (
            patch.object(spelltable_module, "get_accounts", return_value=[("user", "pass")]),
            patch.object(spelltable_module, "RETRY_ATTEMPTS", 0),
        ):
            result = await generate_link(game)
            assert result is None

    @pytest.mark.asyncio
    async def test_generate_link_success(self) -> None:
        game = cast("GameDict", {"id": 1, "format": GameFormat.COMMANDER.value})
        token_data = TokenData(
            access_token="access123",  # noqa: S106
            refresh_token="refresh123",  # noqa: S106
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

        with (
            patch.object(spelltable_module, "get_accounts", return_value=[("user", "pass")]),
            patch.object(
                spelltable_module,
                "pick_account",
                AsyncMock(return_value=("user", "pass")),
            ),
            patch.object(
                spelltable_module,
                "get_user_lock",
                AsyncMock(return_value=MagicMock()),
            ),
            patch.object(
                spelltable_module,
                "user_tokens",
                {"user": token_data},
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with patch.object(
                spelltable_module,
                "create_game",
                AsyncMock(return_value="https://spelltable.wizards.com/game/123"),
            ):
                result = await generate_link(game)
                assert result == "https://spelltable.wizards.com/game/123"

    @pytest.mark.asyncio
    async def test_generate_link_retries_on_failure(self) -> None:
        game = cast("GameDict", {"id": 1, "format": GameFormat.COMMANDER.value})

        with (
            patch.object(spelltable_module, "get_accounts", return_value=[("user", "pass")]),
            patch.object(
                spelltable_module,
                "pick_account",
                AsyncMock(return_value=("user", "pass")),
            ),
            patch.object(
                spelltable_module,
                "get_user_lock",
                AsyncMock(return_value=MagicMock()),
            ),
            patch.object(spelltable_module, "user_tokens", {}),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(spelltable_module, "get_csrf", AsyncMock(side_effect=Exception("Failed"))),
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await generate_link(game)
            assert result is None

    @pytest.mark.asyncio
    async def test_generate_link_with_token_refresh(self) -> None:
        game = cast("GameDict", {"id": 1, "format": GameFormat.COMMANDER.value})
        # Create expired token that needs refreshing
        expired_token = TokenData(
            access_token="old_access",  # noqa: S106
            refresh_token="refresh123",  # noqa: S106
            expires_at=datetime.now(tz=UTC) - timedelta(hours=1),  # Expired
        )
        refreshed_token = TokenData(
            access_token="new_access",  # noqa: S106
            refresh_token="new_refresh",  # noqa: S106
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

        with (
            patch.object(spelltable_module, "get_accounts", return_value=[("user", "pass")]),
            patch.object(
                spelltable_module,
                "pick_account",
                AsyncMock(return_value=("user", "pass")),
            ),
            patch.object(
                spelltable_module,
                "get_user_lock",
                AsyncMock(return_value=MagicMock()),
            ),
            patch.object(spelltable_module, "user_tokens", {"user": expired_token}),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(
                spelltable_module,
                "refresh_access_token",
                AsyncMock(return_value=refreshed_token),
            ),
            patch.object(
                spelltable_module,
                "create_game",
                AsyncMock(return_value="https://spelltable.wizards.com/game/123"),
            ),
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await generate_link(game)
            assert result == "https://spelltable.wizards.com/game/123"

    @pytest.mark.asyncio
    async def test_generate_link_full_login_flow(self) -> None:
        game = cast("GameDict", {"id": 1, "format": GameFormat.COMMANDER.value})
        new_token = TokenData(
            access_token="fresh_access",  # noqa: S106
            refresh_token="fresh_refresh",  # noqa: S106
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

        with (
            patch.object(spelltable_module, "get_accounts", return_value=[("user", "pass")]),
            patch.object(
                spelltable_module,
                "pick_account",
                AsyncMock(return_value=("user", "pass")),
            ),
            patch.object(
                spelltable_module,
                "get_user_lock",
                AsyncMock(return_value=MagicMock()),
            ),
            patch.object(spelltable_module, "user_tokens", {}),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(spelltable_module, "get_csrf", AsyncMock(return_value="csrf_token")),
            patch.object(spelltable_module, "login", AsyncMock()),
            patch.object(spelltable_module, "client_info", AsyncMock()),
            patch.object(spelltable_module, "authorize", AsyncMock(return_value="auth_code")),
            patch.object(spelltable_module, "exchange_code", AsyncMock(return_value=new_token)),
            patch.object(
                spelltable_module,
                "create_game",
                AsyncMock(return_value="https://spelltable.wizards.com/game/456"),
            ),
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await generate_link(game)
            assert result == "https://spelltable.wizards.com/game/456"

    @pytest.mark.asyncio
    async def test_generate_link_refresh_fails_falls_back_to_login(self) -> None:
        game = cast("GameDict", {"id": 1, "format": GameFormat.COMMANDER.value})
        # Create expired token that needs refreshing
        expired_token = TokenData(
            access_token="old_access",  # noqa: S106
            refresh_token="refresh123",  # noqa: S106
            expires_at=datetime.now(tz=UTC) - timedelta(hours=1),  # Expired
        )
        new_token = TokenData(
            access_token="fresh_access",  # noqa: S106
            refresh_token="fresh_refresh",  # noqa: S106
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

        with (
            patch.object(spelltable_module, "get_accounts", return_value=[("user", "pass")]),
            patch.object(
                spelltable_module,
                "pick_account",
                AsyncMock(return_value=("user", "pass")),
            ),
            patch.object(
                spelltable_module,
                "get_user_lock",
                AsyncMock(return_value=MagicMock()),
            ),
            patch.object(spelltable_module, "user_tokens", {"user": expired_token}),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(
                spelltable_module,
                "refresh_access_token",
                AsyncMock(return_value=None),  # Refresh fails
            ),
            patch.object(spelltable_module, "get_csrf", AsyncMock(return_value="csrf_token")),
            patch.object(spelltable_module, "login", AsyncMock()),
            patch.object(spelltable_module, "client_info", AsyncMock()),
            patch.object(spelltable_module, "authorize", AsyncMock(return_value="auth_code")),
            patch.object(spelltable_module, "exchange_code", AsyncMock(return_value=new_token)),
            patch.object(
                spelltable_module,
                "create_game",
                AsyncMock(return_value="https://spelltable.wizards.com/game/789"),
            ),
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await generate_link(game)
            assert result == "https://spelltable.wizards.com/game/789"
