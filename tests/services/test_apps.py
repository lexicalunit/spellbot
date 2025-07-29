from __future__ import annotations

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
        assert await apps.verify_token(token.key) is True
        assert await apps.verify_token("bogus") is False
