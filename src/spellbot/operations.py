from __future__ import annotations

import logging
from asyncio import sleep
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, Union, cast

import discord
from aiohttp.client_exceptions import ClientOSError
from ddtrace import tracer
from discord.errors import DiscordException
from discord.utils import MISSING

from .metrics import add_span_error
from .utils import (
    CANT_SEND_CODE,
    bot_can_delete_channel,
    bot_can_manage_channels,
    bot_can_read,
    bot_can_reply_to,
    bot_can_role,
    log_info,
    log_warning,
    suppress,
)

if TYPE_CHECKING:
    from discord.abc import MessageableChannel, PrivateChannel
    from discord.guild import GuildChannel
    from discord.threads import Thread

    GetChannelReturnType = Optional[Union[GuildChannel, Thread, PrivateChannel]]

logger = logging.getLogger(__name__)
bad_users: set[int] = set()


@tracer.wrap()
async def retry(func: Callable[[], Awaitable[Any]]) -> Any:
    times = 0
    while True:
        try:
            times += 1
            return await func()
        except ClientOSError:
            if times > 3:
                raise
            await sleep(times / 100)  # 10ms, 20ms, 30ms, etc.


@tracer.wrap()
async def safe_original_response(
    interaction: discord.Interaction,
) -> Optional[discord.InteractionMessage]:
    response: Optional[discord.InteractionMessage] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="could fetch original response for user %(user_xid)s",
        user_xid=interaction.user.id,
    ):
        response = await retry(interaction.original_response)
    return response


@tracer.wrap()
async def safe_defer_interaction(interaction: discord.Interaction) -> None:
    with suppress(
        DiscordException,
        ClientOSError,
        log="could defer interaction for user %(user_xid)s",
        user_xid=interaction.user.id,
    ):
        await retry(interaction.response.defer)


@tracer.wrap()
async def safe_fetch_user(
    client: discord.Client,
    user_xid: int,
) -> Optional[discord.User]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": str(user_xid)})

    user: Optional[discord.User]
    if user := client.get_user(user_xid):
        return user

    with suppress(
        DiscordException,
        ClientOSError,
        log="could not fetch user %(user_xid)s",
        user_xid=user_xid,
    ):
        user = await retry(lambda: client.fetch_user(user_xid))
    return user


@tracer.wrap()
async def safe_fetch_guild(
    client: discord.Client,
    guild_xid: int,
) -> Optional[discord.Guild]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid)})

    guild: Optional[discord.Guild]
    if guild := client.get_guild(guild_xid):
        return guild

    with suppress(
        DiscordException,
        ClientOSError,
        log="could not fetch guild %(guild_xid)s",
        guild_xid=guild_xid,
    ):
        guild = await retry(lambda: client.fetch_guild(guild_xid))
    return guild


@tracer.wrap()
async def safe_fetch_text_channel(
    client: discord.Client,
    guild_xid: int,
    channel_xid: int,
) -> Optional[discord.TextChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "channel_xid": str(channel_xid)})

    if got := client.get_channel(channel_xid):
        if not isinstance(got, discord.TextChannel):
            return None
        return got

    channel: Optional[discord.TextChannel] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not fetch channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    ):
        fetched = await retry(lambda: client.fetch_channel(channel_xid))
        if isinstance(fetched, discord.TextChannel):
            channel = fetched

    return channel


@tracer.wrap()
def safe_get_partial_message(
    channel: MessageableChannel,
    guild_xid: int,
    message_xid: int,
) -> Optional[discord.PartialMessage]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "message_xid": str(message_xid)})

    if not hasattr(channel, "type") or getattr(channel, "type") != discord.ChannelType.text:
        return None

    if not bot_can_read(channel):
        return None

    message: Optional[discord.PartialMessage] = None
    text_channel = cast(discord.TextChannel, channel)
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not get partial message %(message_xid)s",
        guild_xid=guild_xid,
        message_xid=message_xid,
    ):
        message = text_channel.get_partial_message(message_xid)
    return message


