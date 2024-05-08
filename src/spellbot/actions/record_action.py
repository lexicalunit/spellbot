from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace import tracer

from spellbot.operations import (
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_send_channel,
    safe_update_embed,
)
from spellbot.settings import settings

from .base_action import BaseAction

if TYPE_CHECKING:
    from collections.abc import ValuesView

    from spellbot import SpellBot
    from spellbot.models import GameDict, PlayDict

logger = logging.getLogger(__name__)


class RecordAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)

    async def _report_embed(self, game: GameDict, plays: ValuesView[PlayDict]) -> discord.Embed:
        assert self.guild is not None
        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name=f"SB{game['id']} Game Report")
        embed.color = settings.INFO_EMBED_COLOR
        description = ""
        for play in sorted(plays, key=lambda p: p["points"] or 0, reverse=True):
            confirmed_str = "✅ " if play["confirmed_at"] is not None else "❌ "
            points = play["points"]
            points_str = f"{points} points" if points is not None else "not reported"
            points_line = f"\n**ﾠ⮑ {confirmed_str}{points_str}**"
            description += f"• <@{play['user_xid']}>{points_line}\n"
        if any(play["confirmed_at"] is None for play in plays):
            description += (
                "\nPlease confirm points with `/confirm` when all players have reported.\n"
            )
        jump_links = game["jump_links"]
        jump_link = jump_links[self.guild.id]
        description += f"\n[Jump to game post]({jump_link})"
        embed.description = description
        return embed

    async def _update_posts(self, game: GameDict) -> None:
        for post in game["posts"]:
            guild_xid = post["guild_xid"]
            channel_xid = post["channel_xid"]
            message_xid = post["message_xid"]
            channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
            if channel:
                message = safe_get_partial_message(channel, guild_xid, message_xid)
                if message:
                    embed = await self.services.games.to_embed()
                    await safe_update_embed(message, embed=embed)

    @tracer.wrap()
    async def process(self, user_xid: int, points: int) -> None:
        game = await self.services.games.select_last_ranked_game(user_xid)
        if game is None:
            await safe_send_channel(self.interaction, "No game found.", ephemeral=True)
            return

        game_id = game["id"]
        plays = await self.services.games.get_plays()
        if plays.get(self.interaction.user.id, {}).get("confirmed_at", None):
            await safe_send_channel(
                self.interaction,
                f"You've already confirmed your points for game SB{game_id}.",
                ephemeral=True,
            )
            return

        # if at least one player has confirmed their points, then changing points not allowed
        if any(play["confirmed_at"] is not None for play in plays.values()):
            await safe_send_channel(
                self.interaction,
                (
                    f"Points for game SB{game_id} are locked in,"
                    " please confirm them or contact a mod."
                ),
                ephemeral=True,
            )
            return

        await self.services.games.add_points(user_xid, points)
        plays[user_xid]["points"] = points

        embed = await self._report_embed(game, plays.values())
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
        await self._update_posts(game)

    @tracer.wrap()
    async def loss(self) -> None:
        await self.process(self.interaction.user.id, 0)

    @tracer.wrap()
    async def win(self) -> None:
        await self.process(self.interaction.user.id, 3)

    @tracer.wrap()
    async def tie(self) -> None:
        await self.process(self.interaction.user.id, 1)

    @tracer.wrap()
    async def confirm(self) -> None:
        user_xid = self.interaction.user.id
        game = await self.services.games.select_last_ranked_game(user_xid)
        if game is None:
            await safe_send_channel(self.interaction, "No game found.", ephemeral=True)
            return
        plays = await self.services.games.get_plays()
        for play in plays.values():
            if play["points"] is None:
                embed = await self._report_embed(game, plays.values())
                await safe_send_channel(
                    self.interaction,
                    "You must wait until all players have reported their points.",
                    embed=embed,
                    ephemeral=True,
                )
                return
        confirmed_at = await self.services.games.confirm_points(user_xid)
        plays[user_xid]["confirmed_at"] = confirmed_at
        embed = await self._report_embed(game, plays.values())
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)
        await self._update_posts(game)
        if all(play["confirmed_at"] is not None for play in plays.values()):
            await self.services.games.update_records(plays)

    @tracer.wrap()
    async def check(self) -> None:
        user_xid = self.interaction.user.id
        game = await self.services.games.select_last_ranked_game(user_xid)
        if game is None:
            await safe_send_channel(self.interaction, "No game found.", ephemeral=True)
            return
        plays = await self.services.games.get_plays()
        embed = await self._report_embed(game, plays.values())
        await safe_send_channel(self.interaction, embed=embed, ephemeral=True)

    @tracer.wrap()
    async def elo(self) -> None:
        if not self.interaction.guild:
            await safe_send_channel(
                self.interaction,
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return
        if not self.interaction.channel:
            await safe_send_channel(
                self.interaction,
                "This command can only be used in a channel.",
                ephemeral=True,
            )
            return
        guild_xid = self.interaction.guild.id
        channel_xid = self.interaction.channel.id
        channel = await self.services.channels.select(channel_xid)
        if not channel or not channel["require_confirmation"] or not channel["show_points"]:
            await safe_send_channel(
                self.interaction,
                "ELO is not supported for this channel.",
                ephemeral=True,
            )
            return
        user_xid = self.interaction.user.id
        record = await self.services.games.get_record(guild_xid, channel_xid, user_xid)
        await safe_send_channel(self.interaction, f"Your ELO is {record['elo']}.", ephemeral=True)
