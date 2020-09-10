import logging
from typing import Any, Optional, Union, cast

import discord

from spellbot.assets import s
from spellbot.constants import GREEN_CHECK, RED_X

logger = logging.getLogger(__name__)

ChannelType = Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.DMChannel,
    discord.CategoryChannel,
    discord.GroupChannel,
    discord.StoreChannel,
]


def _user_or_guild_log_part(message: discord.Message) -> str:
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
        discord.errors.NotFound,
        discord.errors.InvalidArgument,
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
            "warning: discord (%s): could react to message: %s",
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
            "warning: discord (%s): could react to message: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_fetch_message(
    channel: ChannelType, message_xid: int, guild_xid: int
) -> Optional[discord.Message]:  # pragma: no cover
    if isinstance(
        channel, (discord.VoiceChannel, discord.CategoryChannel, discord.StoreChannel)
    ):
        return None
    try:
        return await channel.fetch_message(message_xid)
    except (
        discord.errors.HTTPException,
        discord.errors.NotFound,
        discord.errors.Forbidden,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not fetch message: %s",
            guild_xid,
            e,
        )
        return None


async def safe_fetch_channel(
    client: discord.Client, channel_xid: int, guild_xid: int
) -> Optional[ChannelType]:  # pragma: no cover
    channel = client.get_channel(channel_xid)
    if channel:
        return channel
    try:
        return await client.fetch_channel(channel_xid)
    except (
        discord.errors.InvalidData,
        discord.errors.HTTPException,
        discord.errors.NotFound,
        discord.errors.Forbidden,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not fetch channel: %s",
            guild_xid,
            e,
        )
        return None


async def safe_fetch_user(
    client: discord.Client, user_xid: int
) -> Optional[discord.User]:  # pragma: no cover
    user = client.get_user(user_xid)
    if user:
        return user
    try:
        return await client.fetch_user(user_xid)
    except (discord.errors.NotFound, discord.errors.HTTPException) as e:
        logger.exception("warning: discord: could fetch user: %s", e)
        return None


async def safe_edit_message(
    message: discord.Message, *, reason: str = None, **options
) -> None:  # pragma: no cover
    try:
        await message.edit(reason=reason, **options)
    except (
        discord.errors.InvalidArgument,
        discord.errors.Forbidden,
        discord.errors.HTTPException,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not edit message: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_delete_message(message: discord.Message) -> None:  # pragma: no cover
    try:
        await message.delete()
    except (
        discord.errors.Forbidden,
        discord.errors.NotFound,
        discord.errors.HTTPException,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not delete message: %s",
            _user_or_guild_log_part(message),
            e,
        )
