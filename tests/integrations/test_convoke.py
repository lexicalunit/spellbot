# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import spellbot.integrations.convoke as convoke_module
from spellbot.enums import GameBracket, GameFormat
from spellbot.integrations.convoke import (
    ConvokeGameTypes,
    convoke_game_format,
    fetch_convoke_link,
    generate_link,
)
from tests.mocks import create_mock_game

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


class TestConvokeGameFormat:
    @pytest.mark.parametrize(
        ("game_format", "expected"),
        [
            pytest.param(GameFormat.COMMANDER, ConvokeGameTypes.Commander, id="commander"),
            pytest.param(GameFormat.EDH_MAX, ConvokeGameTypes.Commander, id="edh_max"),
            pytest.param(GameFormat.EDH_HIGH, ConvokeGameTypes.Commander, id="edh_high"),
            pytest.param(GameFormat.EDH_MID, ConvokeGameTypes.Commander, id="edh_mid"),
            pytest.param(GameFormat.EDH_LOW, ConvokeGameTypes.Commander, id="edh_low"),
            pytest.param(
                GameFormat.EDH_BATTLECRUISER,
                ConvokeGameTypes.Commander,
                id="edh_battlecruiser",
            ),
            pytest.param(GameFormat.PRE_CONS, ConvokeGameTypes.Commander, id="pre_cons"),
            pytest.param(GameFormat.CEDH, ConvokeGameTypes.Commander, id="cedh"),
            pytest.param(GameFormat.PAUPER_EDH, ConvokeGameTypes.Commander, id="pauper_edh"),
            pytest.param(GameFormat.MODERN, ConvokeGameTypes.Modern, id="modern"),
            pytest.param(GameFormat.STANDARD, ConvokeGameTypes.Standard, id="standard"),
            pytest.param(GameFormat.HORDE_MAGIC, ConvokeGameTypes.Horde, id="horde_magic"),
            pytest.param(GameFormat.PLANECHASE, ConvokeGameTypes.Planechase, id="planechase"),
            pytest.param(GameFormat.LEGACY, ConvokeGameTypes.Other, id="legacy"),
            pytest.param(GameFormat.VINTAGE, ConvokeGameTypes.Other, id="vintage"),
            pytest.param(GameFormat.PIONEER, ConvokeGameTypes.Other, id="pioneer"),
        ],
    )
    def test_game_format_mapping(
        self,
        game_format: GameFormat,
        expected: ConvokeGameTypes,
    ) -> None:
        assert convoke_game_format(game_format) == expected


