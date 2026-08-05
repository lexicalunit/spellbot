from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot.cogs import tasks_cog
from spellbot.cogs.tasks_cog import TasksCog

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_mock import MockerFixture

    from spellbot import SpellBot

PERIODIC_LOOPS = ("cleanup_old_voice_channels", "expire_inactive_games", "notify_pending_games")
ALL_LOOPS = (*PERIODIC_LOOPS, "process_web_actions")


@pytest.fixture
def outside_pytest(mocker: MockerFixture) -> None:
    """Let `TasksCog` start its loops, which it otherwise refuses to do under pytest."""
    mocker.patch.object(tasks_cog, "running_in_pytest", return_value=False)


def build_cog(bot: SpellBot) -> Iterator[TasksCog]:
    cog = TasksCog(bot)
    try:
        yield cog
    finally:
        for name in ALL_LOOPS:
            getattr(cog, name).cancel()
        cog.cog_unload()


@pytest.mark.asyncio
@pytest.mark.usefixtures("outside_pytest")
class TestTasksCog:
    async def test_all_loops_run_by_default(self, bot: SpellBot) -> None:
        bot.disable_tasks = False
        for cog in build_cog(bot):
            for name in ALL_LOOPS:
                assert getattr(cog, name).is_running(), name

    async def test_disable_tasks_stops_the_periodic_loops(self, bot: SpellBot) -> None:
        bot.disable_tasks = True
        for cog in build_cog(bot):
            for name in PERIODIC_LOOPS:
                assert not getattr(cog, name).is_running(), name

    async def test_disable_tasks_still_handles_website_requests(self, bot: SpellBot) -> None:
        # `--disable-tasks` silences periodic upkeep, but the Play page depends on this
        # loop to reach Discord at all: without it a website request sits unprocessed
        # until it expires, and the page just times out.
        bot.disable_tasks = True
        for cog in build_cog(bot):
            assert cog.process_web_actions.is_running()
