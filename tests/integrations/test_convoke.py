# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, ClassVar

import httpx
import pytest

import spellbot.integrations.convoke as convoke_module
from spellbot.data import GameLinkDetails
from spellbot.enums import GameBracket, GameFormat
from spellbot.integrations import http_errors
from spellbot.integrations.convoke import (
    ConvokeGameTypes,
    LiveGuildWarsCache,
    convoke_game_format,
    fetch_convoke_link,
    generate_link,
    parse_convoke_guild,
    update_players,
)
from tests.mocks import create_mock_game, decoys
from tests.mocks.decoys import ANY
from tests.mocks.http import client_for, in_order, raising, recording_client, serve_httpx

if TYPE_CHECKING:
    from decoy import Decoy

    from spellbot.data import GameData
    from spellbot.integrations.convoke import LiveGuildWar
    from tests.fixtures import Stub
    from tests.mocks.http import JSON, Responder


@pytest.fixture(autouse=True)
def empty_live_guild_wars_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test with no cached Guild Wars, so it sees its own Convoke responses."""
    monkeypatch.setattr(convoke_module, "live_guild_wars_cache", LiveGuildWarsCache())


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
    async def test_fetch_convoke_link_success(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, requests = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/123"})
        )

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

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            players
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        result = await fetch_convoke_link(
            mock_client,
            game,
            pins={200: "654321", 100: "123456"},
        )

        assert result == {"url": "https://convoke.gg/game/123"}
        assert len(requests) == 1
        payload = json.loads(requests[0].content)
        assert payload["spellbotGameId"] == "42"
        # Convoke pairs pins with players by index, whatever order the pins were generated in.
        assert payload["spellbotGamePins"] == ["123456", "654321"]
        assert payload["discordPlayers"] == [
            {"id": "100", "name": "Player1"},
            {"id": "200", "name": "Player2"},
        ]

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_bracket(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, requests = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/456"})
        )

        game = create_mock_game(
            game_id=99,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.BRACKET_2.value,
        )

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/456"}
        payload = json.loads(requests[0].content)
        assert payload["bracketLevel"] == "B2"  # BRACKET_2.value (3) -> B{3-1} = B2

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_guild_war(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, requests = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/war"})
        )

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

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/war"}
        payload = json.loads(requests[0].content)
        assert payload["warId"] == war_id
        assert "warPodMode" not in payload

    @pytest.mark.asyncio
    @pytest.mark.parametrize("competitive_mode", [True, False], ids=["enabled", "disabled"])
    async def test_fetch_convoke_link_with_competitive_mode(
        self,
        competitive_mode: bool,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, requests = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/789"})
        )

        game = create_mock_game(
            game_id=11,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
            competitive_mode=competitive_mode,
        )

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        await fetch_convoke_link(mock_client, game, pins=None)

        payload = json.loads(requests[0].content)
        if competitive_mode:
            assert payload["competitiveMode"] is True
        else:
            # Omitted rather than sent as False so Convoke's B5 default still applies.
            assert "competitiveMode" not in payload

    @pytest.mark.asyncio
    async def test_fetch_live_guild_wars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_client, requests = recording_client(
            httpx.Response(
                200,
                json={
                    "wars": [
                        {
                            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                            "title": "Summer Clash",
                            "slug": "summer-clash",
                            "status": "active",
                            "participants": [{"communityId": 1}, {"communityId": 2}],
                        },
                    ],
                },
            )
        )

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        wars = await convoke_module.fetch_live_guild_wars(mock_client)

        assert wars == [
            {
                "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "title": "Summer Clash",
                "slug": "summer-clash",
                "status": "active",
            },
        ]
        assert str(requests[0].url) == "https://api.convoke.gg/guild-wars/live"

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_precons(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, requests = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/456"})
        )

        game = create_mock_game(
            game_id=99,
            game_format=GameFormat.PRE_CONS.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/456"}
        payload = json.loads(requests[0].content)
        assert payload["bracketLevel"] == "PRECON"

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_password(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, _ = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/789"})
        )

        game = create_mock_game(
            game_id=101,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/789"}

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_supported_locale(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, requests = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/123"})
        )

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
            locale="ja",
        )

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/123"}
        payload = json.loads(requests[0].content)
        assert payload["language"] == "ja"

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_unsupported_locale(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client, requests = recording_client(
            httpx.Response(200, json={"url": "https://convoke.gg/game/123"})
        )

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
            locale="ko",  # Korean - not in SUPPORTED_LOCALES
        )

        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        result = await fetch_convoke_link(mock_client, game, pins=None)

        assert result == {"url": "https://convoke.gg/game/123"}
        payload = json.loads(requests[0].content)
        # Falls back to "en" for unsupported locales
        assert payload["language"] == "en"


class TestConvokeGuild:
    GUILD: ClassVar[dict[str, str]] = {
        "name": "Cool Guild",
        "url": "https://convoke.games/en/guild/cool",
        "joinMode": "open",
    }

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            pytest.param({}, (None, None), id="missing"),
            pytest.param({"guild": "nope"}, (None, None), id="not-a-dict"),
            pytest.param(
                {"guild": {**GUILD, "joinMode": "invite"}},
                (None, None),
                id="invite-only",
            ),
            pytest.param({"guild": {**GUILD, "name": 1}}, (None, None), id="bad-name-type"),
            pytest.param({"guild": {**GUILD, "url": None}}, (None, None), id="bad-url-type"),
            pytest.param({"guild": {**GUILD, "name": ""}}, (None, None), id="empty-name"),
            pytest.param({"guild": {**GUILD, "name": "x" * 500}}, (None, None), id="long-name"),
            pytest.param(
                {"guild": {**GUILD, "url": "https://x.co/" + "a" * 300}},
                (None, None),
                id="long-url",
            ),
            pytest.param(
                {"guild": {**GUILD, "url": "javascript:alert(1)"}},
                (None, None),
                id="non-https-url",
            ),
            pytest.param(
                {"guild": GUILD},
                ("Cool Guild", "https://convoke.games/en/guild/cool"),
                id="open",
            ),
            pytest.param(
                {"guild": {**GUILD, "joinMode": "approval"}},
                ("Cool Guild", "https://convoke.games/en/guild/cool"),
                id="approval",
            ),
        ],
    )
    def test_parse_convoke_guild(
        self,
        data: dict[str, object],
        expected: tuple[str | None, str | None],
    ) -> None:
        assert parse_convoke_guild(data) == expected

    @pytest.mark.asyncio
    async def test_generate_link_includes_guild(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        game = create_mock_game(game_id=1)
        response = {"url": "https://convoke.gg/game/123", "guild": self.GUILD}

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        fetch_convoke_link_fake = stub(convoke_module, "fetch_convoke_link")
        decoy.when(
            await fetch_convoke_link_fake(client=ANY, game_data=ANY, pins=ANY),
            ignore_extra_args=True,
        ).then_return(response)
        result = await generate_link(game, pins=None)

        assert result == GameLinkDetails(
            "https://convoke.gg/game/123",
            None,
            "Cool Guild",
            "https://convoke.games/en/guild/cool",
        )


class TestGenerateLink:
    @pytest.mark.asyncio
    async def test_generate_link_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        game = create_mock_game(game_id=1, game_format=GameFormat.COMMANDER.value)

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "")
        result = await generate_link(game, pins=None)

        assert result == GameLinkDetails()

    @pytest.mark.asyncio
    async def test_generate_link_success(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        fetch_convoke_link_fake = stub(convoke_module, "fetch_convoke_link")
        decoy.when(
            await fetch_convoke_link_fake(client=ANY, game_data=ANY, pins=ANY),
            ignore_extra_args=True,
        ).then_return({"url": "https://convoke.gg/game/123"})
        result = await generate_link(game, pins=None)

        assert result == GameLinkDetails("https://convoke.gg/game/123")

    @pytest.mark.asyncio
    async def test_generate_link_success_with_password_from_response(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        fetch_convoke_link_fake = stub(convoke_module, "fetch_convoke_link")
        decoy.when(
            await fetch_convoke_link_fake(client=ANY, game_data=ANY, pins=ANY),
            ignore_extra_args=True,
        ).then_return({"url": "https://convoke.gg/game/123", "password": "resp_pass"})
        result = await generate_link(game, pins=None)

        assert result == GameLinkDetails("https://convoke.gg/game/123", "resp_pass")

    @pytest.mark.asyncio
    async def test_generate_link_retries_on_failure_then_succeeds(
        self,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that generate_link retries after failure and succeeds on second attempt."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        # The first attempt fails, the second succeeds.
        requests = serve_httpx(
            monkeypatch,
            in_order(
                httpx.ConnectError,
                httpx.Response(200, json={"url": "https://convoke.gg/game/789"}),
            ),
        )

        mock_player_data = decoys.async_returning([])

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        stub(http_errors, "add_span_error")
        monkeypatch.setattr(convoke_module.services.games, "player_convoke_data", mock_player_data)
        result = await generate_link(game, pins=None)

        # First attempt fails, second succeeds
        assert result == GameLinkDetails("https://convoke.gg/game/789")
        assert len(requests) == 2

    @pytest.mark.asyncio
    async def test_generate_link_fails_after_all_retries(
        self,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that generate_link returns None after exhausting all retry attempts."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        requests = serve_httpx(monkeypatch, raising())

        mock_player_data = decoys.async_returning([])

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        stub(http_errors, "add_span_error")
        monkeypatch.setattr(convoke_module.services.games, "player_convoke_data", mock_player_data)
        result = await generate_link(game, pins=None)

        # All attempts fail, returns None
        assert result == GameLinkDetails()
        # Verify that the post method was called RETRY_ATTEMPTS times (2)
        assert len(requests) == convoke_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_generate_link_returns_none_when_data_is_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that generate_link returns None when fetch_convoke_link returns empty dict."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        # Convoke answers with an empty dict (falsy)
        serve_httpx(monkeypatch, in_order(httpx.Response(200, json={})))

        mock_player_data = decoys.async_returning([])

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        monkeypatch.setattr(convoke_module.services.games, "player_convoke_data", mock_player_data)
        result = await generate_link(game, pins=None)

        # Empty dict is falsy, so returns None
        assert result == GameLinkDetails()

    @pytest.mark.asyncio
    async def test_generate_link_zero_retry_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that generate_link returns None when RETRY_ATTEMPTS is 0 (loop never executes)."""
        game = create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        monkeypatch.setattr(convoke_module, "RETRY_ATTEMPTS", 0)
        result = await generate_link(game, pins=None)

        assert result == GameLinkDetails()


