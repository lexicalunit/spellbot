from __future__ import annotations

import logging
from enum import Enum

import discord
from discord.embeds import Embed

from spellbot import services
from spellbot.i18n import guild_locale, t, user_locale
from spellbot.operations import safe_send_channel
from spellbot.settings import settings
from spellbot.utils import EMBED_DESCRIPTION_SIZE_LIMIT

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class ActionType(Enum):
    WATCH = "watched"
    UNWATCH = "unwatched"


class WatchAction(BaseAction):
    async def execute(
        self,
        action: ActionType,
        target: discord.User | discord.Member | None = None,
        id: int | None = None,
        note: str | None = None,
    ) -> None:
        if target:
            await services.users.upsert(target)

        locale = user_locale(self.interaction)
        target_xid: int | None = None
        assert target is not None or id is not None
        if target and hasattr(target, "id"):
            target_xid = target.id
        else:
            assert id is not None
            target_xid = id
        assert target_xid is not None

        if action is ActionType.UNWATCH:
            assert self.interaction.guild_id is not None
            await services.users.unwatch(self.interaction.guild_id, target_xid)
            await safe_send_channel(
                self.interaction,
                t("watch_action.not_watching", locale=locale, user_id=target_xid),
                ephemeral=True,
            )
        else:
            assert self.interaction.guild_id is not None
            await services.users.watch(self.interaction.guild_id, target_xid, note=note)
            await safe_send_channel(
                self.interaction,
                t("watch_action.watching", locale=locale, user_id=target_xid),
                ephemeral=True,
            )

    async def watch(
        self,
        target: discord.User | discord.Member | None,
        id: str | None = None,
        note: str | None = None,
    ) -> None:
        locale = user_locale(self.interaction)
        if not target and not id:
            await safe_send_channel(
                self.interaction,
                t("watch_action.provide_target", locale=locale),
                ephemeral=True,
            )
            return

        xid: int | None = None
        if id:
            try:
                xid = int(id)
            except ValueError:
                await safe_send_channel(
                    self.interaction,
                    t("watch_action.invalid_id", locale=locale),
                    ephemeral=True,
                )
                return

        await self.execute(ActionType.WATCH, target=target, id=xid, note=note)

    async def unwatch(
        self,
        target: discord.User | discord.Member | None = None,
        id: str | None = None,
    ) -> None:
        locale = user_locale(self.interaction)
        if not target and not id:
            await safe_send_channel(
                self.interaction,
                t("watch_action.provide_target", locale=locale),
                ephemeral=True,
            )
            return

        xid: int | None = None
        if id:
            try:
                xid = int(id)
            except ValueError:
                await safe_send_channel(
                    self.interaction,
                    t("watch_action.invalid_id", locale=locale),
                    ephemeral=True,
                )
                return

        await self.execute(ActionType.UNWATCH, target=target, id=xid)

    async def get_watched_embeds(self) -> list[Embed]:
        locale = guild_locale(self.guild)

        def new_embed() -> Embed:
            assert self.interaction.guild
            embed = Embed(title=t("watch_action.list_title", locale=locale))
            embed.set_thumbnail(url=settings.ICO_URL)
            embed.color = discord.Color(settings.INFO_EMBED_COLOR)
            return embed

        assert self.interaction.guild_id is not None
        entries = await services.watches.fetch(guild_xid=self.interaction.guild_id)

        embeds: list[Embed] = []
        embed = new_embed()
        description = ""
        for entry in entries:
            next_line = f"• <@{entry.user_xid}> — {entry.note}\n"
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
                embed.set_footer(text=t("admin.page", locale=locale, current=i, total=n))

        return embeds

    async def watched(self, page: int) -> None:
        embeds: list[Embed] = await self.get_watched_embeds()
        await safe_send_channel(self.interaction, embed=embeds[page - 1])
