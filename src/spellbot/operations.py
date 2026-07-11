from __future__ import annotations

import logging
import random
from asyncio import sleep
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import discord
from aiohttp.client_exceptions import ClientOSError
from ddtrace.trace import tracer
from discord.errors import DiscordException, NotFound
from discord.utils import MISSING

from .dm_limiter import DMKind, try_consume_dm_slot
from .metrics import add_span_error
from .utils import (
    ALREADY_ACKNOWLEDGED_CODE,
    CANT_SEND_CODE,
    MISSING_ACCESS_CODE,
    NO_MUTUAL_GUILDS_CODE,
    UNKNOWN_INTERACTION_CODE,
    UNKNOWN_MESSAGE_CODE,
    bot_can_delete_channel,
    bot_can_delete_message,
    bot_can_manage_channels,
    bot_can_read,
    bot_can_read_messages,
    bot_can_role,
    bot_can_send_messages,
    log_info,
    log_warning,
)

# Error code that are due to user configuration issues that we can't work around.
EXPECTED_DM_FAILURE_CODES = frozenset({CANT_SEND_CODE, NO_MUTUAL_GUILDS_CODE})

# Common set of exceptions we suppress during Discord API operations.
DISCORD_OP_EXCEPTIONS = (DiscordException, ClientOSError, NotFound)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from discord.abc import MessageableChannel

logger = logging.getLogger(__name__)


def is_discord_server_error(ex: BaseException) -> bool:
    """Check if this is a Discord server error (503, etc.) - transient infrastructure issue."""
    return isinstance(ex, discord.errors.DiscordServerError)


def ignore_exception_on_all_spans(ex: Exception, warning_type: str | None = None) -> None:
    """
    Ignore an exception on the current span and all parent spans.

    This prevents the exception from being marked as an error in any span in the trace.
    Optionally sets warning tags if warning_type is provided.
    """
    span = tracer.current_span()
    exception_type = type(ex)
    while span is not None:
        span._ignore_exception(exception_type)  # noqa: SLF001
        if warning_type is not None:
            span.set_tags(
                {
                    "warning": "true",
                    "warning.type": warning_type,
                    "warning.code": str(getattr(ex, "code", getattr(ex, "status", ""))),
                },
            )
        span = span._parent  # noqa: SLF001


@tracer.wrap()
async def retry(
    func: Callable[[], Awaitable[Any]],
    ignore_error: Callable[[BaseException], bool] | None = None,
) -> Any:
    times = 0
    while True:
        try:
            times += 1
            return await func()
        except ClientOSError:
            if times > 3:
                raise
            await sleep(times / 100)  # 10ms, 20ms, 30ms, etc.
        except Exception as ex:
            # Always ignore Discord server errors (503s) - transient infrastructure issues
            if is_discord_server_error(ex):
                ignore_exception_on_all_spans(ex, warning_type="discord_server_error")
            # Also ignore any caller-specified errors
            elif ignore_error is not None and ignore_error(ex):
                ignore_exception_on_all_spans(ex)
            raise


@dataclass
class ExpectedError:
    """Describes an expected error condition and how to handle it."""

    check: Callable[[BaseException], bool]
    warning_type: str
    log_msg: str


async def safe_call(
    func: Callable[[], Awaitable[Any]],
    log_msg: str,
    **log_kwargs: Any,
) -> Any:
    """
    Execute a Discord API call with standard error suppression and logging.

    Returns None if the call fails with an expected Discord error.
    """
    try:
        return await retry(func)
    except DISCORD_OP_EXCEPTIONS as ex:
        add_span_error(ex)
        log_warning(log_msg, exc_info=True, **log_kwargs)
        return None


async def safe_call_with_expected(
    func: Callable[[], Awaitable[Any]],
    expected_errors: list[ExpectedError],
    error_log_msg: str,
    **log_kwargs: Any,
) -> tuple[bool, Any]:
    """
    Execute a Discord API call with specific expected error handling.

    Args:
        func: The async function to call
        expected_errors: List of expected error conditions that should be treated as warnings
        error_log_msg: Log message for unexpected errors
        **log_kwargs: Keyword arguments for log messages

    Returns:
        (success, result) tuple. success is True if call completed without error.

    """

    def ignore_error(ex: BaseException) -> bool:
        return any(e.check(ex) for e in expected_errors)

    try:
        result = await retry(func, ignore_error=ignore_error)
    except DISCORD_OP_EXCEPTIONS as ex:
        for expected in expected_errors:
            if expected.check(ex):
                set_warning_tags(expected.warning_type, ex)
                log_info(expected.log_msg, **log_kwargs)
                return False, None
        add_span_error(ex)
        log_warning(error_log_msg, **log_kwargs)
        return False, None
    else:
        return True, result


