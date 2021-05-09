import logging
from typing import Any, Optional, Union, cast

import discord

from spellbot.assets import s
from spellbot.constants import EMOJI_FAIL, EMOJI_OK

logger = logging.getLogger(__name__)

ChannelType = Union[
    discord.CategoryChannel,
    discord.DMChannel,
    discord.GroupChannel,
    discord.StoreChannel,
    discord.TextChannel,
    discord.VoiceChannel,
]

MentionableChannelType = Union[
    discord.CategoryChannel,
    discord.GroupChannel,
    discord.StoreChannel,
    discord.TextChannel,
    discord.VoiceChannel,
]

# Discord API error code indicating that we can not send messages to this user.
CANT_SEND_CODE = 50007


def _user_or_guild_log_part(message: discord.Message) -> str:  # pragma: no cover
    if hasattr(message, "guild"):
        return f"guild {cast(Any, message.guild).id}"
    return "DM"


def bot_can_react(message: discord.Message) -> bool:
    if message.channel.type == discord.ChannelType.private:
        return True
    requirements = {
        "read_messages",
        "read_message_history",
        "add_reactions",
        "manage_messages",
    }
    perms = message.channel.guild.me.permissions_in(message.channel)
    for req in requirements:
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_send(message: discord.Message) -> bool:
    if message.channel.type == discord.ChannelType.private:
        return True
    requirements = {"send_messages"}
    perms = message.channel.guild.me.permissions_in(message.channel)
    for req in requirements:
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_read(channel: discord.TextChannel) -> bool:
    if channel.type == discord.ChannelType.private:
        return True
    requirements = {
        "read_messages",
        "read_message_history",
    }
    perms = channel.guild.me.permissions_in(channel)
    for req in requirements:
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_role(guild: discord.Guild) -> bool:
    requirements = {
        "manage_roles",
    }
    perms = guild.me.guild_permissions
    for req in requirements:
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


