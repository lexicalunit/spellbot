from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Self

import discord

from spellbot import audit
from spellbot.operations import safe_channel_reply

from .base_action import BaseAction, action_session
from .leave_action import LeaveAction
from .lfg_action import LookingForGameAction

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from spellbot import SpellBot
    from spellbot.data import GameData

logger = logging.getLogger(__name__)


class WebActionMixin(BaseAction):
    """
    Drives a `BaseAction` from a website request instead of a Discord interaction.

    The Discord path answers the user through the interaction that triggered it. A
    website request has no interaction to answer, and the user is looking at a web page
    rather than at Discord, so text that would have gone back through the interaction is
    captured in `notices` for the web tier to render instead. Anything the *guild* needs
    to see — the game post itself, and warnings that mention other players — still goes
    to the Discord channel.

    Deliberately does not set `self.interaction`: any call site we failed to route
    through the accessors on `BaseAction` raises `AttributeError` rather than silently
    doing the wrong thing.
    """

    notices: list[str]
    game_id: int | None

    def __init__(
        self,
        bot: SpellBot,
        *,
        actor: discord.User | discord.Member,
        guild: discord.Guild,
        channel: discord.TextChannel,
        locale: str,
    ) -> None:
        self.bot = bot
        self.guild = guild
        self.channel = channel
        self.web_actor = actor
        self.web_locale = locale
        self.notices = []
        self.game_id = None

    @property
    def actor(self) -> discord.User | discord.Member:
        return self.web_actor

    @property
    def guild_xid(self) -> int | None:
        return self.guild.id if self.guild else None

    @property
    def origin_message(self) -> discord.Message | None:
        return None

    @property
    def locale(self) -> str:
        return self.web_locale

    @classmethod
    @asynccontextmanager
    async def create_for_web(
        cls,
        bot: SpellBot,
        *,
        actor: discord.User | discord.Member,
        guild: discord.Guild,
        channel: discord.TextChannel,
        locale: str,
        request_id: str,
    ) -> AsyncGenerator[Self]:
        action = cls(bot, actor=actor, guild=guild, channel=channel, locale=locale)
        async with action_session(action, request_id=request_id, source=audit.SOURCE_WEB):
            yield action

    def record(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        """Capture a message that would have gone back through a Discord interaction."""
        content = args[0] if args else kwargs.get("content")
        if isinstance(content, str) and content:
            self.notices.append(content)
            return
        embed = kwargs.get("embed")
        if isinstance(embed, discord.Embed):
            if text := embed.description:
                self.notices.append(text)
            elif embed.author and embed.author.name:
                self.notices.append(embed.author.name)

    async def reply(self, *args: Any, **kwargs: Any) -> discord.Message | None:
        self.record(args, kwargs)
        return None

    async def respond(self, *args: Any, **kwargs: Any) -> discord.Message | None:
        self.record(args, kwargs)
        return None

    async def update_origin(self, *args: Any, **kwargs: Any) -> bool:
        # There is no origin message, so `handle_embed_update` should always take the
        # fetch-the-channel path instead.
        return False

    async def origin_response(self) -> discord.InteractionMessage | None:
        return None


class WebLookingForGameAction(WebActionMixin, LookingForGameAction):
    """A `/lfg`-equivalent driven from the website."""

    async def handle_embed_creation(self, game_data: GameData, **kwargs: Any) -> GameData:
        # Every create and join path reaches here with the game it settled on, whether
        # that game is still pending or just filled up and started. Recording the id
        # here is what lets the website link the user straight to their game.
        self.game_id = game_data.id
        return await super().handle_embed_creation(game_data, **kwargs)

    async def notify_actor(self, *args: Any, **kwargs: Any) -> None:
        # The user is looking at the website, so show it there. DMing would surprise
        # them and would spend a slot from the DM budget that real game-details DMs
        # share (see `spellbot.dm_limiter`).
        self.record(args, kwargs)

    async def post_game_message(self, **kwargs: Any) -> discord.Message | None:
        # No interaction to follow up on. Returning None makes `create_initial_post`
        # fall through to posting directly into the channel.
        return None

    async def warn_channel(self, *args: Any, **kwargs: Any) -> discord.Message | None:
        # These warnings are about *other* players — "I could not DM <@x>", "I could not
        # give role Y to <@z>". Their audience is those players and the channel's
        # moderators, not the person on the website, so they must still be posted to
        # Discord. They are `t()`-rendered from server-side data, never user input.
        self.record(args, kwargs)
        if self.channel is None:  # pragma: no cover
            return None
        return await safe_channel_reply(self.channel, *args, **kwargs)


class WebLeaveAction(WebActionMixin, LeaveAction):
    """A `/leave`-equivalent driven from the website."""
