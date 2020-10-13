import logging
from typing import Any, Optional, Union, cast

import discord

from spellbot.assets import s
from spellbot.constants import GREEN_CHECK, RED_X

logger = logging.getLogger(__name__)

ChannelType = Union[
    discord.CategoryChannel,
    discord.DMChannel,
    discord.GroupChannel,
    discord.StoreChannel,
    discord.TextChannel,
    discord.VoiceChannel,
]


def _user_or_guild_log_part(message: discord.Message) -> str:  # pragma: no cover
    if hasattr(message, "guild"):
        return f"guild {cast(Any, message.guild).id}"
    return "DM"


async def safe_remove_reaction(
    message: discord.Message, emoji: str, user: discord.User
) -> None:
    try:
        await message.remove_reaction(emoji, user)
    except discord.errors.Forbidden:
        await message.channel.send(s("reaction_permissions_required"))
    except (
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
        discord.errors.NotFound,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not remove reaction: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_clear_reactions(message: discord.Message) -> None:
    try:
        await message.clear_reactions()
    except discord.errors.Forbidden:
        await message.channel.send(s("reaction_permissions_required"))
    except discord.errors.HTTPException as e:
        logger.exception(
            "warning: discord (%s): could not clear reactions: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_react_ok(message: discord.Message) -> None:
    try:
        await message.add_reaction(GREEN_CHECK)
    except discord.errors.Forbidden:
        await message.channel.send(s("reaction_permissions_required"))
    except discord.errors.HTTPException as e:
        logger.exception(
            "warning: discord (%s): could not react to message: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_react_error(message: discord.Message) -> None:
    try:
        await message.add_reaction(RED_X)
    except discord.errors.Forbidden:
        await message.channel.send(s("reaction_permissions_required"))
    except discord.errors.HTTPException as e:
        logger.exception(
            "warning: discord (%s): could not react to message: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_fetch_message(
    channel: ChannelType, message_xid: int, guild_xid: int
) -> Optional[discord.Message]:
    if isinstance(
        channel, (discord.VoiceChannel, discord.CategoryChannel, discord.StoreChannel)
    ):
        return None
    try:
        return await channel.fetch_message(message_xid)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.NotFound,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not fetch message: %s",
            guild_xid,
            e,
        )
        return None


async def safe_fetch_channel(
    client: discord.Client, channel_xid: int, guild_xid: int
) -> Optional[ChannelType]:
    channel = client.get_channel(channel_xid)
    if channel:
        return channel
    try:
        return await client.fetch_channel(channel_xid)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.InvalidData,
        discord.errors.NotFound,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not fetch channel: %s",
            guild_xid,
            e,
        )
        return None


async def safe_fetch_user(
    client: discord.Client, user_xid: int
) -> Optional[discord.User]:
    user = client.get_user(user_xid)
    if user:
        return user
    try:
        return await client.fetch_user(user_xid)
    except (discord.errors.NotFound, discord.errors.HTTPException) as e:
        logger.exception("warning: discord: could not fetch user: %s", e)
        return None


async def safe_edit_message(
    message: discord.Message, *, reason: str = None, **options
) -> None:
    try:
        await message.edit(reason=reason, **options)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not edit message: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_delete_message(message: discord.Message) -> None:
    try:
        await message.delete()
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.NotFound,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not delete message: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_send_user(user: discord.User, *args, **kwargs) -> None:
    try:
        await user.send(*args, **kwargs)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
    ) as e:
        logger.exception(
            "warning: discord (DM): could not send message to user (%s): %s",
            str(user),
            e,
        )


async def safe_create_voice_channel(
    client: discord.Client,
    guild_xid: int,
    name: str,
    category: Optional[discord.CategoryChannel] = None,
) -> Optional[discord.VoiceChannel]:
    guild = client.get_guild(guild_xid)
    if not guild:
        return None
    try:
        return await guild.create_voice_channel(name, category=category)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not create voice channel: %s",
            guild_xid,
            e,
        )
        return None


async def safe_create_category_channel(
    client: discord.Client, guild_xid: int, name: str
) -> Optional[discord.CategoryChannel]:
    guild = client.get_guild(guild_xid)
    if not guild:
        return None
    try:
        return await guild.create_category_channel(name)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not create category channel: %s",
            guild_xid,
            e,
        )
        return None


async def safe_delete_channel(channel: ChannelType, guild_xid: int) -> None:
    try:
        await channel.delete()  # type: ignore
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.NotFound,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not delete channel: %s",
            guild_xid,
            e,
        )
        return None


async def safe_create_invite(
    channel: discord.VoiceChannel, guild_xid: int, max_age: int = 0
) -> Optional[str]:
    try:
        invite = await channel.create_invite(max_age=max_age)
        return cast(str, invite.url)
    except discord.errors.HTTPException as e:
        logger.exception(
            "warning: discord (guild %s): could create channel invite: %s",
            guild_xid,
            e,
        )
        return None
