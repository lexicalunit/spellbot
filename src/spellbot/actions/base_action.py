from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, NoReturn, Self, cast

from ddtrace.trace import tracer

from spellbot import audit, services
from spellbot.database import DatabaseSession, db_session_manager
from spellbot.errors import (
    GuildBannedError,
    SpellBotError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from spellbot.i18n import guild_locale, user_locale
from spellbot.metrics import add_span_request_id, setup_ignored_errors
from spellbot.utils import user_can_moderate

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import discord

    from spellbot import SpellBot
    from spellbot.data import ChannelData, GuildData, UserData

logger = logging.getLogger(__name__)


@asynccontextmanager
async def action_session(
    action: BaseAction,
    *,
    request_id: str,
    source: str,
) -> AsyncGenerator[None]:
    """
    Open the database session an action runs in and attribute its audited writes.

    Shared by every entry point (Discord interactions and website requests alike) so
    that session handling, tracing, and audit attribution can not drift between them.
    """
    with tracer.trace(name=f"spellbot.interactions.{type(action).__name__}.create") as span:
        setup_ignored_errors(span)
        add_span_request_id(request_id)
        async with db_session_manager():
            try:
                await action.upsert_request_objects()
                # Attribute any settings changes this action makes to the acting user. The
                # auto-upserts above are intentionally left outside this scope so they stay
                # unattributed. See spellbot.audit.
                with audit.actor(  # pragma: no branch
                    action.actor.id,
                    getattr(action.actor, "display_name", None),
                    source,
                ):
                    yield
            except Exception as ex:  # pragma: no cover
                await handle_exception(ex)


async def handle_exception(ex: Exception) -> NoReturn:
    if isinstance(ex, SpellBotError):
        raise ex
    logger.exception(
        "error: rolling back database session due to unhandled exception: %s: %s",
        ex.__class__.__name__,
        ex,
    )
    await DatabaseSession.rollback()
    raise ex


class BaseAction:
    bot: SpellBot
    # Only set on the Discord path. The website path (see `actions/web_action.py`)
    # deliberately leaves this unset so that any call site we failed to route through
    # the accessors below fails loudly instead of silently misbehaving.
    interaction: discord.Interaction
    guild: discord.Guild | None
    channel: discord.TextChannel | None
    channel_data: ChannelData
    guild_data: GuildData | None
    user_data: UserData | None

    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        self.bot = bot
        self.interaction = interaction
        self.guild = cast("discord.Guild", self.interaction.guild)
        self.channel = cast("discord.TextChannel", self.interaction.channel)

    # The four accessors below are the seam between "where this action came from" and
    # "what this action does". Subclasses driven by something other than a Discord
    # interaction override them; everything else in the action layer reads through them
    # rather than touching `self.interaction` directly.

    @property
    def actor(self) -> discord.User | discord.Member:
        """The user performing this action."""
        return self.interaction.user

    @property
    def guild_xid(self) -> int | None:
        """The external Discord ID of the guild this action targets."""
        return self.interaction.guild_id

    @property
    def origin_message(self) -> discord.Message | None:
        """The message this action was triggered from, when it came from a component."""
        return self.interaction.message

    @property
    def locale(self) -> str:
        """The acting user's preferred locale."""
        return user_locale(self.interaction)

    # Transport seams. These are declared here but *implemented in the subclass modules*
    # so that the `safe_*` names they call resolve through those modules' globals, which
    # is what `tests.mocks.mock_operations` patches.

    async def reply(self, *args: Any, **kwargs: Any) -> discord.Message | None:
        """Send a follow-up message in response to a deferred interaction."""
        raise NotImplementedError  # pragma: no cover

    async def respond(self, *args: Any, **kwargs: Any) -> discord.Message | None:
        """Send the initial response to an interaction that was not deferred."""
        raise NotImplementedError  # pragma: no cover

    async def update_origin(self, *args: Any, **kwargs: Any) -> bool:
        """Edit the message this action was triggered from."""
        raise NotImplementedError  # pragma: no cover

    async def origin_response(self) -> discord.InteractionMessage | None:
        """Fetch the message this action was triggered from, when there is one."""
        raise NotImplementedError  # pragma: no cover

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

        # Capture the user's locale from the request to store in the database.
        locale = self.locale
        guild_xid = self.guild.id if self.guild else None
        self.user_data = await services.users.upsert(
            self.actor,
            guild_xid=guild_xid,
            locale=locale,
        )

        if self.user_data.banned:
            raise UserBannedError

        if self.should_do_verification():
            await self.handle_verification()

    async def handle_verification(self) -> None:  # pragma: no cover
        if not self.guild:
            return
        verified: bool | None = None
        if self.channel_data.auto_verify:
            verified = True
        verify_data = await services.verifies.upsert(
            self.guild.id,
            self.actor.id,
            verified,
        )
        if not user_can_moderate(self.actor, self.guild, self.channel):
            if verify_data.verified and self.channel_data.unverified_only:
                raise UserVerifiedError
            if not verify_data.verified and self.channel_data.verified_only:
                raise UserUnverifiedError

    def should_do_verification(self) -> bool:
        return bool(self.guild and self.channel)

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        bot: SpellBot,
        interaction: discord.Interaction,
    ) -> AsyncGenerator[Self]:
        action = cls(bot, interaction)
        async with action_session(
            action,
            request_id=str(interaction.id),
            source=audit.SOURCE_DISCORD,
        ):
            yield action
