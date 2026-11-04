# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from spellbot.database import DatabaseSession, ProcessGlobal, end_session


@pytest.mark.asyncio
async def test_end_session_closes_when_commit_fails() -> None:
    """
    A failed commit must still return the connection to the pool.

    An `AsyncSession` cannot be reclaimed by the garbage collector, so skipping
    `close()` here would permanently burn a pool slot for the life of the process.
    """
    session = MagicMock()
    session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    session.close = AsyncMock()
    token = DatabaseSession.set(session)

    with pytest.raises(RuntimeError, match="commit failed"):
        await end_session(token)

    session.close.assert_awaited_once_with()


class TestProcessGlobal:
    def test_get_before_set(self) -> None:
        holder = ProcessGlobal[int]("widget")
        assert holder.value is None
        with pytest.raises(RuntimeError, match="database widget isn't set up"):
            holder.get()

    def test_set_and_get(self) -> None:
        holder = ProcessGlobal[int]("widget")
        holder.set(7)
        assert holder.get() == 7
        assert holder.value == 7
