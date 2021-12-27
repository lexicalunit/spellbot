import logging
from typing import Optional, Union, cast

import discord
from ddtrace import tracer
from discord.errors import DiscordException
from discord_slash.context import ComponentContext, InteractionContext

from .metrics import add_span_error
from .utils import (
    CANT_SEND_CODE,
    DiscordChannel,
    bot_can_delete_channel,
    bot_can_read,
    bot_can_reply_to,
    bot_can_role,
    log_warning,
    suppress,
)

logger = logging.getLogger(__name__)
bad_users: set[int] = set()


@tracer.wrap()
async def safe_fetch_user(
    client: discord.Client,
    user_xid: int,
) -> Optional[discord.User]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": user_xid})

    user: Optional[discord.User]
    if user := client.get_user(user_xid):
        return user

    with suppress(
        DiscordException,
        log="could not fetch user %(user_xid)s",
        user_xid=user_xid,
    ):
        user = await client.fetch_user(user_xid)
    return user


@tracer.wrap()
async def safe_fetch_guild(
    client: discord.Client,
    guild_xid: int,
) -> Optional[discord.Guild]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xid": guild_xid})

    guild: Optional[discord.Guild]
    if guild := client.get_guild(guild_xid):
        return guild

    with suppress(
        DiscordException,
        log="could not fetch guild %(guild_xid)s",
        guild_xid=guild_xid,
    ):
        guild = await client.fetch_guild(guild_xid)
    return guild


@tracer.wrap()
async def safe_fetch_text_channel(
    client: discord.Client,
    guild_xid: int,
    channel_xid: int,
) -> Optional[discord.TextChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xids": guild_xid, "channel_xid": channel_xid})

    # first check our channel cache
    channel: Optional[DiscordChannel]
    if channel := client.get_channel(channel_xid):
        if not isinstance(channel, discord.TextChannel):
            return None
        return channel

    # fallback to hitting the Discord API
    with suppress(
        DiscordException,
        log="in guild %(guild_xid)s, could not fetch channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    ):
        fetched = await client.fetch_channel(channel_xid)
        if isinstance(fetched, discord.TextChannel):
            return fetched

    # failed to find in cache or via the API
    return None


@tracer.wrap()
def safe_get_partial_message(
    channel: DiscordChannel,
    guild_xid: int,
    message_xid: int,
) -> Optional[discord.PartialMessage]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xids": guild_xid, "message_xid": message_xid})

    if (
        not hasattr(channel, "type")
        or getattr(channel, "type") != discord.ChannelType.text
    ):
        return None

    if not bot_can_read(channel):
        return None

    message: Optional[discord.PartialMessage] = None
    text_channel = cast(discord.TextChannel, channel)
    with suppress(
        DiscordException,
        log="in guild %(guild_xid)s, could not get partial message %(message_xid)s",
        guild_xid=guild_xid,
        message_xid=message_xid,
    ):
        message = text_channel.get_partial_message(message_xid)
    return message


@tracer.wrap()
async def safe_update_embed(
    message: Union[discord.Message, discord.PartialMessage],
    *args,
    **kwargs,
) -> None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"messsage_xid": message.id})

    with suppress(
        DiscordException,
        log="could not update embed in message %(message_xid)s",
        message_xid=message.id,
    ):
        await message.edit(*args, **kwargs)


@tracer.wrap()
async def safe_update_embed_origin(ctx: ComponentContext, *args, **kwargs) -> bool:
    assert hasattr(ctx, "origin_message_id")

    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"origin_messsage_xid": ctx.origin_message_id})

    success: bool = False
    with suppress(
        DiscordException,
        log="could not update origin embed in message %(message_xid)s",
        message_xid=ctx.origin_message_id,
    ):
        await ctx.edit_origin(*args, **kwargs)
        success = True
    return success


