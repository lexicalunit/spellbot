# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer

from spellbot import services
from spellbot.enums import GameFormat
from spellbot.i18n import t
from spellbot.operations import (
    VoiceChannelSuggestion,
    safe_channel_reply,
    safe_fetch_text_channel,
    safe_followup_channel,
    safe_get_partial_message,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.views import BaseView, GameView

from .base_action import info_embed

if TYPE_CHECKING:
    from spellbot.data import GameData

    from .lfg_action import LookingForGameAction


class GamePosts:
    """Create and update a game's posts for a `LookingForGameAction`."""

    def __init__(self, action: LookingForGameAction) -> None:
        self.action = action

    @tracer.wrap()
    async def update_other_game_posts(self, other_game_ids: list[int]) -> None:
        """Update any other pending games to show that some players are no longer available."""
        for game_data in await services.games.get_many(other_game_ids):
            await self.action.refresh_game_posts(
                game_data,
                delete_if_empty=False,
                view=GameView(bot=self.action.bot, locale=game_data.locale),
            )

    @tracer.wrap()
    async def create_initial_post(
        self,
        game_data: GameData,
        embed: discord.Embed,
        view: BaseView | None = None,
        content: str | None = None,
    ) -> GameData:
        assert self.action.guild
        assert self.action.channel
        allowed_mentions = discord.AllowedMentions(everyone=True, users=False, roles=True)
        if message := await safe_followup_channel(
            self.action.interaction,
            content=content,
            embed=embed,
            view=view,
            allowed_mentions=allowed_mentions,
        ) or (
            message := await safe_channel_reply(
                self.action.channel,
                content=content,
                embed=embed,
                view=view,
                allowed_mentions=allowed_mentions,
            )
        ):
            return await services.games.add_post(
                game_data,
                self.action.guild.id,
                self.action.channel.id,
                message.id,
            )
        return game_data

    @tracer.wrap()
    async def handle_embed_creation(
        self,
        game_data: GameData,
        *,
        new: bool,
        origin: bool,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
        force_start: bool = False,
    ) -> GameData:
        assert self.action.guild
        assert self.action.channel

        # build the game post's embed and view:
        embed = self.action.game_embed(game_data, suggested_vc=suggested_vc, rematch=rematch)
        content = self.action.channel_data.extra

        view = (
            None
            if game_data.fully_seated
            else GameView(bot=self.action.bot, locale=game_data.locale)
        )
        if new:  # create the initial game post:
            return await self.create_initial_post(game_data, embed, view, content)

        # update the game post(s) for this game, which should already exist
        return await self.handle_embed_update(
            game_data,
            embed=embed,
            view=view,
            origin=origin,
            force_start=force_start,
        )

    @tracer.wrap()
    async def handle_embed_update(
        self,
        game_data: GameData,
        *,
        embed: discord.Embed,
        view: GameView | None,
        origin: bool = False,
        force_start: bool = False,
    ) -> GameData:
        assert self.action.guild
        assert self.action.channel

        for post in game_data.posts:
            message: discord.Message | discord.PartialMessage | None = None
            guild_xid = post.guild_xid
            channel_xid = post.channel_xid
            message_xid = post.message_xid

            channel: discord.TextChannel | None = None
            if self.action.guild.id == guild_xid and self.action.channel.id == channel_xid:
                # this post is for the current channel and guild
                channel = self.action.channel
            else:
                # the post is in a different channel/guild, so we need to fetch it
                channel = await safe_fetch_text_channel(self.action.bot, guild_xid, channel_xid)

            if channel is None:
                # failed for find the channel for this post
                continue

            # The post we're going to update here is the origin post:
            if (
                self.action.interaction.message
                and self.action.interaction.message.id == message_xid
            ):
                content = self.action.channel_data.extra
                if await safe_update_embed_origin(
                    self.action.interaction,
                    content=content,
                    embed=embed,
                    view=view,
                ):
                    # successfully updated the origin post
                    continue

            message = safe_get_partial_message(channel, guild_xid, message_xid)
            if not message:
                # failed to find the message for this post
                continue

            if not await safe_update_embed(message, embed=embed, view=view):
                # failed to update the message for this post
                continue

        if force_start or not origin:
            await self.reply_game_embed(game_data, started=force_start)

        return game_data

    @tracer.wrap()
    async def reply_game_embed(self, game_data: GameData, *, started: bool) -> None:
        """Point the user at the game they just joined (or force started)."""
        assert self.action.guild is not None
        locale = game_data.locale
        format = str(GameFormat(game_data.format))
        title_key = "lfg.started_game" if started else "lfg.found_game"
        if link := game_data.jump_links.get(self.action.guild.id):
            description = t("lfg.jump_to_game", locale=locale, link=link)
        elif started:
            description = t("lfg.game_started_id", locale=locale, game_id=game_data.id)
        else:
            description = t("lfg.joined_game", locale=locale, game_id=game_data.id)
        embed = info_embed(
            author=t(title_key, locale=locale, format=format),
            description=description,
        )
        await safe_followup_channel(self.action.interaction, embed=embed)
