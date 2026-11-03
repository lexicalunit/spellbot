# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from inspect import cleandoc
from typing import TYPE_CHECKING

from discord.ext import commands

from spellbot import services
from spellbot.actions.base_action import handle_exception
from spellbot.database import db_session_manager
from spellbot.operations import safe_send_user
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, load_extensions, traced_interaction

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from spellbot import SpellBot

logger = logging.getLogger(__name__)


async def parse_target(ctx: commands.Context[SpellBot], arg: str | None, noun: str) -> int | None:
    """Parse a command's target id, telling the owner when it's missing or malformed."""
    if arg is None:
        await safe_send_user(ctx.message.author, f"No target {noun}.")
        return None
    try:
        return int(arg)
    except ValueError:
        await safe_send_user(ctx.message.author, f"Invalid {noun} id.")
        return None


async def set_banned(banned: bool, ctx: commands.Context[SpellBot], arg: str | None) -> None:
    if (user_xid := await parse_target(ctx, arg, "user")) is None:
        return
    await services.users.set_banned(user_xid, banned)
    await safe_send_user(
        ctx.message.author,
        f"User <@{user_xid}> has been {'banned' if banned else 'unbanned'}.",
    )


async def set_banned_guild(banned: bool, ctx: commands.Context[SpellBot], arg: str | None) -> None:
    if (guild_xid := await parse_target(ctx, arg, "guild")) is None:
        return
    await services.guilds.set_banned(guild_xid, banned)
    await safe_send_user(
        ctx.message.author,
        f"Guild {guild_xid} has been {'banned' if banned else 'unbanned'}.",
    )


async def set_admin(is_admin: bool, ctx: commands.Context[SpellBot], arg: str | None) -> None:
    if (user_xid := await parse_target(ctx, arg, "user")) is None:
        return
    await services.users.set_admin(user_xid, is_admin)
    await safe_send_user(
        ctx.message.author,
        f"User <@{user_xid}> is {'now an admin' if is_admin else 'no longer an admin'}.",
    )


async def run_owner_op(ctx: commands.Context[SpellBot], op: Awaitable[None]) -> None:
    """Run an owner command's database operation, reporting any failure back to the owner."""
    async with db_session_manager():
        try:
            await op
        except Exception as ex:
            await safe_send_user(ctx.message.author, f"Error: {ex}")
            await handle_exception(ex)


@for_all_callbacks(commands.is_owner())
class OwnerCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    @traced_interaction()
    async def sync(self, ctx: commands.Context[SpellBot]) -> None:
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
    @traced_interaction()
    async def ban(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        await run_owner_op(ctx, set_banned(True, ctx, arg))

    @commands.command(name="unban")
    @traced_interaction()
    async def unban(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        await run_owner_op(ctx, set_banned(False, ctx, arg))

    @commands.command(name="ban_guild")
    @traced_interaction()
    async def ban_guild(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        await run_owner_op(ctx, set_banned_guild(True, ctx, arg))

    @commands.command(name="unban_guild")
    @traced_interaction()
    async def unban_guild(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        await run_owner_op(ctx, set_banned_guild(False, ctx, arg))

    @commands.command(name="promote")
    @traced_interaction()
    async def promote(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        await run_owner_op(ctx, set_admin(True, ctx, arg))

    @commands.command(name="demote")
    @traced_interaction()
    async def demote(self, ctx: commands.Context[SpellBot], arg: str | None = None) -> None:
        await run_owner_op(ctx, set_admin(False, ctx, arg))

    @commands.command(name="stats")
    @traced_interaction()
    async def stats(self, ctx: commands.Context[SpellBot]) -> None:
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


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(OwnerCog(bot), guild=settings.GUILD_OBJECT)
