from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Union

import discord
from discord.embeds import Embed

from ..operations import safe_send_channel
from ..services import WatchesService
from ..settings import Settings
from ..utils import EMBED_DESCRIPTION_SIZE_LIMIT
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ActionType(Enum):
    WATCH = "watched"
    UNWATCH = "unwatched"


class WatchAction(BaseAction):
    async def execute(
        self,
        action: ActionType,
        target: Optional[Union[discord.User, discord.Member]] = None,
        id: Optional[int] = None,
        note: Optional[str] = None,
    ):
        if target:
            await self.services.users.upsert(target)

        target_xid: Optional[int] = None
        if target and hasattr(target, "id"):
            target_xid = target.id
        elif id:
            target_xid = id
        assert target_xid is not None

        if action is ActionType.UNWATCH:
            await self.services.users.unwatch(self.interaction.guild_id, target_xid)
            await safe_send_channel(
                self.interaction,
                f"No longer watching <@{target_xid}>.",
                ephemeral=True,
            )
        else:
            await self.services.users.watch(self.interaction.guild_id, target_xid, note=note)
            await safe_send_channel(self.interaction, f"Watching <@{target_xid}>.", ephemeral=True)

    async def watch(self, target: Union[discord.User, discord.Member], note: Optional[str] = None):
        await self.execute(ActionType.WATCH, target=target, note=note)

    async def unwatch(
        self,
        target: Optional[Union[discord.User, discord.Member]] = None,
        id: Optional[str] = None,
    ):
        if not target and not id:
            await safe_send_channel(
                self.interaction,
                "You must provide either a target User or their ID",
                ephemeral=True,
            )
            return

        xid: Optional[int] = None
        if id:
            try:
                xid = int(id)
            except ValueError:
                await safe_send_channel(
                    self.interaction,
                    "You must provide a valid integer for an ID",
                    ephemeral=True,
                )
                return

        await self.execute(ActionType.UNWATCH, target=target, id=xid)

    async def get_watched_embeds(self) -> list[Embed]:
        settings = Settings()

        def new_embed() -> Embed:
            assert self.interaction.guild
            embed = Embed(title="List of watched players on this server")
            embed.set_thumbnail(url=settings.ICO_URL)
            embed.color = discord.Color(settings.EMBED_COLOR)
            return embed

        watches = WatchesService()
        entries = await watches.fetch(guild_xid=self.interaction.guild_id)

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

    async def watched(self, page: int):
        embeds: list[Embed] = await self.get_watched_embeds()
        await safe_send_channel(self.interaction, embed=embeds[page - 1])