@tracer.wrap()
async def safe_update_embed(
    message: Union[discord.Message, discord.PartialMessage],
    *args: Any,
    **kwargs: Any,
) -> Optional[discord.Message]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"message_xid": str(message.id)})

    updated_message: Optional[discord.Message] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="could not update embed in message %(message_xid)s",
        message_xid=message.id,
    ):
        try:
            updated_message = await retry(lambda: message.edit(*args, **kwargs))
        except discord.errors.NotFound:
            guild_xid = message.guild.id if message.guild else None
            logger.warning("in guild %s, unknown message %s", guild_xid, message.id)
    return updated_message


@tracer.wrap()
async def safe_delete_message(message: Union[discord.Message, discord.PartialMessage]) -> bool:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"message_xid": str(message.id)})

    success: bool = False
    with suppress(
        DiscordException,
        ClientOSError,
        log="could not delete message %(message_xid)s",
        message_xid=message.id,
    ):
        await retry(message.delete)
        success = True
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

    success: bool = False
    with suppress(
        DiscordException,
        ClientOSError,
        log="could not update origin embed in message %(message_xid)s",
        message_xid=interaction.message.id,
    ):
        await retry(lambda: interaction.edit_original_response(*args, **kwargs))
        success = True
    return success


@tracer.wrap()
async def safe_create_category_channel(
    client: discord.Client,
    guild_xid: int,
    name: str,
) -> Optional[discord.CategoryChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "name": name})

    guild: Optional[discord.Guild]
    if not (guild := await retry(lambda: safe_fetch_guild(client, guild_xid))):
        return None

    if not bot_can_manage_channels(guild):
        return None

    channel: Optional[discord.CategoryChannel] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not create category channel",
        guild_xid=guild_xid,
    ):
        channel = await retry(lambda: guild.create_category_channel(name))
    return channel


@tracer.wrap()
async def safe_create_voice_channel(
    client: discord.Client,
    guild_xid: int,
    name: str,
    category: Optional[discord.CategoryChannel] = None,
) -> Optional[discord.VoiceChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "name": name})

    guild: Optional[discord.Guild]
    if not (guild := await retry(lambda: safe_fetch_guild(client, guild_xid))):
        return None

    channel: Optional[discord.VoiceChannel] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not create voice channel",
        guild_xid=guild_xid,
    ):
        channel = await retry(lambda: guild.create_voice_channel(name, category=category))
    return channel


@tracer.wrap()
async def safe_ensure_voice_category(
    client: discord.Client,
    guild_xid: int,
    prefix: str,
) -> Optional[discord.CategoryChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "prefix": prefix})

    guild: Optional[discord.Guild]
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

    available: Optional[discord.CategoryChannel] = None
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
        span.set_tag("guild_xid", guild_xid)

    if not bot_can_delete_channel(channel):
        return False

    if not hasattr(channel, "id"):
        return False

    if not hasattr(channel, "delete"):
        return False

    channel_xid: int = getattr(channel, "id")
    if span:  # pragma: no cover
        span.set_tag("channel_xid", channel_xid)

    success = False
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not delete channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    ):
        try:
            await retry(channel.delete)  # type: ignore - this is asserted above
            success = True
        except discord.errors.NotFound:
            logger.warning("in guild  %s, unknown channel %s", guild_xid, channel_xid)
    return success


@tracer.wrap()
async def safe_send_channel(
    interaction: discord.Interaction,
    *args: Any,
    **kwargs: Any,
) -> Optional[discord.Message]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags(
            {
                "guild_xid": str(interaction.guild_id),
                "channel_xid": str(interaction.channel_id),
            },
        )

    message: Optional[discord.Message] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not send message to channel %(channel_xid)s",
        guild_xid=interaction.guild_id,
        channel_xid=interaction.channel_id,
    ):
        await retry(lambda: interaction.response.send_message(*args, **kwargs))
        message = await retry(interaction.original_response)
    return message