class TestFetchConvokeLink:
    @pytest.mark.asyncio
    async def test_fetch_convoke_link_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/123"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        players = [
            {"xid": 100, "name": "Player1", "pin": "123456"},
            {"xid": 200, "name": "Player2", "pin": "654321"},
        ]

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=players),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, pins=["123456"])

        assert result == {"url": "https://convoke.gg/game/123"}
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["spellbotGameId"] == "42"
        assert payload["spellbotGamePins"] == ["123456"]
        assert payload["discordPlayers"] == [
            {"id": "100", "name": "Player1"},
            {"id": "200", "name": "Player2"},
        ]

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_bracket(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/456"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=99,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.BRACKET_2.value,
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/456"}
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["bracketLevel"] == "B2"  # BRACKET_2.value (3) -> B{3-1} = B2

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_guild_war(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/war"}
        mock_client.post = AsyncMock(return_value=mock_response)

        war_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        game = create_mock_game(
            game_id=7,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
            war_id=war_id,
            war_title="Summer Clash",
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/war"}
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["warId"] == war_id
        assert "warPodMode" not in payload

    @pytest.mark.asyncio
    @pytest.mark.parametrize("competitive_mode", [True, False], ids=["enabled", "disabled"])
    async def test_fetch_convoke_link_with_competitive_mode(
        self,
        competitive_mode: bool,
    ) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/789"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=11,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
            competitive_mode=competitive_mode,
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            await fetch_convoke_link(mock_client, game, pins=None)

        payload = mock_client.post.call_args.kwargs["json"]
        if competitive_mode:
            assert payload["competitiveMode"] is True
        else:
            # Omitted rather than sent as False so Convoke's B5 default still applies.
            assert "competitiveMode" not in payload

    @pytest.mark.asyncio
    async def test_fetch_live_guild_wars(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "wars": [
                {
                    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "title": "Summer Clash",
                    "slug": "summer-clash",
                    "status": "active",
                    "participants": [{"communityId": 1}, {"communityId": 2}],
                },
            ],
        }
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"):
            wars = await convoke_module.fetch_live_guild_wars(mock_client)

        assert wars == [
            {
                "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "title": "Summer Clash",
                "slug": "summer-clash",
                "status": "active",
            },
        ]
        assert mock_client.get.call_args.args[0] == "https://api.convoke.gg/guild-wars/live"

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_precons(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/456"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=99,
            game_format=GameFormat.PRE_CONS.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/456"}
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["bracketLevel"] == "PRECON"

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_password(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/789"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=101,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/789"}

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_supported_locale(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/123"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
            locale="ja",
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/123"}
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["language"] == "ja"

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_unsupported_locale(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/123"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
            locale="ko",  # Korean - not in SUPPORTED_LOCALES
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_convoke_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/123"}
        payload = mock_client.post.call_args.kwargs["json"]
        # Falls back to "en" for unsupported locales
        assert payload["language"] == "en"


class TestGenerateLink:
    @pytest.mark.asyncio
    async def test_generate_link_no_api_key(self) -> None:
        game = create_mock_game(game_id=1, game_format=GameFormat.COMMANDER.value)

        with patch.object(convoke_module.settings, "CONVOKE_API_KEY", ""):
            result = await generate_link(game, pins=None)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_success(self) -> None:
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(
                convoke_module,
                "fetch_convoke_link",
                AsyncMock(return_value={"url": "https://convoke.gg/game/123"}),
            ),
        ):
            result = await generate_link(game, pins=None)

        assert result == ("https://convoke.gg/game/123", None)

    @pytest.mark.asyncio
    async def test_generate_link_success_with_password_from_response(self) -> None:
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(
                convoke_module,
                "fetch_convoke_link",
                AsyncMock(
                    return_value={"url": "https://convoke.gg/game/123", "password": "resp_pass"},
                ),
            ),
        ):
            result = await generate_link(game, pins=None)

        assert result == ("https://convoke.gg/game/123", "resp_pass")

    @pytest.mark.asyncio
    async def test_generate_link_retries_on_failure_then_succeeds(self) -> None:
        """Test that generate_link retries after failure and succeeds on second attempt."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        # Create a mock that fails then succeeds (to test the retry path)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/789"}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        # First call fails, second call succeeds
        mock_client.post = AsyncMock(
            side_effect=[Exception("Connection error"), mock_response],
        )

        mock_player_data = AsyncMock(return_value=[])

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(convoke_module, "add_span_error"),
            patch.object(convoke_module.services.games, "player_convoke_data", mock_player_data),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game, pins=None)

        # First attempt fails, second succeeds
        assert result == ("https://convoke.gg/game/789", None)
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_link_fails_after_all_retries(self) -> None:
        """Test that generate_link returns None after exhausting all retry attempts."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        mock_client = MagicMock(spec=httpx.AsyncClient)
        # All calls fail
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

        mock_player_data = AsyncMock(return_value=[])

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(convoke_module, "add_span_error"),
            patch.object(convoke_module.services.games, "player_convoke_data", mock_player_data),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game, pins=None)

        # All attempts fail, returns None
        assert result == (None, None)
        # Verify that the post method was called RETRY_ATTEMPTS times (2)
        assert mock_client.post.call_count == convoke_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_generate_link_returns_none_when_data_is_empty(self) -> None:
        """Test that generate_link returns None when fetch_convoke_link returns empty dict."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        # Mock the response to return an empty dict (falsy)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        mock_player_data = AsyncMock(return_value=[])

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(convoke_module.services.games, "player_convoke_data", mock_player_data),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game, pins=None)

        # Empty dict is falsy, so returns None
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_zero_retry_attempts(self) -> None:
        """Test that generate_link returns None when RETRY_ATTEMPTS is 0 (loop never executes)."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(convoke_module, "RETRY_ATTEMPTS", 0),
        ):
            result = await generate_link(game, pins=None)

        assert result == (None, None)


def war_response(payload: object) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    return resp


def war_client(payload: object) -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=war_response(payload))
    return client


WAR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.mark.asyncio
class TestFetchLiveGuildWars:
    """Covers how a Convoke Guild War payload is parsed, including malformed shapes."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param([], id="not_an_object"),
            pytest.param({}, id="no_wars_key"),
            pytest.param({"wars": None}, id="wars_is_null"),
            pytest.param({"wars": "nope"}, id="wars_is_a_string"),
        ],
    )
    async def test_a_payload_we_do_not_recognize_yields_nothing(self, payload: object) -> None:
        # Autocomplete must degrade to an empty list rather than raising inside
        # Discord's UI if Convoke ever changes this response shape.
        assert await convoke_module.fetch_live_guild_wars(war_client(payload)) == []

    async def test_rows_that_are_not_objects_are_skipped(self) -> None:
        payload = {"wars": ["nope", 42, {"id": WAR_ID, "title": "Summer Clash"}]}
        wars = await convoke_module.fetch_live_guild_wars(war_client(payload))
        assert [war["id"] for war in wars] == [WAR_ID]

    @pytest.mark.parametrize(
        "row",
        [
            pytest.param({"title": "Summer Clash"}, id="missing_id"),
            pytest.param({"id": WAR_ID}, id="missing_title"),
            pytest.param({"id": 42, "title": "Summer Clash"}, id="non_string_id"),
            pytest.param({"id": WAR_ID, "title": 42}, id="non_string_title"),
        ],
    )
    async def test_rows_without_a_usable_id_and_title_are_skipped(self, row: object) -> None:
        # Both are required: the id is what gets stored on the game, and the title is
        # the only thing a player sees in autocomplete.
        assert await convoke_module.fetch_live_guild_wars(war_client({"wars": [row]})) == []

    async def test_a_missing_slug_falls_back_to_the_id(self) -> None:
        payload = {"wars": [{"id": WAR_ID, "title": "Summer Clash"}]}
        wars = await convoke_module.fetch_live_guild_wars(war_client(payload))
        assert wars == [
            {"id": WAR_ID, "title": "Summer Clash", "slug": WAR_ID, "status": "active"},
        ]

    async def test_a_non_string_status_falls_back_to_active(self) -> None:
        payload = {"wars": [{"id": WAR_ID, "title": "Summer Clash", "slug": "sc", "status": 7}]}
        wars = await convoke_module.fetch_live_guild_wars(war_client(payload))
        assert wars[0]["status"] == "active"


@pytest.mark.asyncio
class TestGetLiveGuildWars:
    async def test_returns_parsed_wars(self) -> None:
        payload = {"wars": [{"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash"}]}
        client = war_client(payload)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch.object(convoke_module.httpx, "AsyncClient", return_value=cm):
            wars = await convoke_module.get_live_guild_wars()

        assert [war["id"] for war in wars] == [WAR_ID]

    async def test_an_unreachable_convoke_yields_nothing(self) -> None:
        # `/war` autocomplete calls this on every keystroke, so a Convoke outage must
        # not surface as an error to the user.
        client = MagicMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch.object(convoke_module.httpx, "AsyncClient", return_value=cm):
            assert await convoke_module.get_live_guild_wars() == []


@pytest.mark.asyncio
class TestResolveLiveGuildWar:
    def patch_wars(self, wars: list[dict[str, str]]) -> AbstractContextManager[AsyncMock]:
        return patch.object(
            convoke_module,
            "get_live_guild_wars",
            AsyncMock(return_value=wars),
        )

    async def test_matches_by_id(self) -> None:
        war = {"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash", "status": "active"}
        with self.patch_wars([war]):
            assert await convoke_module.resolve_live_guild_war(WAR_ID) == war

    async def test_matches_by_slug(self) -> None:
        # Autocomplete submits the id, but someone typing the command by hand is far
        # more likely to have the slug from a Convoke URL.
        war = {"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash", "status": "active"}
        with self.patch_wars([war]):
            assert await convoke_module.resolve_live_guild_war("summer-clash") == war

    async def test_an_unknown_war_is_none(self) -> None:
        war = {"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash", "status": "active"}
        with self.patch_wars([war]):
            assert await convoke_module.resolve_live_guild_war("winter-clash") is None

    async def test_no_live_wars_is_none(self) -> None:
        with self.patch_wars([]):
            assert await convoke_module.resolve_live_guild_war(WAR_ID) is None