async def safe_remove_reaction(
    message: discord.Message, emoji: str, user: discord.User
) -> None:
    try:
        if not bot_can_react(message):
            await message.channel.send(s("reaction_permissions_required"))
            return
        await message.remove_reaction(emoji, user)
    except (
        discord.errors.DiscordServerError,
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
        discord.errors.NotFound,
        discord.errors.Forbidden,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not remove reaction: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_clear_reactions(message: discord.Message) -> None:
    try:
        if not bot_can_react(message):
            await message.channel.send(s("reaction_permissions_required"))
            return
        await message.clear_reactions()
    except (
        discord.errors.DiscordServerError,
        discord.errors.HTTPException,
        discord.errors.Forbidden,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not clear reactions: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_react_emoji(message: discord.Message, emoji: str) -> None:
    try:
        if not bot_can_react(message):
            await message.channel.send(s("reaction_permissions_required"))
            return
        await message.add_reaction(emoji)
    except (
        discord.errors.DiscordServerError,
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
        discord.errors.Forbidden,
        discord.errors.NotFound,
    ) as e:
        logger.exception(
            "warning: discord (%s): could not react to message: %s",
            _user_or_guild_log_part(message),
            e,
        )


async def safe_react_ok(message: discord.Message) -> None:
    await safe_react_emoji(message, EMOJI_OK)


async def safe_react_error(message: discord.Message) -> None:
    await safe_react_emoji(message, EMOJI_FAIL)


async def safe_fetch_message(
    channel: ChannelType, message_xid: int, guild_xid: int
) -> Optional[discord.Message]:
    if channel.type != discord.ChannelType.text:
        return None

    text_channel = cast(discord.TextChannel, channel)
    if not bot_can_read(text_channel):
        return None

    try:
        return await text_channel.fetch_message(message_xid)
    except (
        discord.errors.DiscordServerError,
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
        discord.errors.DiscordServerError,
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
        discord.errors.DiscordServerError,
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
        discord.errors.DiscordServerError,
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
    if not hasattr(user, "send"):
        # Very rarely we get a ClientUser object here instead of a User? I have
        # no idea why this happens but a ClientUser does not have a send() method.
        # For now let's just log this I guess.
        logger.warning(
            "warning: discord (DM): could not send message to ClientUser (%s)",
            str(user),
        )
        return

    def log_exception(e):
        logger.exception(
            "error: discord (DM): could not send message to user (%s): %s",
            str(user),
            e,
        )

    try:
        await user.send(*args, **kwargs)
    except (discord.errors.Forbidden, discord.errors.HTTPException) as e:
        # User may have the bot blocked or they may have DMs only allowed for friends.
        # Generally speaking, we can safely ignore this sort of error. However, too
        # many failed API requests can cause our bot to be flagged and rate limited.
        # It's not clear what can be done to avoid this though.
        if isinstance(e, discord.errors.Forbidden) or e.code == CANT_SEND_CODE:
            logger.warning(
                "warning: discord (DM): can not send messages to user %s",
                str(user),
            )
        else:
            log_exception(e)
    except (discord.errors.DiscordServerError, discord.errors.InvalidArgument) as e:
        log_exception(e)


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
        discord.errors.DiscordServerError,
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
        discord.errors.DiscordServerError,
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


async def safe_delete_channel(channel: ChannelType, guild_xid: int) -> bool:
    try:
        await channel.delete()  # type: ignore
        return True
    except (
        discord.errors.DiscordServerError,
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.NotFound,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not delete channel: %s",
            guild_xid,
            e,
        )
    return False


async def safe_create_invite(
    channel: discord.VoiceChannel, guild_xid: int, max_age: int = 0
) -> Optional[str]:
    try:
        invite = await channel.create_invite(max_age=max_age)
        return cast(str, invite.url)
    except (
        discord.errors.DiscordServerError,
        discord.errors.HTTPException,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could create channel invite: %s",
            guild_xid,
            e,
        )
    return None


async def safe_fetch_guild(
    client: discord.Client, guild_xid: int
) -> Optional[discord.Guild]:
    guild = client.get_guild(guild_xid)
    if guild:
        return guild

    try:
        return await client.fetch_guild(guild_xid)
    except (
        discord.errors.DiscordServerError,
        discord.errors.Forbidden,
        discord.errors.HTTPException,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not fetch guild: %s",
            guild_xid,
            e,
        )
    return None


async def safe_send_channel(
    message: discord.Message,
    content: Optional[str] = None,
    *,
    embed: Optional[discord.Embed] = None,
    file: Optional[discord.File] = None,
) -> Optional[discord.Message]:
    try:
        if not bot_can_send(message):
            return None

        return await message.channel.send(content, embed=embed, file=file)
    except (
        discord.errors.DiscordServerError,
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.InvalidArgument,
    ) as e:
        logger.exception(
            "warning: discord: could not send message to channel: %s",
            e,
        )
    return None


async def safe_add_role(
    user_or_member: Union[discord.User, discord.Member], guild: discord.Guild, role: str
) -> None:
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
                "warning: discord (guild %s): add role: could not find member: %s",
                guild.id,
                str(user_or_member),
            )
            return
        discord_role = discord.utils.find(lambda m: m.name == role, guild.roles)
        if not discord_role:
            logger.warning(
                "warning: discord (guild %s): add role: could not find role: %s",
                guild.id,
                str(role),
            )
            return
        if not bot_can_role(guild):
            logger.warning(
                "warning: discord (guild %s): add role: no permissions to add role: %s",
                guild.id,
                str(role),
            )
            return
        await member.add_roles(discord_role)
    except (
        discord.errors.Forbidden,
        discord.errors.HTTPException,
    ) as e:
        logger.exception(
            "warning: discord (guild %s): could not add role to member (%s): %s",
            guild.id,
            str(user_or_member),
            e,
        )