@tracer.wrap()
async def safe_followup_channel(
    interaction: discord.Interaction,
    *args: Any,
    **kwargs: Any,
) -> Optional[discord.Message]:
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

    message: Optional[discord.Message] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not send message to channel %(channel_xid)s",
        guild_xid=interaction.guild_id,
        channel_xid=interaction.channel_id,
    ):
        if "content" in kwargs and kwargs["content"] is None:
            kwargs["content"] = MISSING
        await retry(lambda: interaction.followup.send(*args, **kwargs))
        message = await retry(interaction.original_response)
    return message


@tracer.wrap()
async def safe_channel_reply(
    channel: discord.TextChannel,
    *args: Any,
    **kwargs: Any,
) -> Optional[discord.Message]:
    guild_xid = channel.guild.id
    channel_xid = channel.id
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "channel_xid": str(channel_xid)})

    message: Optional[discord.Message] = None
    with suppress(
        DiscordException,
        ClientOSError,
        log="in guild %(guild_xid)s, could not reply to channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    ):
        message = await retry(lambda: channel.send(*args, **kwargs))
    return message


@tracer.wrap()
async def safe_message_reply(message: discord.Message, *args: Any, **kwargs: Any) -> None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"message_xid": str(message.id)})

    if not bot_can_reply_to(message):
        return

    try:
        await retry(lambda: message.reply(*args, **kwargs))
    except Exception as ex:
        add_span_error(ex)
        logger.debug("debug: %s", ex, exc_info=True)


@tracer.wrap()
async def safe_send_user(
    user: Union[discord.User, discord.Member],
    *args: Any,
    **kwargs: Any,
) -> None:
    user_xid = getattr(user, "id", None)
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": str(user_xid)})

    if user_xid in bad_users:
        return log_warning("not sending to bad user %(user)s %(xid)s", user=user, xid=user_xid)

    if not hasattr(user, "send"):
        return log_warning("no send method on user %(user)s %(xid)s", user=user, xid=user_xid)

    try:
        await retry(lambda: user.send(*args, **kwargs))
    except discord.errors.DiscordServerError as ex:
        add_span_error(ex)
        log_warning(
            "discord server error sending to user %(user)s %(xid)s",
            user=user,
            xid=user_xid,
            exec_info=True,
        )
    except (discord.errors.Forbidden, discord.errors.HTTPException) as ex:
        add_span_error(ex)
        if isinstance(ex, discord.errors.Forbidden) or ex.code == CANT_SEND_CODE:
            # User may have the bot blocked or they may have DMs only allowed for friends.
            # Generally speaking, we can safely ignore this sort of error. However, too
            # many failed API requests can cause our bot to be flagged and rate limited.
            # It's not clear what can be done to avoid this, but we can maybe mitigate
            # by flagging the user until the next time we restart.
            if user_xid is not None:
                bad_users.add(user_xid)
            return log_info(
                "not allowed to send message to %(user)s %(xid)s",
                user=user,
                xid=user_xid,
            )
        log_warning(
            "failed to send message to user %(user)s %(xid)s",
            user=user,
            xid=user_xid,
            exec_info=True,
        )
    except ClientOSError as ex:
        add_span_error(ex)
        log_warning(
            "client error sending to user %(user)s %(xid)s",
            user=user,
            xid=user_xid,
            exec_info=True,
        )


@tracer.wrap()
async def safe_add_role(
    user_or_member: Union[discord.User, discord.Member],
    guild: discord.Guild,
    role: str,
    remove: Optional[bool] = False,
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
            Optional[discord.Member],
            (
                user_or_member
                if hasattr(user_or_member, "roles")
                else guild.get_member(cast(discord.User, user_or_member).id)
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
            "warning: in guild %s (%s), could not add role to member %s: %s",
            guild.name,
            guild.id,
            str(user_or_member),
            ex,
            exc_info=True,
        )
