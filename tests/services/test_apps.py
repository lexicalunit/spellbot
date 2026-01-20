from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot.services import AppsService

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceApps:
    async def test_verify_token(self, factories: Factories) -> None:
        apps = AppsService()
        token = factories.token.create(key="key")
        assert await apps.verify_token(token.key, "/api/game/1/verify") is True
        assert await apps.verify_token("bogus", "/api/game/1/verify") is False

    async def test_verify_token_deleted(self, factories: Factories) -> None:
        """Test that deleted tokens are rejected."""
        apps = AppsService()
        token = factories.token.create(key="deleted_key", deleted_at=datetime.now(tz=UTC))
        assert await apps.verify_token(token.key, "/api/game/1/verify") is False

    async def test_verify_token_wildcard_scope(self, factories: Factories) -> None:
        """Test that wildcard scope grants access to all paths."""
        apps = AppsService()
        token = factories.token.create(key="wildcard_key", scopes="*")
        assert await apps.verify_token(token.key, "/api/game/1/verify") is True
        assert await apps.verify_token(token.key, "/api/notification/1") is True
        assert await apps.verify_token(token.key, "/api/anything/else") is True

    async def test_verify_token_specific_scope(self, factories: Factories) -> None:
        """Test that specific scopes only grant access to matching paths."""
        apps = AppsService()
        token = factories.token.create(key="specific_key", scopes="game,notification")
        assert await apps.verify_token(token.key, "/api/game/1/verify") is True
        assert await apps.verify_token(token.key, "/api/notification/1") is True
        assert await apps.verify_token(token.key, "/api/other/1") is False

    async def test_verify_token_empty_required_scope(self, factories: Factories) -> None:
        """Test that empty required scope returns False."""
        apps = AppsService()
        token = factories.token.create(key="empty_scope_key", scopes="game")
        # Path where the second segment is empty after split
        # "/api//" -> ["", "api", "", ""] -> [1] is "api"
        # "/foo//" -> ["", "foo", "", ""] -> [1] is "foo"
        # We need a path like "/api/" where split gives ["", "api", ""] and [1] is "api"
        # Actually the check on line 22 is for when required_scope is empty string
        # Let's test with a path that produces an empty string at index 1
        # "//game" -> ["", "", "game"] -> [1] is "" which triggers the check
        assert await apps.verify_token(token.key, "//game/1") is False

    async def test_verify_token_when_path_is_bad(self, factories: Factories) -> None:
        """Test that a bad path doesn't crash and returns False."""
        apps = AppsService()
        token = factories.token.create(key="key", scopes="game")
        assert await apps.verify_token(token.key, "/bogus") is False
