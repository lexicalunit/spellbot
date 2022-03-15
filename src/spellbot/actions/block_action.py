from __future__ import annotations

import logging
from enum import Enum
from typing import Union

import discord

from ..operations import safe_send_channel
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ActionType(Enum):
    BLOCK = "blocked"
    UNBLOCK = "unblocked"


class BlockAction(BaseAction):
    async def execute(
        self,
        target: Union[discord.User, discord.Member],
        action: ActionType,
    ) -> None:
        await self.services.users.upsert(target)

        assert hasattr(target, "id")
        target_xid = target.id  # type: ignore

        if self.interaction.user.id == target_xid:
            await safe_send_channel(
                self.interaction,
                "You can not block yourself.",
                ephemeral=True,
            )
            return

        if action is ActionType.BLOCK:
            await self.services.users.block(self.interaction.user.id, target_xid)
        else:
            await self.services.users.unblock(self.interaction.user.id, target_xid)
        await safe_send_channel(
            self.interaction,
            f"<@{target_xid}> has been {action.value}.",
            ephemeral=True,
        )

    async def block(self, target: Union[discord.User, discord.Member]) -> None:
        await self.execute(target, ActionType.BLOCK)

    async def unblock(self, target: Union[discord.User, discord.Member]) -> None:
        await self.execute(target, ActionType.UNBLOCK)
