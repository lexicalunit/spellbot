# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot.services import apps

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceApps:
    async def test_verify_token(self, factories: Factories) -> None:
        factories.token.create(key="key")
        assert await apps.verify_token("key", "/api/game/1/verify") is True
        assert await apps.verify_token("bogus", "/api/game/1/verify") is False

    async def test_verify_token_deleted(self, factories: Factories) -> None:
        """Test that deleted tokens are rejected."""
        factories.token.create(key="deleted_key", deleted_at=datetime.now(tz=UTC))
        assert await apps.verify_token("deleted_key", "/api/game/1/verify") is False

    async def test_verify_token_wildcard_scope(self, factories: Factories) -> None:
        """Test that wildcard scope grants access to all paths."""
        factories.token.create(key="wildcard_key", scopes="*")
        assert await apps.verify_token("wildcard_key", "/api/game/1/verify") is True
        assert await apps.verify_token("wildcard_key", "/api/anything/else") is True

    async def test_verify_token_specific_scope(self, factories: Factories) -> None:
        """Test that specific scopes only grant access to matching paths."""
        factories.token.create(key="specific_key", scopes="game,play")
        assert await apps.verify_token("specific_key", "/api/game/1/verify") is True
        assert await apps.verify_token("specific_key", "/api/play/1") is True
        assert await apps.verify_token("specific_key", "/api/other/1") is False

    async def test_verify_token_empty_required_scope(self, factories: Factories) -> None:
        """Test that empty required scope returns False."""
        factories.token.create(key="empty_scope_key", scopes="game")
        # Path where the second segment is empty after split
        # "/api//" -> ["", "api", "", ""] -> [1] is "api"
        # "/foo//" -> ["", "foo", "", ""] -> [1] is "foo"
        # We need a path like "/api/" where split gives ["", "api", ""] and [1] is "api"
        # Actually the check on line 22 is for when required_scope is empty string
        # Let's test with a path that produces an empty string at index 1
        # "//game" -> ["", "", "game"] -> [1] is "" which triggers the check
        assert await apps.verify_token("empty_scope_key", "//game/1") is False

    async def test_verify_token_action_scope(self, factories: Factories) -> None:
        """An action scope grants that one endpoint and nothing else under the resource."""
        factories.token.create(key="verify_only", scopes="game:verify")
        assert await apps.verify_token("verify_only", "/api/game/1/verify") is True
        assert await apps.verify_token("verify_only", "/api/game/1/record") is False
        assert await apps.verify_token("verify_only", "/api/game/1/metadata") is False

    async def test_verify_token_resource_scope_grants_every_action(
        self,
        factories: Factories,
    ) -> None:
        factories.token.create(key="all_game", scopes="game")
        for action in ("verify", "record", "metadata"):
            assert await apps.verify_token("all_game", f"/api/game/1/{action}") is True

    async def test_verify_token_when_path_is_bad(self, factories: Factories) -> None:
        """Test that a bad path doesn't crash and returns False."""
        factories.token.create(key="key", scopes="game")
        assert await apps.verify_token("key", "/bogus") is False

    async def test_create_token(self) -> None:
        token, key = await apps.create_token(scopes="game,record", note="Mythic Track")
        assert token.key_hash == apps.hash_api_key(key)
        assert key not in token.key_hash
        assert token.scopes == "game,record"
        assert token.note == "Mythic Track"
        assert await apps.verify_token(key, "/api/game/1/verify") is True

    async def test_create_token_keys_are_unique(self) -> None:
        _, first = await apps.create_token(scopes="*", note=None)
        _, second = await apps.create_token(scopes="*", note=None)
        assert first != second

    async def test_list_tokens(self, factories: Factories) -> None:
        active = factories.token.create(note="active")
        revoked = factories.token.create(note="revoked", deleted_at=datetime.now(tz=UTC))
        assert [token.id for token in await apps.list_tokens()] == [active.id]
        listed = await apps.list_tokens(include_revoked=True)
        assert [token.id for token in listed] == [active.id, revoked.id]

    async def test_revoke_token(self, factories: Factories) -> None:
        token = factories.token.create(key="to-revoke")
        assert await apps.revoke_token(token.id) is True
        assert await apps.verify_token("to-revoke", "/api/game/1/verify") is False
        assert await apps.revoke_token(token.id) is False

    async def test_revoke_missing_token(self) -> None:
        assert await apps.revoke_token(404) is False


class TestHashApiKey:
    def test_hash_api_key(self) -> None:
        assert apps.hash_api_key("abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )


class TestGrantingScopes:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            pytest.param("/api/game/1/record", {"game", "game:record"}, id="action"),
            pytest.param("/api/game/1", {"game"}, id="no-action"),
            pytest.param("/bogus", set(), id="too-short"),
        ],
    )
    def test_granting_scopes(self, path: str, expected: set[str]) -> None:
        assert apps.granting_scopes(path) == expected


class TestParseScopes:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param("game", "game", id="single"),
            pytest.param(" game, ,record ", "game,record", id="messy"),
            pytest.param("*", "*", id="wildcard"),
            pytest.param(" , ", None, id="blank"),
        ],
    )
    def test_parse_scopes(self, raw: str, expected: str | None) -> None:
        assert apps.parse_scopes(raw) == expected