@pytest.mark.asyncio
class TestUpdatePlayers:
    players: ClassVar[list[dict[str, object]]] = [
        {"xid": 100, "name": "Player1"},
        {"xid": 200, "name": "Player2"},
    ]

    def game(self, game_link: str | None = "https://convoke.games/en/play/abc-123/") -> GameData:
        return create_mock_game(game_id=42, game_link=game_link)

    async def test_puts_the_final_roster_with_aligned_pins(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        requests = serve_httpx(monkeypatch, lambda _: httpx.Response(200))

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg")
        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            self.players
        )
        await update_players(self.game(), {200: "654321", 100: "123456"})

        [request] = requests
        assert (request.method, str(request.url)) == (
            "PUT",
            "https://api.convoke.gg/game/abc-123/spellbot-players",
        )
        assert json.loads(request.content) == {
            "discordPlayers": [
                {"id": "100", "name": "Player1"},
                {"id": "200", "name": "Player2"},
            ],
            "spellbotGamePins": ["123456", "654321"],
        }
        assert request.headers["x-api-key"] == "test_key"

    async def test_gives_up_after_all_retries(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        requests = serve_httpx(monkeypatch, raising())

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        add_span_error = stub(http_errors, "add_span_error")
        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            self.players
        )
        await update_players(self.game(), {100: "123456", 200: "654321"})

        assert len(requests) == convoke_module.RETRY_ATTEMPTS
        decoy.verify(add_span_error(ex=ANY), times=1, ignore_extra_args=True)

    @pytest.mark.parametrize(
        ("api_key", "game_link"),
        [
            pytest.param("", "https://convoke.games/en/play/abc-123", id="no-api-key"),
            pytest.param("test_key", None, id="no-link"),
        ],
    )
    async def test_does_nothing_without_a_key_or_link(
        self,
        api_key: str,
        game_link: str | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", api_key)
        requests = serve_httpx(monkeypatch, raising())
        await update_players(self.game(game_link), {100: "123456"})

        assert requests == []


def war_client(payload: JSON) -> httpx.AsyncClient:
    return client_for(lambda _: httpx.Response(200, json=payload))


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
    async def test_a_payload_we_do_not_recognize_yields_nothing(self, payload: JSON) -> None:
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
    async def test_rows_without_a_usable_id_and_title_are_skipped(self, row: JSON) -> None:
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
    async def test_returns_parsed_wars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {"wars": [{"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash"}]}
        serve_httpx(monkeypatch, lambda _: httpx.Response(200, json=payload))
        wars = await convoke_module.get_live_guild_wars()

        assert [war["id"] for war in wars] == [WAR_ID]

    async def test_an_unreachable_convoke_yields_nothing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # `/war` autocomplete calls this on every keystroke, so a Convoke outage must
        # not surface as an error to the user.
        serve_httpx(monkeypatch, raising())
        assert await convoke_module.get_live_guild_wars() == []


class Clock:
    """A settable stand-in for `monotonic`."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(convoke_module, "monotonic", clock)
    return clock


@pytest.mark.asyncio
class TestLiveGuildWarsCache:
    PAYLOAD: ClassVar = {"wars": [{"id": WAR_ID, "title": "Summer Clash"}]}

    async def test_reuses_the_list_until_it_expires(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clock: Clock,
    ) -> None:
        requests = serve_httpx(monkeypatch, lambda _: httpx.Response(200, json=self.PAYLOAD))
        first = await convoke_module.get_live_guild_wars()
        clock.now += convoke_module.LIVE_GUILD_WARS_TTL_S - 1
        assert await convoke_module.get_live_guild_wars() == first
        assert len(requests) == 1

        clock.now += 1
        assert await convoke_module.get_live_guild_wars() == first
        assert len(requests) == 2

    async def test_concurrent_callers_share_one_fetch(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        war: LiveGuildWar = {"id": WAR_ID, "title": "Summer Clash", "slug": WAR_ID, "status": "x"}
        fetches: list[httpx.AsyncClient] = []

        async def slow_fetch(client: httpx.AsyncClient) -> list[LiveGuildWar]:
            fetches.append(client)
            await asyncio.sleep(0)  # let the other callers run while this one is in flight
            return [war]

        monkeypatch.setattr(convoke_module, "fetch_live_guild_wars", slow_fetch)
        results = await asyncio.gather(*(convoke_module.get_live_guild_wars() for _ in range(5)))
        assert results == [[war]] * 5
        assert len(fetches) == 1

    async def test_failures_are_retried_after_a_short_wait(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clock: Clock,
    ) -> None:
        requests = serve_httpx(
            monkeypatch,
            in_order(httpx.ConnectError, httpx.Response(200, json=self.PAYLOAD)),
        )
        assert await convoke_module.get_live_guild_wars() == []
        clock.now += convoke_module.LIVE_GUILD_WARS_RETRY_S - 1
        assert await convoke_module.get_live_guild_wars() == []
        assert len(requests) == 1

        clock.now += 1
        wars = await convoke_module.get_live_guild_wars()
        assert [war["id"] for war in wars] == [WAR_ID]
        assert len(requests) == 2


@pytest.mark.asyncio
class TestResolveLiveGuildWar:
    @staticmethod
    def use_wars(monkeypatch: pytest.MonkeyPatch, wars: list[dict[str, str]]) -> None:
        monkeypatch.setattr(convoke_module, "get_live_guild_wars", decoys.async_returning(wars))

    async def test_matches_by_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        war = {"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash", "status": "active"}
        self.use_wars(monkeypatch, [war])
        assert await convoke_module.resolve_live_guild_war(WAR_ID) == war

    async def test_matches_by_slug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Autocomplete submits the id, but someone typing the command by hand is far
        # more likely to have the slug from a Convoke URL.
        war = {"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash", "status": "active"}
        self.use_wars(monkeypatch, [war])
        assert await convoke_module.resolve_live_guild_war("summer-clash") == war

    async def test_an_unknown_war_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        war = {"id": WAR_ID, "title": "Summer Clash", "slug": "summer-clash", "status": "active"}
        self.use_wars(monkeypatch, [war])
        assert await convoke_module.resolve_live_guild_war("winter-clash") is None

    async def test_no_live_wars_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.use_wars(monkeypatch, [])
        assert await convoke_module.resolve_live_guild_war(WAR_ID) is None


class TestConvokeTerminalClientErrors:
    """A 4xx from Convoke means the request was wrong, so replaying it only wastes attempts."""

    @staticmethod
    def make_game() -> GameData:
        return create_mock_game(
            game_id=1,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            guild_xid=12345,
            channel_xid=67890,
            bracket=GameBracket.NONE.value,
        )

    @staticmethod
    def always(status: int, body: str = "") -> Responder:
        """Answer every request with `status` and `body`."""
        return lambda _: httpx.Response(status, text=body)

    @pytest.mark.asyncio
    async def test_400_is_not_retried(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        requests = serve_httpx(monkeypatch, self.always(400, '{"error":"invalid_body"}'))

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        stub(http_errors, "add_span_error")
        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        result = await generate_link(self.make_game(), pins=None)

        assert result == GameLinkDetails()
        assert len(requests) == 1

    @pytest.mark.asyncio
    async def test_400_logs_the_response_body(
        self,
        caplog: pytest.LogCaptureFixture,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        serve_httpx(monkeypatch, self.always(400, '{"error":"invalid_body","details":"seatLimit"}'))

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        stub(http_errors, "add_span_error")
        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        await generate_link(self.make_game(), pins=None)

        assert "seatLimit" in caplog.text
        assert "HTTP 400" in caplog.text

    @pytest.mark.asyncio
    async def test_429_is_still_retried(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        requests = serve_httpx(monkeypatch, self.always(429))

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        stub(http_errors, "add_span_error")
        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        result = await generate_link(self.make_game(), pins=None)

        assert result == GameLinkDetails()
        assert len(requests) == convoke_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_500_is_still_retried(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        requests = serve_httpx(monkeypatch, self.always(500))

        monkeypatch.setattr(convoke_module.settings, "CONVOKE_API_KEY", "test_key")
        stub(http_errors, "add_span_error")
        player_convoke_data_fake = stub(convoke_module.services.games, "player_convoke_data")
        decoy.when(await player_convoke_data_fake(game_id=ANY), ignore_extra_args=True).then_return(
            []
        )
        result = await generate_link(self.make_game(), pins=None)

        assert result == GameLinkDetails()
        assert len(requests) == convoke_module.RETRY_ATTEMPTS
