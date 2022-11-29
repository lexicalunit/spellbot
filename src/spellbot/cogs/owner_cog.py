import logging
from inspect import cleandoc
from typing import Optional

from ddtrace import tracer
from discord.ext import commands

from .. import SpellBot
from ..actions.base_action import handle_exception
from ..database import db_session_manager
from ..metrics import add_span_context
from ..operations import safe_send_user
from ..services import UsersService
from ..utils import for_all_callbacks

logger = logging.getLogger(__name__)


async def set_banned(banned: bool, ctx: commands.Context[SpellBot], arg: Optional[str]):
    assert ctx.message
    if arg is None:
        return await safe_send_user(ctx.message.author, "No target user.")
    user_xid: int
    try:
        user_xid = int(arg)
    except ValueError:
        return await safe_send_user(ctx.message.author, "Invalid user id.")
    await UsersService().set_banned(banned, user_xid)
    await safe_send_user(
        ctx.message.author,
        f"User <@{user_xid}> has been {'banned' if banned else 'unbanned'}.",
    )


@for_all_callbacks(commands.is_owner())
class OwnerCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @commands.command(name="ban")
    @tracer.wrap(name="interaction", resource="ban")
    async def ban(self, ctx: commands.Context[SpellBot], arg: Optional[str] = None):
        add_span_context(ctx)
        async with db_session_manager():
            try:
                await set_banned(True, ctx, arg)
            except Exception as ex:
                await handle_exception(ex)

    @commands.command(name="unban")
    @tracer.wrap(name="interaction", resource="unban")
    async def unban(self, ctx: commands.Context[SpellBot], arg: Optional[str] = None):
        add_span_context(ctx)
        async with db_session_manager():
            try:
                await set_banned(False, ctx, arg)
            except Exception as ex:
                await handle_exception(ex)

    @commands.command(name="stats")
    @tracer.wrap(name="interaction", resource="stats")
    async def stats(self, ctx: commands.Context[SpellBot]):
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
                    ```
                """
            ),
        )


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(OwnerCog(bot), guild=bot.settings.GUILD_OBJECT)
