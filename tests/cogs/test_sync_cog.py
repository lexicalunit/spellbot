from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from spellbot.cogs import SyncCog
from tests.mixins import ContextMixin

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.asyncio
class TestCogSync(ContextMixin):
    async def test_sync(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.cogs.sync_cog.load_extensions", AsyncMock())
        cog = SyncCog(self.bot)
        callback = partial(cog.sync.callback, cog)

        await callback(self.context)

        self.context.author.send.assert_called_once_with("Commands synced!")

    async def test_sync_exception(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.cogs.sync_cog.load_extensions",
            AsyncMock(side_effect=RuntimeError("oops")),
        )
        cog = SyncCog(self.bot)
        callback = partial(cog.sync.callback, cog)

        with pytest.raises(RuntimeError):
            await callback(self.context)

        self.context.author.send.assert_called_once_with("Error: oops")
