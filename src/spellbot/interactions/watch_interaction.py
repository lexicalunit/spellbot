import logging
from enum import Enum
from typing import Optional, Union

import discord
from discord.embeds import Embed
from discord_slash.context import InteractionContext
from pygicord import Config, Paginator

from .. import SpellBot
from ..operations import safe_send_channel
from ..services import WatchesService
from ..settings import Settings
from ..utils import EMBED_DESCRIPTION_SIZE_LIMIT, log_warning
from .base_interaction import BaseInteraction

logger = logging.getLogger(__name__)


class ActionType(Enum):
    WATCH = "watched"
    UNWATCH = "unwatched"


class WatchInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)

    async def execute(
        self,
        target: Union[discord.User, discord.Member],
        action: ActionType,
        note: Optional[str] = None,
    ):
        assert self.ctx
        await self.services.users.upsert(target)

        assert hasattr(target, "id")
        target_xid = target.id  # type: ignore

        if action is ActionType.UNWATCH:
            await self.services.users.unwatch(self.ctx.guild_id, target_xid)
            await safe_send_channel(
                self.ctx,
                f"No longer watching <@{target_xid}>.",
                hidden=True,
            )
        else:
            await self.services.users.watch(self.ctx.guild_id, target_xid, note=note)
            await safe_send_channel(self.ctx, f"Watching <@{target_xid}>.", hidden=True)

    async def watch(
        self,
        target: Union[discord.User, discord.Member],
        note: Optional[str] = None,
    ):
        await self.execute(target, ActionType.WATCH, note)

    async def unwatch(self, target: Union[discord.User, discord.Member]):
        await self.execute(target, ActionType.UNWATCH)

    async def get_watched_embeds(self) -> list[Embed]:
        assert self.ctx
        settings = Settings()

        def new_embed() -> Embed:
            assert self.ctx
            assert self.ctx.guild
            embed = Embed(title="List of watched players on this server")
            embed.set_thumbnail(url=settings.ICO_URL)
            embed.color = discord.Color(settings.EMBED_COLOR)
            return embed

        watches = WatchesService()
        entries = await watches.fetch(guild_xid=self.ctx.guild_id)

        embeds: list[Embed] = []
        embed = new_embed()
        description = ""
        for entry in entries:
            next_line = f"• <@{entry['user_xid']}> — {entry['note']}\n"
            if len(description) + len(next_line) >= EMBED_DESCRIPTION_SIZE_LIMIT:
                embed.description = description
                embeds.append(embed)
                embed = new_embed()
                description = ""
            description += next_line
        embed.description = description
        embeds.append(embed)

        n = len(embeds)
        if n > 1:
            for i, embed in enumerate(embeds, start=1):
                embed.set_footer(text=f"page {i} of {n}")

        return embeds

    async def watched(self):
        assert self.ctx
        embeds: list[Embed] = await self.get_watched_embeds()
        paginator = Paginator(pages=embeds, config=Config.MINIMAL)
        if len(embeds) > 1:
            try:
                await paginator.start(self.ctx)  # type: ignore
            except Exception as e:
                log_warning("pagination error: %(err)s", err=e, exec_info=True)
        else:
            await safe_send_channel(self.ctx, embed=embeds[0])
