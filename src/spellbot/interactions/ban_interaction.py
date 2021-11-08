import logging
from typing import Optional

from discord.ext import commands

from .. import SpellBot
from ..operations import safe_send_user
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class BanInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot):
        super().__init__(bot)

    async def set_banned(self, banned: bool, ctx: commands.Context, arg: Optional[str]):
        assert ctx.message
        if arg is None:
            return await safe_send_user(ctx.message.author, "No target user.")
        user_xid: int
        try:
            user_xid = int(arg)
        except ValueError:
            return await safe_send_user(ctx.message.author, "Invalid user id.")
        await self.services.users.set_banned(banned, user_xid)
        await safe_send_user(
            ctx.message.author,
            f"User <@{user_xid}> has been {'banned' if banned else 'unbanned'}.",
        )
