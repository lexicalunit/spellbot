# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import TYPE_CHECKING, Any, NoReturn, Self, cast

import discord
from ddtrace.trace import tracer

from spellbot import audit, services
from spellbot.database import DatabaseSession, db_session_manager
from spellbot.errors import GuildBannedError, SpellBotError, UserBannedError
from spellbot.i18n import guild_locale, t, user_locale
from spellbot.metrics import add_span_request_id, setup_ignored_errors
from spellbot.operations import (
    safe_delete_message,
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from spellbot import SpellBot
    from spellbot.data import ChannelData, GameData, GuildData, UserData
    from spellbot.views import GameView

logger = logging.getLogger(__name__)


def info_embed(
    *,
    title: str | None = None,
    author: str | None = None,
    description: str | None = None,
) -> discord.Embed:
    """Build an informational embed with SpellBot's thumbnail and color."""
    embed = discord.Embed(title=title, description=description, color=settings.INFO_EMBED_COLOR)
    embed.set_thumbnail(url=settings.ICO_URL)
    if author:
        embed.set_author(name=author)
    return embed


async def handle_exception(ex: Exception) -> NoReturn:
    if isinstance(ex, SpellBotError):
        raise ex
    # This is always called from an except handler, but not lexically inside one,
    # so pass exc_info explicitly rather than relying on logger.exception().
    logger.error(
        "error: rolling back database session due to unhandled exception: %s: %s",
        ex.__class__.__name__,
        ex,
        exc_info=ex,
    )
    await DatabaseSession.rollback()
    raise ex


def convoke_table_post(bot: SpellBot, game: GameData) -> dict[str, Any]:
    """
    Return the edit that hands a game's post over to its open Convoke table.

    SpellBot stops taking players for the game, so its buttons go, but the post keeps linking
    to the table so players can still join it on Convoke.
    """
    embed = replace(game, players=[]).to_embed(
        emojis=bot.emojis_cache,
        supporters=bot.supporters,
    )
    content = t("game.war_convoke_only", locale=game.locale)
    return {"content": content, "embed": embed, "view": None}


async def expire_games(
    bot: SpellBot,
    games: list[GameData],
    *,
    report: Callable[..., None] | None = None,
) -> None:
    """
    Expire inactive games: dequeue their players and clear up their posts.

    A post is deleted when nobody was queued or its channel deletes expired games, otherwise
    it is replaced with an "expired" notice. A Guild War game whose Convoke table is open was
    possibly played there, so its posts are handed over to the table instead.

    Progress is passed to `report` as translation keys with their parameters. Games are spaced
    out to stay under Discord's rate limits.
    """

    def note(key: str, **params: Any) -> None:
        if report is not None:
            report(key, **params)

    for count, game in enumerate(games, start=1):
        logger.info("expiring game %s...", game.id)
        note("admin.expire_game", game_id=game.id)
        dequeued = await services.games.delete_games([game.id])
        note("admin.expire_dequeued", count=dequeued)
        handoff = convoke_table_post(bot, game) if game.convoke_table_open else None
        for post in game.posts:
            channel = await safe_fetch_text_channel(bot, post.guild_xid, post.channel_xid)
            if not channel:
                note("admin.expire_no_channel", channel_id=post.channel_xid)
                continue
            message = safe_get_partial_message(channel, post.guild_xid, post.message_xid)
            if not message:
                note("admin.expire_no_message", message_id=post.message_xid)
                continue
            channel_data = await services.channels.select(post.channel_xid)
            if handoff is not None:
                note("admin.expire_updating", message_id=post.message_xid)
                done = await safe_update_embed(message, **handoff)
            elif not dequeued or (channel_data and channel_data.delete_expired):
                note("admin.expire_deleting", message_id=post.message_xid)
                done = await safe_delete_message(message, own_message=True)
            else:
                note("admin.expire_updating", message_id=post.message_xid)
                done = await safe_update_embed(
                    message,
                    content=t("admin.game_expired", locale=game.locale),
                    embed=None,
                    view=None,
                )
            if not done:
                note("admin.expire_no_permission")
            note("admin.expire_done")
        await asyncio.sleep(5 if count % 5 == 0 else 1)


class BaseAction:
    bot: SpellBot
    interaction: discord.Interaction
    member: discord.Member
    guild: discord.Guild | None
    channel: discord.TextChannel | None
    channel_data: ChannelData
    guild_data: GuildData | None
    user_data: UserData | None

    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        self.bot = bot
        self.interaction = interaction
        self.member = cast("discord.Member", self.interaction.user)
        self.guild = cast("discord.Guild", self.interaction.guild)
        self.channel = cast("discord.TextChannel", self.interaction.channel)

    async def upsert_request_objects(self) -> None:  # pragma: no cover
        self.guild_data: GuildData | None = None
        if self.guild:
            self.guild_data = await services.guilds.upsert(
                self.guild,
                locale=guild_locale(self.guild),
            )

        if self.guild_data and self.guild_data.banned:
            raise GuildBannedError

        if self.guild and self.channel:
            self.channel_data = await services.channels.upsert(self.channel)

        # Capture user's locale from the interaction to store in the database
        locale = user_locale(self.interaction)
        guild_xid = self.guild.id if self.guild else None
        self.user_data = await services.users.upsert(
            self.member,
            guild_xid=guild_xid,
            locale=locale,
        )

        if self.user_data.banned:
            raise UserBannedError

    def game_embed(self, game_data: GameData, **options: Any) -> discord.Embed:
        """Render the embed for a game post, decorated with the bot's emojis and supporters."""
        return game_data.to_embed(
            emojis=self.bot.emojis_cache,
            supporters=self.bot.supporters,
            **options,
        )

    async def refresh_game_posts(
        self,
        game_data: GameData,
        *,
        delete_if_empty: bool,
        view: GameView | None = None,
        origin_message_xid: int | None = None,
    ) -> None:
        """
        Re-render every post of a game, or delete them all (and the game) once it has no players.

        A Guild War game whose Convoke table is open keeps its posts when it empties: they're
        handed over to the table instead (see `convoke_table_post`).

        The post whose message is `origin_message_xid` is the one the user interacted with, so it
        is updated through the interaction response rather than edited directly. When `view` is
        None the posts keep whatever view they already have.
        """
        empty = delete_if_empty and not game_data.players
        # `None` deletes the posts.
        edit: dict[str, Any] | None
        if empty and game_data.convoke_table_open:
            edit = convoke_table_post(self.bot, game_data)
        elif empty:
            edit = None
        else:
            edit = {"embed": self.game_embed(game_data)} | ({} if view is None else {"view": view})
        for post in game_data.posts:
            if origin_message_xid is not None and post.message_xid == origin_message_xid:
                if edit is None:
                    assert self.interaction.message is not None
                    await safe_delete_message(self.interaction.message, own_message=True)
                else:
                    await safe_update_embed_origin(self.interaction, **edit)
                continue
            channel = await safe_fetch_text_channel(self.bot, post.guild_xid, post.channel_xid)
            if channel is None:
                continue
            message = safe_get_partial_message(channel, post.guild_xid, post.message_xid)
            if message is None:
                continue
            if edit is None:
                await safe_delete_message(message, own_message=True)
            else:
                await safe_update_embed(message, **edit)
        if empty:
            await services.games.delete_games([game_data.id])

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        bot: SpellBot,
        interaction: discord.Interaction,
    ) -> AsyncGenerator[Self]:
        action = cls(bot, interaction)
        with tracer.trace(name=f"spellbot.interactions.{cls.__name__}.create") as span:
            setup_ignored_errors(span)
            add_span_request_id(str(interaction.id))
            async with db_session_manager():
                try:
                    await action.upsert_request_objects()
                    # Attribute any settings changes this action makes to the acting user. The
                    # auto-upserts above are intentionally left outside this scope so they stay
                    # unattributed. See spellbot.audit.
                    with audit.actor(  # pragma: no branch
                        interaction.user.id,
                        getattr(interaction.user, "display_name", None),
                        audit.SOURCE_DISCORD,
                    ):
                        yield action
                except Exception as ex:  # pragma: no cover
                    await handle_exception(ex)