@tracer.wrap()
async def safe_original_response(
    interaction: discord.Interaction,
) -> discord.InteractionMessage | None:
    _, result = await safe_call_with_expected(
        interaction.original_response,
        [
            ExpectedError(
                is_unknown_message,
                "unknown_message",
                "unknown message fetching original response for user %(user_xid)s (deleted)",
            ),
        ],
        "could not fetch original response for user %(user_xid)s",
        user_xid=interaction.user.id,
    )
    return result


def is_unknown_interaction(ex: BaseException) -> bool:
    return isinstance(ex, NotFound) and getattr(ex, "code", None) == UNKNOWN_INTERACTION_CODE


def is_already_acknowledged(ex: BaseException) -> bool:
    return (
        isinstance(ex, discord.errors.HTTPException)
        and getattr(ex, "code", None) == ALREADY_ACKNOWLEDGED_CODE
    )


def set_warning_tags(warning_type: str, ex: BaseException) -> None:
    """Set warning tags on the current span for expected errors."""
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags(
            {
                "warning": "true",
                "warning.type": warning_type,
                "warning.code": str(getattr(ex, "code", "")),
            },
        )


@tracer.wrap()
async def safe_defer_interaction(interaction: discord.Interaction) -> bool:
    success, _ = await safe_call_with_expected(
        interaction.response.defer,
        [
            ExpectedError(
                is_unknown_interaction,
                "unknown_interaction",
                "unknown interaction for user %(user_xid)s (token expired)",
            ),
            ExpectedError(
                is_already_acknowledged,
                "already_acknowledged",
                "interaction already acknowledged for user %(user_xid)s",
            ),
        ],
        "could not defer interaction for user %(user_xid)s",
        user_xid=interaction.user.id,
    )
    return success


@tracer.wrap()
async def safe_fetch_user(
    client: discord.Client,
    user_xid: int,
) -> discord.User | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": str(user_xid)})

    if user := client.get_user(user_xid):
        return user

    return await safe_call(
        lambda: client.fetch_user(user_xid),
        "could not fetch user %(user_xid)s",
        user_xid=user_xid,
    )


@tracer.wrap()
async def safe_fetch_guild(
    client: discord.Client,
    guild_xid: int,
) -> discord.Guild | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid)})

    if guild := client.get_guild(guild_xid):
        return guild

    return await safe_call(
        lambda: client.fetch_guild(guild_xid),
        "could not fetch guild %(guild_xid)s",
        guild_xid=guild_xid,
    )


@tracer.wrap()
async def safe_fetch_text_channel(
    client: discord.Client,
    guild_xid: int,
    channel_xid: int,
) -> discord.TextChannel | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "channel_xid": str(channel_xid)})

    if got := client.get_channel(channel_xid):
        if not isinstance(got, discord.TextChannel):
            return None
        return got

    if not (guild := await safe_fetch_guild(client, guild_xid)):
        return None

    if not bot_can_read_messages(guild):
        logger.warning("in guild %s, no permissions to read messages", guild_xid)
        return None

    fetched = await safe_call(
        lambda: client.fetch_channel(channel_xid),
        "in guild %(guild_xid)s, could not fetch channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    )
    return fetched if isinstance(fetched, discord.TextChannel) else None


@tracer.wrap()
def safe_get_partial_message(
    channel: MessageableChannel,
    guild_xid: int,
    message_xid: int,
) -> discord.PartialMessage | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "message_xid": str(message_xid)})

    if not hasattr(channel, "type") or channel.type != discord.ChannelType.text:
        return None

    if not bot_can_read(channel):
        return None

    # Note: get_partial_message is synchronous and doesn't actually make API calls,
    # so it won't raise Discord errors. We keep this simple.
    text_channel = cast("discord.TextChannel", channel)
    return text_channel.get_partial_message(message_xid)


def is_unknown_message(ex: BaseException) -> bool:
    return isinstance(ex, NotFound) and getattr(ex, "code", None) == UNKNOWN_MESSAGE_CODE


