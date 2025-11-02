from __future__ import annotations

import logging
from inspect import cleandoc
from typing import TYPE_CHECKING

from ddtrace.trace import tracer
from discord.ext import commands

from spellbot.actions.base_action import handle_exception
from spellbot.database import db_session_manager
from spellbot.metrics import add_span_context
from spellbot.operations import is_bad_user, safe_send_user
from spellbot.services import ServicesRegistry
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, load_extensions

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


async def set_banned(banned: bool, ctx: commands.Context[SpellBot], arg: str | None) -> None:
    assert ctx.message
    if arg is None:
        return await safe_send_user(ctx.message.author, "No target user.")

    user_xid: int
    try:
        user_xid = int(arg)
    except ValueError:
        return await safe_send_user(ctx.message.author, "Invalid user id.")
    services = ServicesRegistry()
    await services.users.set_banned(banned, user_xid)
    await safe_send_user(
        ctx.message.author,
        f"User <@{user_xid}> has been {'banned' if banned else 'unbanned'}.",
    )
    return None


async def set_banned_guild(banned: bool, ctx: commands.Context[SpellBot], arg: str | None) -> None:
    assert ctx.message
    if arg is None:
        return await safe_send_user(ctx.message.author, "No target guild.")

    guild_xid: int
    try:
        guild_xid = int(arg)
    except ValueError:
        return await safe_send_user(ctx.message.author, "Invalid guild id.")
    services = ServicesRegistry()
    await services.guilds.set_banned(banned, guild_xid)
    await safe_send_user(
        ctx.message.author,
        f"Guild {guild_xid} has been {'banned' if banned else 'unbanned'}.",
    )
    return None


@for_all_callbacks(commands.is_owner())
class OwnerCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    @tracer.wrap(name="interaction", resource="sync")
    async def sync(self, ctx: commands.Context[SpellBot]) -> None:
        add_span_context(self.bot)
        try:
            await load_extensions(self.bot, do_sync=True)
            await safe_send_user(ctx.message.author, "Commands synced!")
        except Exception as ex:
            try:
                await safe_send_user(ctx.message.author, f"Error: {ex}")
            except Exception:  # pragma: no cover
                logger.exception("Failed to send error message to user.")
            await handle_exception(ex)

    @commands.command(name="ban")
    @tracer.wrap(name="interaction", resource="ban")
    async def ban(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        add_span_context(ctx)
        async with db_session_manager():
            try:
                await set_banned(True, ctx, arg)
            except Exception as ex:
                await safe_send_user(ctx.message.author, f"Error: {ex}")
                await handle_exception(ex)

    @commands.command(name="unban")
    @tracer.wrap(name="interaction", resource="unban")
    async def unban(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        add_span_context(ctx)
        async with db_session_manager():
            try:
                await set_banned(False, ctx, arg)
            except Exception as ex:
                await safe_send_user(ctx.message.author, f"Error: {ex}")
                await handle_exception(ex)

    @commands.command(name="ban_guild")
    @tracer.wrap(name="interaction", resource="ban_guild")
    async def ban_guild(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        add_span_context(ctx)
        async with db_session_manager():
            try:
                await set_banned_guild(True, ctx, arg)
            except Exception as ex:
                await safe_send_user(ctx.message.author, f"Error: {ex}")
                await handle_exception(ex)

    @commands.command(name="unban_guild")
    @tracer.wrap(name="interaction", resource="unban_guild")
    async def unban_guild(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        add_span_context(ctx)
        async with db_session_manager():
            try:
                await set_banned_guild(False, ctx, arg)
            except Exception as ex:
                await safe_send_user(ctx.message.author, f"Error: {ex}")
                await handle_exception(ex)

    @commands.command(name="stats")
    @tracer.wrap(name="interaction", resource="stats")
    async def stats(self, ctx: commands.Context[SpellBot]) -> None:
        add_span_context(ctx)
        await safe_send_user(
            ctx.message.author,
            cleandoc(
                f"""
                    ```
                    status:   {self.bot.status}
                    activity: {self.bot.activity}
                    ready:    {self.bot.is_ready()}
                    shards:   {self.bot.shard_count}
                    guilds:   {len(self.bot.guilds)}
                    users:    {len(self.bot.users)}
                    patrons:  {self.bot.supporters}
                    ```
                """,
            ),
        )

    @commands.command(name="is_bad")
    @tracer.wrap(name="interaction", resource="is_bad")
    async def is_bad(self, ctx: commands.Context[SpellBot], arg: str | None) -> None:
        add_span_context(ctx)
        result = await is_bad_user(arg)
        await safe_send_user(ctx.message.author, "Yes" if result else "No")


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(OwnerCog(bot), guild=settings.GUILD_OBJECT)
