from __future__ import annotations

import logging
from typing import Optional

from ..operations import (
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_send_channel,
    safe_update_embed,
)
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ConfigAction(BaseAction):
    async def power(self, level: Optional[int] = None) -> None:
        await self.services.configs.upsert(
            self.interaction.guild_id,
            self.interaction.user.id,
            level,
        )
        await safe_send_channel(self.interaction, f"Power level set to {level}.", ephemeral=True)
        await self._handle_update()

    async def _handle_update(self) -> None:
        if await self.services.users.is_waiting() and self.interaction.guild_id:
            game_id = await self.services.users.current_game_id()
            assert game_id

            found = await self.services.games.select(game_id)
            assert found

            data = await self.services.games.to_dict()
            bot = self.bot
            guild_xid = self.interaction.guild_id
            channel_xid = data["channel_xid"]
            message_xid = data["message_xid"]

            if not (chan := await safe_fetch_text_channel(bot, guild_xid, channel_xid)):
                return
            if not (message := safe_get_partial_message(chan, guild_xid, message_xid)):
                return

            embed = await self.services.games.to_embed()
            await safe_update_embed(message, embed=embed)