@tracer.wrap()
async def safe_update_embed(
    message: discord.Message | discord.PartialMessage,
    *args: Any,
    **kwargs: Any,
) -> discord.Message | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"message_xid": str(message.id)})

    _, result = await safe_call_with_expected(
        lambda: message.edit(*args, **kwargs),
        [
            ExpectedError(
                is_unknown_message,
                "unknown_message",
                "unknown message %(message_xid)s (already deleted)",
            ),
        ],
        "could not update embed in message %(message_xid)s",
        message_xid=message.id,
    )
    return result


def is_missing_access(ex: BaseException) -> bool:
    return (
        isinstance(ex, discord.errors.Forbidden)
        and getattr(ex, "code", None) == MISSING_ACCESS_CODE
    )


@tracer.wrap()
async def safe_delete_message(message: discord.Message | discord.PartialMessage) -> bool:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"message_xid": str(message.id)})

    if not bot_can_delete_message(message):
        maybe_guild = getattr(message, "guild", None)
        maybe_guild_xid = getattr(maybe_guild, "id", None)
        logger.warning(
            "warning: in guild %s (%s), could not manage message: no permissions: %s",
            maybe_guild,
            maybe_guild_xid,
            str(message),
        )
        return False

    success, _ = await safe_call_with_expected(
        message.delete,
        [
            ExpectedError(
                is_missing_access,
                "missing_access",
                "missing access to delete message %(message_xid)s",
            ),
            ExpectedError(
                is_unknown_message,
                "unknown_message",
                "unknown message %(message_xid)s (already deleted)",
            ),
        ],
        "could not delete message %(message_xid)s",
        message_xid=message.id,
    )
    return success


@tracer.wrap()
async def safe_update_embed_origin(
    interaction: discord.Interaction,
    *args: Any,
    **kwargs: Any,
) -> bool:
    assert hasattr(interaction, "message")
    assert interaction.message

    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"interaction.message.id": str(interaction.message.id)})

    result = await safe_call(
        lambda: interaction.edit_original_response(*args, **kwargs),
        "could not update origin embed in message %(message_xid)s",
        message_xid=interaction.message.id,
    )
    return result is not None


@tracer.wrap()
async def safe_create_category_channel(
    client: discord.Client,
    guild_xid: int,
    name: str,
) -> discord.CategoryChannel | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "name": name})

    guild: discord.Guild | None
    if not (guild := await retry(lambda: safe_fetch_guild(client, guild_xid))):
        return None

    if not bot_can_manage_channels(guild):
        return None

    return await safe_call(
        lambda: guild.create_category_channel(name),
        "in guild %(guild_xid)s, could not create category channel",
        guild_xid=guild_xid,
    )


@tracer.wrap()
async def safe_create_voice_channel(
    client: discord.Client,
    guild_xid: int,
    name: str,
    *,
    category: discord.CategoryChannel | None = None,
    use_max_bitrate: bool = False,
) -> discord.VoiceChannel | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "name": name})

    guild: discord.Guild | None
    if not (guild := await retry(lambda: safe_fetch_guild(client, guild_xid))):
        return None

    return await safe_call(
        lambda: guild.create_voice_channel(
            name,
            category=category,
            bitrate=int(guild.bitrate_limit) if use_max_bitrate else MISSING,
        ),
        "in guild %(guild_xid)s, could not create voice channel",
        guild_xid=guild_xid,
    )


@tracer.wrap()
async def safe_ensure_voice_category(  # noqa: C901
    client: discord.Client,
    guild_xid: int,
    prefix: str,
) -> discord.CategoryChannel | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "prefix": prefix})

    guild: discord.Guild | None
    if not (guild := await retry(lambda: safe_fetch_guild(client, guild_xid))):
        return None

    def category_num(cat: discord.CategoryChannel) -> int:
        try:
            offset = len(prefix) + 1
            return 0 if cat.name == prefix else int(cat.name[offset:]) - 1
        except ValueError:
            return -1

    def category_name(i: int) -> str:
        return prefix if i == 0 else f"{prefix} {i + 1}"

    available: discord.CategoryChannel | None = None
    full: list[discord.CategoryChannel] = []
    for i, cat in enumerate(
        sorted(
            (c for c in guild.categories if c.name.startswith(prefix)),
            key=category_num,
        ),
    ):
        cat_num = category_num(cat)
        if cat_num < 0:
            continue  # invalid category name, skip it
        if i != cat_num:
            break  # there's a missing category, we need to re-create it
        if len(cat.channels) < 50:
            available = cat
            break  # we found an available channel, use it
        full.append(cat)  # keep track of how many full channels there are

    if available:
        return available

    return await retry(
        lambda: safe_create_category_channel(
            client,
            guild_xid,
            category_name(len(full)),
        ),
    )


