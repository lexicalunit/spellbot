from __future__ import annotations

import logging
from enum import Enum
from typing import Union

import discord

from ..operations import safe_send_channel
from ..settings import Settings
from ..utils import EMBED_DESCRIPTION_SIZE_LIMIT
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

    async def blocked(self, page: int) -> None:
        settings = Settings()
        blocklist = await self.services.users.blocklist(self.interaction.user.id)
        embed = discord.Embed(title="Blocked Users")
        embed.set_thumbnail(url=settings.ICO_URL)
        pages = []
        cur_page = ""
        for xid in blocklist:
            next_user = f"<@{xid}>\n"
            if len(cur_page) + len(next_user) > EMBED_DESCRIPTION_SIZE_LIMIT:
                pages.append(cur_page)
                cur_page = ""
            cur_page += next_user
        if cur_page:
            pages.append(cur_page)
        embed.color = discord.Color(settings.EMBED_COLOR)
        if pages:
            index = min(page - 1, len(pages) - 1)
            embed.description = pages[index]
            embed.set_footer(text=f"Page {page} of {len(pages)}")
        else:
            embed.description = "You have no blocked users."
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
