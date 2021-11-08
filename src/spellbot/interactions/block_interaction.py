import logging
from enum import Enum
from typing import Union

import discord
from discord_slash.context import InteractionContext

from .. import SpellBot
from ..operations import safe_send_channel
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class ActionType(Enum):
    BLOCK = "blocked"
    UNBLOCK = "unblocked"


class BlockInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)

    async def execute(
        self,
        target: Union[discord.User, discord.Member],
        action: ActionType,
    ):
        assert self.ctx
        await self.services.users.upsert(target)

        assert hasattr(target, "id")
        target_xid = target.id  # type: ignore
        if action is ActionType.BLOCK:
            await self.services.users.block(self.ctx.author_id, target_xid)
        else:
            await self.services.users.unblock(self.ctx.author_id, target_xid)
        await safe_send_channel(
            self.ctx,
            f"<@{target_xid}> has been {action.value}.",
            hidden=True,
        )

    async def block(self, target: Union[discord.User, discord.Member]):
        await self.execute(target, ActionType.BLOCK)

    async def unblock(self, target: Union[discord.User, discord.Member]):
        await self.execute(target, ActionType.UNBLOCK)
