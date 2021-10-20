import logging

from discord_slash.context import InteractionContext

from spellbot.client import SpellBot
from spellbot.interactions import BaseInteraction
from spellbot.operations import safe_send_channel
from spellbot.services.games import GamesService

logger = logging.getLogger(__name__)


class AdminInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)

    async def info(self, game_id: str):
        assert self.ctx
        games = GamesService()
        found = await games.select(game_id)
        if found:
            embed = await games.to_embed(dm=True)
            await safe_send_channel(
                self.ctx,
                embed=embed,
                hidden=True,
            )
        else:
            await safe_send_channel(
                self.ctx,
                "There is no game with that ID.",
                hidden=True,
            )
