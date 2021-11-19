import logging
from typing import cast

from discord_slash.context import ComponentContext

from ..operations import (
    safe_fetch_message,
    safe_fetch_text_channel,
    safe_send_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class LeaveInteraction(BaseInteraction):
    async def report_success(self):
        assert self.ctx
        await safe_send_channel(
            self.ctx,
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )

    async def execute(self, origin: bool = False):
        game_id = await self.services.users.current_game_id()
        if not game_id:
            return await self.report_success()

        await self.services.games.select(game_id)
        game_data = await self.services.games.to_dict()
        channel_xid = game_data["channel_xid"]
        guild_xid = game_data["guild_xid"]

        await self.services.users.leave_game()
        channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)

        if not channel:
            return await self.report_success()

        message_xid = game_data["message_xid"]
        if not message_xid:
            return await self.report_success()

        message = await safe_fetch_message(channel, guild_xid, message_xid)
        if not message:
            return await self.report_success()

        embed = await self.services.games.to_embed()

        if origin:
            # self.ctx should be a ComponentContext from a button click
            ctx: ComponentContext = cast(ComponentContext, self.ctx)
            if ctx.origin_message_id == message_xid:
                return await safe_update_embed_origin(ctx, embed=embed)
            return await self.report_success()

        await safe_update_embed(message, embed=embed)
        await self.report_success()
