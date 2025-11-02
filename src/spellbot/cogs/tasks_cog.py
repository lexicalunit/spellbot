from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ddtrace.trace import tracer
from discord.ext import commands, tasks

from spellbot.actions import TasksAction
from spellbot.environment import running_in_pytest
from spellbot.settings import settings

if TYPE_CHECKING:
    from discord import Client

    from spellbot import SpellBot

logger = logging.getLogger(__name__)

WAIT_UNTIL_READY_TIMEOUT = 900.0  # 15 minutes


async def wait_until_ready(bot: Client) -> None:  # pragma: no cover
    while True:
        try:
            if bot.is_ready():
                logger.info("wait_until_ready: already ready")
                break

            # Note: bot.wait_until_ready() is not used because it sometimes hangs
            #       waiting for a ready event that never comes. Speculation is that
            #       what happens is the client gets a resumed event instead, so the
            #       ready event never triggers the wait_until_ready() to return.
            #       This is a workaround that waits for either a ready or resumed.
            #       See: https://github.com/Rapptz/discord.py/issues/9074 for details.
            _, unfinished = await asyncio.wait(
                [
                    asyncio.create_task(bot.wait_for("ready", timeout=WAIT_UNTIL_READY_TIMEOUT)),
                    asyncio.create_task(bot.wait_for("resumed", timeout=WAIT_UNTIL_READY_TIMEOUT)),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in unfinished:
                task.cancel()
            logger.info("wait_until_ready: ready or resumed")
            break
        except TimeoutError:
            logger.warning("wait_until_ready: timeout waiting for ready or resumed")
            break
        except BaseException:  # Catch EVERYTHING so tasks don't die
            logger.exception("error: exception in task before loop")


class TasksCog(commands.Cog):  # pragma: no cover
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot
        if not running_in_pytest():
            self.cleanup_old_voice_channels.start()
            self.expire_inactive_games.start()
            self.patreon_sync.start()

    @tasks.loop(minutes=settings.VOICE_CLEANUP_LOOP_M)
    async def cleanup_old_voice_channels(self) -> None:
        try:
            with tracer.trace(name="command", resource="cleanup_old_voice_channels"):
                async with TasksAction.create(self.bot) as action:
                    await action.cleanup_old_voice_channels()
        except BaseException:  # Catch EVERYTHING so tasks don't die
            logger.exception("error: exception in task cog")

    @cleanup_old_voice_channels.before_loop
    async def before_cleanup_old_voice_channels(self) -> None:
        await wait_until_ready(self.bot)

    @tasks.loop(minutes=settings.EXPIRE_GAMES_LOOP_M)
    async def expire_inactive_games(self) -> None:
        try:
            with tracer.trace(name="command", resource="expire_inactive_games"):
                async with TasksAction.create(self.bot) as action:
                    await action.expire_inactive_games()
        except BaseException:  # Catch EVERYTHING so tasks don't die
            logger.exception("error: exception in task cog")

    @expire_inactive_games.before_loop
    async def before_expire_inactive_games(self) -> None:
        await wait_until_ready(self.bot)

    @tasks.loop(minutes=settings.PATREON_SYNC_LOOP_M)
    async def patreon_sync(self) -> None:
        try:
            with tracer.trace(name="command", resource="patreon_sync"):
                async with TasksAction.create(self.bot) as action:
                    await action.patreon_sync()
        except BaseException:  # Catch EVERYTHING so tasks don't die
            logger.exception("error: exception in task cog")

    @patreon_sync.before_loop
    async def before_patreon_sync(self) -> None:
        await wait_until_ready(self.bot)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(TasksCog(bot), guild=settings.GUILD_OBJECT)