@tracer.wrap()
async def safe_delete_channel(
    channel: MessageableChannel,
    guild_xid: int,
) -> bool:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tag("guild_xid", str(guild_xid))

    if not bot_can_delete_channel(channel):
        return False

    if not hasattr(channel, "id"):
        return False

    if not hasattr(channel, "delete"):
        return False

    channel_xid: int = channel.id
    if span:  # pragma: no cover
        span.set_tag("channel_xid", str(channel_xid))

    result = await safe_call(
        channel.delete,  # type: ignore
        "in guild %(guild_xid)s, could not delete channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    )
    return result is not None


async def safe_send_and_get_message(
    send_func: Callable[[], Awaitable[Any]],
    response_func: Callable[[], Awaitable[discord.Message]],
    log_msg: str,
    **log_kwargs: Any,
) -> discord.Message | None:
    """Send a message and retrieve the message object, with error handling."""
    try:
        await retry(send_func)
        return await retry(response_func)
    except DISCORD_OP_EXCEPTIONS as ex:
        add_span_error(ex)
        log_warning(log_msg, exc_info=True, **log_kwargs)
        return None


@tracer.wrap()
async def safe_send_channel(
    interaction: discord.Interaction,
    *args: Any,
    **kwargs: Any,
) -> discord.Message | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags(
            {
                "guild_xid": str(interaction.guild_id),
                "channel_xid": str(interaction.channel_id),
            },
        )

    return await safe_send_and_get_message(
        lambda: interaction.response.send_message(*args, **kwargs),
        interaction.original_response,
        "in guild %(guild_xid)s, could not send message to channel %(channel_xid)s",
        guild_xid=interaction.guild_id,
        channel_xid=interaction.channel_id,
    )


@tracer.wrap()
async def safe_followup_channel(
    interaction: discord.Interaction,
    *args: Any,
    **kwargs: Any,
) -> discord.Message | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags(
            {
                "guild_xid": str(interaction.guild_id),
                "channel_xid": str(interaction.channel_id),
            },
        )

    # interaction.followup.send() requires that view be MISSING rather than None.
    if "view" in kwargs:
        view_hack = MISSING if kwargs["view"] is None else kwargs["view"]
        kwargs["view"] = view_hack

    if "content" in kwargs and kwargs["content"] is None:
        kwargs["content"] = MISSING
    kwargs["wait"] = True  # ensure that we get the message object back

    return await safe_call(
        lambda: interaction.followup.send(*args, **kwargs),
        "in guild %(guild_xid)s, could not send message to channel %(channel_xid)s",
        guild_xid=interaction.guild_id,
        channel_xid=interaction.channel_id,
    )


@tracer.wrap()
async def safe_channel_reply(
    channel: discord.TextChannel,
    *args: Any,
    **kwargs: Any,
) -> discord.Message | None:
    guild_xid = channel.guild.id
    channel_xid = channel.id
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "channel_xid": str(channel_xid)})
    if not bot_can_send_messages(channel):
        return log_info(
            "in guild %(guild_xid)s, could not reply to channel %(channel_xid)s",
            guild_xid=guild_xid,
            channel_xid=channel_xid,
        )
    return await safe_call(
        lambda: channel.send(*args, **kwargs),
        "in guild %(guild_xid)s, could not reply to channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    )


@tracer.wrap()
async def safe_create_channel_invite(
    channel: discord.abc.GuildChannel,
    *args: Any,
    **kwargs: Any,
) -> discord.Invite | None:
    guild_xid = channel.guild.id
    channel_xid = channel.id
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "channel_xid": str(channel_xid)})

    return await safe_call(
        lambda: channel.create_invite(*args, **kwargs),
        "in guild %(guild_xid)s, could not create invite to channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    )


def is_expected_dm_failure(ex: BaseException) -> bool:
    return (
        isinstance(ex, discord.errors.HTTPException)
        and getattr(ex, "code", None) in EXPECTED_DM_FAILURE_CODES
    )


@tracer.wrap()
async def safe_send_user(
    user: discord.User | discord.Member,
    *args: Any,
    kind: DMKind = "start",
    **kwargs: Any,
) -> None:
    user_xid = getattr(user, "id", None)
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": str(user_xid), "dm_kind": kind})

    if not hasattr(user, "send"):
        return log_warning("no send method on user %(user)s %(xid)s", user=user, xid=user_xid)

    if not await try_consume_dm_slot(kind):
        return log_info(
            "dm rate limit reached, skipping %(kind)s dm to %(user)s %(xid)s",
            kind=kind,
            user=user,
            xid=user_xid,
        )

    # Note: safe_send_user has special handling for DiscordServerError and DM failures
    # that differs from the standard safe_call pattern, so we handle it explicitly here.
    try:
        await retry(
            lambda: user.send(*args, **kwargs),
            ignore_error=is_expected_dm_failure,
        )
    except discord.errors.DiscordServerError as ex:
        # Discord server errors (5xx) are transient issues, not bot errors.
        set_warning_tags("discord_server_error", ex)
        log_warning(
            "discord server error sending to user %(user)s %(xid)s",
            user=user,
            xid=user_xid,
            exc_info=True,
        )
    except (discord.errors.Forbidden, discord.errors.HTTPException) as ex:
        if is_expected_dm_failure(ex):
            # User may have the bot blocked, DMs allowed only for friends, or
            # no mutual-guild visibility per their privacy settings.
            set_warning_tags("dm_delivery_blocked", ex)
            return log_info(
                "not allowed to send message to %(user)s %(xid)s",
                user=user,
                xid=user_xid,
            )
        add_span_error(ex)
        log_warning(
            "failed to send message to user %(user)s %(xid)s",
            user=user,
            xid=user_xid,
            exc_info=True,
        )
    except ClientOSError as ex:
        add_span_error(ex)
        log_warning(
            "client error sending to user %(user)s %(xid)s",
            user=user,
            xid=user_xid,
            exc_info=True,
        )


@tracer.wrap()
async def safe_add_role(
    user_or_member: discord.User | discord.Member,
    guild: discord.Guild,
    role: str,
    remove: bool | None = False,
) -> None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags(
            {
                "user_xid": str(getattr(user_or_member, "id", None)),
                "guild_xid": str(guild.id),
                "role": role,
                "remove": str(remove),
            },
        )

    if role == "@everyone":  # you can't assign the default role!
        return

    try:
        member = cast(
            "discord.Member | None",
            (
                user_or_member
                if hasattr(user_or_member, "roles")
                else guild.get_member(cast("discord.User", user_or_member).id)
            ),
        )
        if not member or not hasattr(member, "roles"):
            logger.warning(
                "warning: in guild %s (%s), could not manage role %s: could not find member: %s",
                guild.name,
                guild.id,
                str(role),
                str(user_or_member),
            )
            return
        discord_role = discord.utils.find(lambda m: m.name == role, guild.roles)
        if not discord_role:
            logger.warning(
                "warning: in guild %s (%s), could not manage role: could not find role: %s",
                guild.name,
                guild.id,
                str(role),
            )
            return
        if not bot_can_role(guild, discord_role):
            logger.warning(
                (
                    "warning: in guild %s (%s), could not manage role:"
                    " no permissions to manage role: %s"
                ),
                guild.name,
                guild.id,
                str(role),
            )
            return
        if remove:
            await retry(lambda: member.remove_roles(discord_role))
        else:
            await retry(lambda: member.add_roles(discord_role))
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
    ) as ex:
        add_span_error(ex)
        logger.exception(
            "warning: in guild %s (%s), could not add role to member %s",
            guild.name,
            guild.id,
            str(user_or_member),
        )


@dataclass
class VoiceChannelSuggestion:
    already_picked: int | None = None
    random_empty: int | None = None

    def get(self) -> int | None:
        return self.already_picked or self.random_empty


@tracer.wrap()
def safe_suggest_voice_channel(
    *,
    guild: discord.Guild | None,
    category: str,
    player_xids: list[int],
) -> VoiceChannelSuggestion:
    if guild is None:
        return VoiceChannelSuggestion()

    empty_channels = []
    random_empty = None
    already_picked = None
    for vc in guild.voice_channels:
        if not vc.category or not vc.category.name.lower().startswith(category.lower()):
            continue
        member_xids = {m.id for m in vc.members}
        if any(player_xid in member_xids for player_xid in player_xids):
            already_picked = vc.id
            break
        if not member_xids:
            empty_channels.append(vc.id)
    random_empty = random.choice(empty_channels) if empty_channels else None
    return VoiceChannelSuggestion(already_picked, random_empty)
