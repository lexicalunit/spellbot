import logging
from typing import Union

import discord
from discord_slash.context import InteractionContext

from .. import SpellBot
from ..operations import safe_send_channel
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class VerifyInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)

    async def execute(self, target: Union[discord.User, discord.Member], setting: bool):
        assert self.ctx
        assert hasattr(target, "id")
        target_xid = target.id  # type: ignore

        await self.services.verifies.upsert(self.ctx.guild_id, target_xid, setting)
        await safe_send_channel(
            self.ctx,
            f"{'Verified' if setting else 'Unverified'} <@{target_xid}>.",
            hidden=True,
        )

    async def verify(self, target: Union[discord.User, discord.Member]):
        await self.execute(target, setting=True)

    async def unverify(self, target: Union[discord.User, discord.Member]):
        await self.execute(target, setting=False)
