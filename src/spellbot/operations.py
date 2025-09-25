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
from redis import asyncio as aioredis

from .metrics import add_span_error
from .settings import settings
from .utils import (
    CANT_SEND_CODE,
    bot_can_delete_channel,
    bot_can_delete_message,
    bot_can_manage_channels,
    bot_can_read,
    bot_can_read_messages,
    bot_can_reply_to,
    bot_can_role,
    bot_can_send_messages,
    log_info,
    log_warning,
    suppress,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from discord.abc import MessageableChannel, PrivateChannel
    from discord.guild import GuildChannel
    from discord.threads import Thread

    GetChannelReturnType = GuildChannel | Thread | PrivateChannel | None

logger = logging.getLogger(__name__)
BAD_USER_EXPIRATION = 60 * 60 * 24  # 1 day


@tracer.wrap()
async def mark_bad_user(user_xid: int) -> None:
    if not settings.REDIS_URL:
        return

    redis = await aioredis.from_url(settings.REDIS_URL)
    key = f"bad_user:{user_xid}"

    try:
        redis.set(key, 1, ex=BAD_USER_EXPIRATION)
    except Exception:
        logger.warning("redis error bad user cache", exc_info=True)


@tracer.wrap()
async def is_bad_user(user_xid: int | str | None) -> bool:
    if not settings.REDIS_URL:
        return False
    if not user_xid:
        return False
    if isinstance(user_xid, str):
        try:
            user_xid = int(user_xid)
        except ValueError:
            return False

    redis = await aioredis.from_url(settings.REDIS_URL)
    key = f"bad_user:{user_xid}"

    try:
        return await redis.exists(key)
    except Exception:
        logger.warning("redis error bad user cache", exc_info=True)
    return False


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
) -> discord.InteractionMessage | None:
    response: discord.InteractionMessage | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="could fetch original response for user %(user_xid)s",
        user_xid=interaction.user.id,
    ):
        response = await retry(interaction.original_response)
    return response


@tracer.wrap()
async def safe_defer_interaction(interaction: discord.Interaction) -> bool:
    rvalue = False
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="could not defer interaction for user %(user_xid)s",
        user_xid=interaction.user.id,
    ):
        await retry(interaction.response.defer)
        rvalue = True
    return rvalue


@tracer.wrap()
async def safe_fetch_user(
    client: discord.Client,
    user_xid: int,
) -> discord.User | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": str(user_xid)})

    user: discord.User | None
    if user := client.get_user(user_xid):
        return user

    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="could not fetch user %(user_xid)s",
        user_xid=user_xid,
    ):
        user = await retry(lambda: client.fetch_user(user_xid))
    return user


@tracer.wrap()
async def safe_fetch_guild(
    client: discord.Client,
    guild_xid: int,
) -> discord.Guild | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid)})

    guild: discord.Guild | None
    if guild := client.get_guild(guild_xid):
        return guild

    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
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

    channel: discord.TextChannel | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
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
) -> discord.PartialMessage | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "message_xid": str(message_xid)})

    if not hasattr(channel, "type") or channel.type != discord.ChannelType.text:
        return None

    if not bot_can_read(channel):
        return None

    message: discord.PartialMessage | None = None
    text_channel = cast("discord.TextChannel", channel)
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="in guild %(guild_xid)s, could not get partial message %(message_xid)s",
        guild_xid=guild_xid,
        message_xid=message_xid,
    ):
        message = text_channel.get_partial_message(message_xid)
    return message


@tracer.wrap()
async def safe_update_embed(
    message: discord.Message | discord.PartialMessage,
    *args: Any,
    **kwargs: Any,
) -> discord.Message | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"message_xid": str(message.id)})

    updated_message: discord.Message | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="could not update embed in message %(message_xid)s",
        message_xid=message.id,
    ):
        updated_message = await retry(lambda: message.edit(*args, **kwargs))
    return updated_message


@tracer.wrap()
async def safe_delete_message(message: discord.Message | discord.PartialMessage) -> bool:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"message_xid": str(message.id)})

    if not bot_can_delete_message(message):
        maybe_guild = getattr(message, "guild", None)
        maybe_guild_xid = getattr(maybe_guild, "id", None)
        logger.warning(
            (
                "warning: in guild %s (%s), could not manage message:"
                " no permissions to manage message: %s"
            ),
            maybe_guild,
            maybe_guild_xid,
            str(message),
        )
        return False

    success: bool = False
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
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
        NotFound,
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
) -> discord.CategoryChannel | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "name": name})

    guild: discord.Guild | None
    if not (guild := await retry(lambda: safe_fetch_guild(client, guild_xid))):
        return None

    if not bot_can_manage_channels(guild):
        return None

    channel: discord.CategoryChannel | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
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
    *,
    category: discord.CategoryChannel | None = None,
    use_max_bitrate: bool = False,
) -> discord.VoiceChannel | None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": str(guild_xid), "name": name})

    guild: discord.Guild | None
    if not (guild := await retry(lambda: safe_fetch_guild(client, guild_xid))):
        return None

    channel: discord.VoiceChannel | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="in guild %(guild_xid)s, could not create voice channel",
        guild_xid=guild_xid,
    ):
        channel = await retry(
            lambda: guild.create_voice_channel(
                name,
                category=category,
                bitrate=int(guild.bitrate_limit) if use_max_bitrate else MISSING,
            ),
        )
    return channel


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
        span.set_tag("guild_xid", guild_xid)

    if not bot_can_delete_channel(channel):
        return False

    if not hasattr(channel, "id"):
        return False

    if not hasattr(channel, "delete"):
        return False

    channel_xid: int = channel.id
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
        await retry(channel.delete)  # type: ignore - this is asserted above
        success = True
    return success


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

    message: discord.Message | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
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

    message: discord.Message | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
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
    message: discord.Message | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="in guild %(guild_xid)s, could not reply to channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    ):
        message = await retry(lambda: channel.send(*args, **kwargs))
    return message


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

    invite: discord.Invite | None = None
    with suppress(
        DiscordException,
        ClientOSError,
        NotFound,
        log="in guild %(guild_xid)s, could not create invite to channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    ):
        invite = await retry(lambda: channel.create_invite(*args, **kwargs))
    return invite


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
    user: discord.User | discord.Member,
    *args: Any,
    **kwargs: Any,
) -> None:
    user_xid = getattr(user, "id", None)
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": str(user_xid)})

    if await is_bad_user(user_xid):
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
                await mark_bad_user(user_xid)
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
    random_empty = random.choice(empty_channels) if empty_channels else None  # noqa: S311
    return VoiceChannelSuggestion(already_picked, random_empty)
