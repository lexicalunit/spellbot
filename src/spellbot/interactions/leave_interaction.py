import logging
from typing import cast

from ddtrace import tracer
from discord_slash.context import ComponentContext

from ..operations import (
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_send_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class LeaveInteraction(BaseInteraction):
    @tracer.wrap()
    async def _handle_click(self):
        assert self.ctx
        ctx: ComponentContext = cast(ComponentContext, self.ctx)

        if not (game_id := await self.services.users.current_game_id()):
            return await ctx.defer(ignore=True)

        found = await self.services.games.select(game_id)
        assert found

        game_data = await self.services.games.to_dict()
        if not (message_xid := game_data["message_xid"]):
            return await ctx.defer(ignore=True)

        if ctx.origin_message_id != message_xid:
            return await safe_send_channel(
                ctx,
                "You're not in that game. Use the /leave command to leave a game.",
                hidden=True,
            )

        await self.services.users.leave_game()
        embed = await self.services.games.to_embed()
        await safe_update_embed_origin(ctx, embed=embed)

    async def _removed(self):
        assert self.ctx
        await safe_send_channel(
            self.ctx,
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )

    @tracer.wrap()
    async def _handle_command(self):
        assert self.ctx

        if not (game_id := await self.services.users.current_game_id()):
            return await self._removed()

        found = await self.services.games.select(game_id)
        assert found

        await self.services.users.leave_game()

        game_data = await self.services.games.to_dict()
        chan_xid = game_data["channel_xid"]
        guild_xid = game_data["guild_xid"]

        if not (channel := await safe_fetch_text_channel(self.bot, guild_xid, chan_xid)):
            return await self._removed()
        if not (message_xid := game_data["message_xid"]):
            return await self._removed()
        if not (message := safe_get_partial_message(channel, guild_xid, message_xid)):
            return await self._removed()

        embed = await self.services.games.to_embed()
        await safe_update_embed(message, embed=embed)
        await self._removed()

    @tracer.wrap()
    async def execute(self, origin: bool = False):
        if origin:
            return await self._handle_click()
        return await self._handle_command()
