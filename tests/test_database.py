# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from spellbot.database import DatabaseSession, ProcessGlobal, end_session, to_async_url

if TYPE_CHECKING:
    from decoy import Decoy


@pytest.mark.asyncio
async def test_end_session_closes_when_commit_fails(decoy: Decoy) -> None:
    """
    A failed commit must still return the connection to the pool.

    An `AsyncSession` cannot be reclaimed by the garbage collector, so skipping
    `close()` here would permanently burn a pool slot for the life of the process.
    """
    session = decoy.mock(cls=AsyncSession)
    decoy.when(await session.commit()).then_raise(RuntimeError("commit failed"))
    token = DatabaseSession.set(session)

    with pytest.raises(RuntimeError, match="commit failed"):
        await end_session(token)

    decoy.verify(await session.close(), times=1)


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


class TestToAsyncUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            pytest.param("postgresql+psycopg://h/db", "postgresql+psycopg://h/db", id="psycopg"),
            pytest.param("postgresql://h/db", "postgresql+psycopg://h/db", id="plain"),
            pytest.param("sqlite:///db", "sqlite:///db", id="other"),
        ],
    )
    def test_to_async_url(self, url: str, expected: str) -> None:
        assert to_async_url(url) == expected