@tracer.wrap()
async def safe_create_category_channel(
    client: discord.Client,
    guild_xid: int,
    name: str,
) -> Optional[discord.CategoryChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xids": guild_xid, "name": name})

    guild: Optional[discord.Guild]
    if not (guild := await safe_fetch_guild(client, guild_xid)):
        return None

    channel: Optional[discord.CategoryChannel] = None
    with suppress(
        DiscordException,
        log="in guild %(guild_xid)s, could not create category channel",
        guild_xid=guild_xid,
    ):
        channel = await guild.create_category_channel(name)
    return channel


@tracer.wrap()
async def safe_create_voice_channel(
    client: discord.Client,
    guild_xid: int,
    name: str,
    category: Optional[discord.CategoryChannel] = None,
) -> Optional[discord.VoiceChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xids": guild_xid, "name": name})

    guild: Optional[discord.Guild]
    if not (guild := await safe_fetch_guild(client, guild_xid)):
        return None

    channel: Optional[discord.VoiceChannel] = None
    with suppress(
        DiscordException,
        log="in guild %(guild_xid)s, could not create voice channel",
        guild_xid=guild_xid,
    ):
        channel = await guild.create_voice_channel(name, category=category)
    return channel


@tracer.wrap()
async def safe_ensure_voice_category(
    client: discord.Client,
    guild_xid: int,
    prefix: str,
) -> Optional[discord.CategoryChannel]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xids": guild_xid, "prefix": prefix})

    guild: Optional[discord.Guild]
    if not (guild := await safe_fetch_guild(client, guild_xid)):
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

    return await safe_create_category_channel(
        client,
        guild_xid,
        category_name(len(full)),
    )


@tracer.wrap()
async def safe_create_invite(
    channel: discord.VoiceChannel,
    guild_xid: int,
    max_age: int = 0,
) -> Optional[str]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xids": guild_xid, "channel_xid": channel.id})

    invite: Optional[str] = None
    with suppress(
        DiscordException,
        log="int guild %(guild_xid)s, could create invite for channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel.id,
    ):
        discord_invite = await channel.create_invite(max_age=max_age)
        invite = str(discord_invite.url)
    return invite


@tracer.wrap()
async def safe_delete_channel(
    channel: discord.abc.GuildChannel,
    guild_xid: int,
) -> bool:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tag("guild_xid", guild_xid)

    if not bot_can_delete_channel(channel):
        return False

    if not hasattr(channel, "id"):
        return False

    channel_xid: int = getattr(channel, "id")
    if span:  # pragma: no cover
        span.set_tag("channel_xid", channel_xid)

    success = False
    with suppress(
        DiscordException,
        log="in guild %(guild_xid)s, could not delete channel %(channel_xid)s",
        guild_xid=guild_xid,
        channel_xid=channel_xid,
    ):
        await channel.delete()
        success = True
    return success


@tracer.wrap()
async def safe_send_channel(
    ctx: InteractionContext,
    *args,
    **kwargs,
) -> Optional[discord.Message]:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"guild_xids": ctx.guild_id, "channel_xid": ctx.channel_id})

    message: Optional[discord.Message] = None
    with suppress(
        DiscordException,
        log="in guild %(guild_xid)s, could not send message to channel %(channel_xid)s",
        guild_xid=ctx.guild_id,
        channel_xid=ctx.channel_id,
    ):
        message = await ctx.send(*args, **kwargs)
    return message


@tracer.wrap()
async def safe_message_reply(message: discord.Message, *args, **kwargs) -> None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"messsage_xid": message.id})

    if not bot_can_reply_to(message):
        return

    try:
        await message.reply(*args, **kwargs)
    except Exception as ex:
        add_span_error(ex)
        logger.debug("debug: %s", ex, exc_info=True)


@tracer.wrap()
async def safe_send_user(
    user: Union[discord.User, discord.Member],
    *args,
    **kwargs,
) -> None:
    user_xid = getattr(user, "id", None)
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags({"user_xid": user_xid})

    if user_xid in bad_users:
        return log_warning("not sending to bad user %(user)s", user=user)

    if not hasattr(user, "send"):
        return log_warning("no send method on user %(user)s", user=user)

    try:
        await user.send(*args, **kwargs)
    except discord.errors.DiscordServerError as ex:
        add_span_error(ex)
        log_warning(
            "discord server error sending to user %(user)s",
            user=user,
            exec_info=True,
        )
    except discord.errors.InvalidArgument as ex:
        add_span_error(ex)
        log_warning(
            "could not send message to user %(user)s",
            user=user,
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
            return log_warning(
                "not allowed to send message to %(user)s",
                user=user,
                exec_info=True,
            )
        log_warning(
            "failed to send message to user %(user)s",
            user=user,
            exec_info=True,
        )


@tracer.wrap()
async def safe_add_role(
    user_or_member: Union[discord.User, discord.Member],
    guild: discord.Guild,
    role: str,
) -> None:
    if span := tracer.current_span():  # pragma: no cover
        span.set_tags(
            {
                "user_xid": getattr(user_or_member, "id", None),
                "guild_xid": guild.id,
                "role": role,
            },
        )

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
                "warning: in guild %s, could not add role: could not find member: %s",
                guild.id,
                str(user_or_member),
            )
            return
        discord_role = discord.utils.find(lambda m: m.name == role, guild.roles)
        if not discord_role:
            logger.warning(
                "warning: in guild %s, could not add role: could not find role: %s",
                guild.id,
                str(role),
            )
            return
        if not bot_can_role(guild):
            logger.warning(
                (
                    "warning: in guild %s, could not add role: "
                    "no permissions to add role: %s"
                ),
                guild.id,
                str(role),
            )
            return
        await member.add_roles(discord_role)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
    ) as ex:
        add_span_error(ex)
        logger.exception(
            "warning: in guild %s, could not add role to member %s: %s",
            guild.id,
            str(user_or_member),
            ex,
            exc_info=True,
        )
