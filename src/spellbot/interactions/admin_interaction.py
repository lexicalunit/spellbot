import logging

from discord_slash.context import InteractionContext

from .. import SpellBot
from ..operations import safe_send_channel
from ..services import GamesService
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class AdminInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)

    async def report_failure(self):
        assert self.ctx
        await safe_send_channel(self.ctx, "There is no game with that ID.", hidden=True)

    async def info(self, game_id: str):
        assert self.ctx

        numeric_filter = filter(str.isdigit, game_id)
        numeric_string = "".join(numeric_filter)
        if not numeric_string:
            return await self.report_failure()
        game_id_int = int(numeric_string)

        games = GamesService()
        found = await games.select(game_id_int)
        if not found:
            return await self.report_failure()

        embed = await games.to_embed(dm=True)
        await safe_send_channel(self.ctx, embed=embed, hidden=True)
