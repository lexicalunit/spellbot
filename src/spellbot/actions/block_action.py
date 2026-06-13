from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from spellbot import services
from spellbot.i18n import t, user_locale
from spellbot.operations import safe_send_channel
from spellbot.settings import settings

from .base_action import BaseAction

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)


class ActionType(Enum):
    BLOCK = "blocked"
    UNBLOCK = "unblocked"


class BlockAction(BaseAction):
    async def execute(
        self,
        target: discord.User | discord.Member,
        action: ActionType,
    ) -> None:
        await services.users.upsert(target)
        locale = user_locale(self.interaction)

        assert hasattr(target, "id")
        target_xid = target.id

        if self.interaction.user.id == target_xid:
            await safe_send_channel(
                self.interaction,
                t("block.self_block", locale=locale),
                ephemeral=True,
            )
            return

        if action is ActionType.BLOCK:
            await services.users.block(self.interaction.user.id, target_xid)
            msg = t("block.blocked", locale=locale, user_id=target_xid)
        else:
            await services.users.unblock(self.interaction.user.id, target_xid)
            msg = t("block.unblocked", locale=locale, user_id=target_xid)
        cta = t("block.manage_message", locale=locale, link=self.blocklist_link())
        await safe_send_channel(self.interaction, f"{msg}\n\n{cta}", ephemeral=True)

    def blocklist_link(self) -> str:
        """Link to the acting user's profile page, where their block list is managed."""
        return f"{settings.API_BASE_URL}/u/{self.interaction.user.id}"

    async def block(self, target: discord.User | discord.Member) -> None:
        await self.execute(target, ActionType.BLOCK)

    async def unblock(self, target: discord.User | discord.Member) -> None:
        await self.execute(target, ActionType.UNBLOCK)

    async def blocked(self) -> None:
        locale = user_locale(self.interaction)
        await safe_send_channel(
            self.interaction,
            t("block.manage_message", locale=locale, link=self.blocklist_link()),
            ephemeral=True,
        )
