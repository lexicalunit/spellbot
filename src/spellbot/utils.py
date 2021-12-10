import logging
from contextlib import AbstractContextManager
from typing import Any, Optional, Union, cast

import discord
from discord_slash.context import InteractionContext
from discord_slash.model import CallbackObject

from .errors import AdminOnlyError
from .metrics import alert_error
from .settings import Settings

logger = logging.getLogger(__name__)

# I don't know why, but there isn't any base "channel" type in discord.py.
DiscordChannel = Union[discord.abc.GuildChannel, discord.abc.PrivateChannel]

# Discord API error code indicating that we can not send messages to this user.
CANT_SEND_CODE = 50007

EMBED_DESCRIPTION_SIZE_LIMIT = 4096


def log_warning(log: str, exec_info: bool = False, **kwargs: Any):
    message = f"warning: discord: {log}"
    logger.warning(message, kwargs, exc_info=exec_info)


def bot_can_reply_to(message: discord.Message) -> bool:
    if (
        not hasattr(message, "channel")
        or not hasattr(message.channel, "type")
        or not hasattr(message.channel, "guild")
        or message.channel.type != discord.ChannelType.text
    ):
        return False
    perms = message.channel.permissions_for(message.channel.guild.me)
    for req in ("send_messages",):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_role(guild: discord.Guild) -> bool:
    if not guild.me:
        return False
    perms = guild.me.guild_permissions
    for req in ("manage_roles",):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_read(channel: DiscordChannel) -> bool:
    if not hasattr(channel, "type"):
        return False
    channel_type = getattr(channel, "type")
    if channel_type == discord.ChannelType.private:
        return True
    guild_channel = cast(discord.abc.GuildChannel, channel)
    if not hasattr(guild_channel, "guild"):
        return True
    guild: discord.Guild = getattr(guild_channel, "guild")
    perms = guild_channel.permissions_for(guild.me)
    for req in ("read_messages", "read_message_history"):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_delete_channel(channel: DiscordChannel) -> bool:
    if not hasattr(channel, "type"):
        return False
    channel_type = getattr(channel, "type")
    if channel_type == discord.ChannelType.private:
        return False
    guild_channel = cast(discord.abc.GuildChannel, channel)
    if not hasattr(guild_channel, "guild"):
        return False
    guild: discord.Guild = getattr(guild_channel, "guild")
    perms = guild_channel.permissions_for(guild.me)
    for req in ("manage_channels",):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def is_admin(ctx: InteractionContext) -> bool:
    guild = getattr(ctx, "guild", None)
    channel = getattr(ctx, "channel", None)
    if not guild or not channel:
        raise AdminOnlyError()
    if ctx.author_id == guild.owner_id:
        return True
    if (perms := channel.permissions_for(ctx.author)) and perms.administrator:
        return True
    if not hasattr(ctx.author, "roles"):
        raise AdminOnlyError()
    author_roles = ctx.author.roles  # type: ignore
    settings = Settings()
    has_admin_role = any(
        role.name == settings.ADMIN_ROLE
        for role in cast(list[discord.Role], author_roles)
    )
    if not has_admin_role:
        raise AdminOnlyError()
    return True


def user_can_moderate(
    author: Optional[Union[discord.User, discord.Member]],
    guild: Optional[discord.Guild],
    channel: Optional[Union[discord.TextChannel, discord.DMChannel]],
) -> bool:
    if not guild or not channel:
        return False
    if not hasattr(author, "id"):
        return False
    author_id = author.id  # type: ignore
    if author_id == guild.owner_id:
        return True
    if not hasattr(author, "roles"):
        return False
    if (perms := channel.permissions_for(author)) and perms.administrator:
        return True
    author_roles = author.roles  # type: ignore
    settings = Settings()
    return any(
        role.name == settings.ADMIN_ROLE or role.name.startswith(settings.MOD_PREFIX)
        for role in cast(list[discord.Role], author_roles)
    )


class suppress(AbstractContextManager):
    """
    Suppresses any exceptions from the given set.

    Logs the given log message whenever an exception is suppressed. String interpolation
    parameters should be embedded into the log message as `%(name)s` and provided
    coresponding values via keyword argument. For example:

        with suppress(YourError, log="whatever %s(wotnot)s", wotnot="I don't know"):
            ...

    Note that you should NOT use `return` within the context of `suppress()`. Instead
    use The Single Return Law pattern. This is because static analysis tools will not
    be able to understand that code following the context is reachable.
    """

    def __init__(self, *exceptions, log: str, **kwargs: Any):
        self._exceptions = exceptions
        self._log = log
        self._kwargs = kwargs

    def __enter__(self):
        pass

    def __exit__(self, exctype, excinst, exctb):
        if captured := exctype is not None and issubclass(exctype, self._exceptions):
            alert_error("safe_message_reply error", str(excinst))
            log_warning(self._log, exec_info=True, **self._kwargs)
        return captured


def for_all_callbacks(decorator):
    def decorate(cls):
        for attr in cls.__dict__:
            method = getattr(cls, attr)
            if isinstance(method, CallbackObject):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls

    return decorate
