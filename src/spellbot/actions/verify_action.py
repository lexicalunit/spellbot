from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from spellbot.operations import safe_send_channel

from .base_action import BaseAction

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)


class VerifyAction(BaseAction):
    async def execute(self, target: discord.User | discord.Member, setting: bool) -> None:
        assert hasattr(target, "id")
        target_xid = target.id

        assert self.interaction.guild_id is not None
        await self.services.verifies.upsert(self.interaction.guild_id, target_xid, setting)
        await safe_send_channel(
            self.interaction,
            f"{'Verified' if setting else 'Unverified'} <@{target_xid}>.",
            ephemeral=True,
        )

    async def verify(self, target: discord.User | discord.Member) -> None:
        await self.execute(target, setting=True)

    async def unverify(self, target: discord.User | discord.Member) -> None:
        await self.execute(target, setting=False)
