from __future__ import annotations

import asyncio
import logging
import traceback
from contextlib import AbstractContextManager
from inspect import Traceback
from typing import TYPE_CHECKING, Any, Optional, Type, Union, cast

import discord
from ddtrace import tracer
from ddtrace.constants import ERROR_MSG, ERROR_TYPE
from discord.app_commands import AppCommandError, ContextMenu, NoPrivateMessage
from discord.app_commands import Command as AppCommand
from discord.ext.commands import AutoShardedBot
from discord.ext.commands import Command as ExtCommand
from discord.ui import Item

from .errors import (
    AdminOnlyError,
    GuildOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from .metrics import add_span_error
from .settings import Settings

if TYPE_CHECKING:
    from discord.abc import MessageableChannel


logger = logging.getLogger(__name__)


# Discord API error code indicating that we can not send messages to this user.
CANT_SEND_CODE = 50007

EMBED_DESCRIPTION_SIZE_LIMIT = 4096


def log_warning(log: str, exec_info: bool = False, **kwargs: Any) -> None:
    message = f"warning: discord: {log}"
    logger.warning(message, kwargs, exc_info=exec_info)


def log_info(log: str, exec_info: bool = False, **kwargs: Any) -> None:
    message = f"info: discord: {log}"
    logger.info(message, kwargs, exc_info=exec_info)


def bot_can_reply_to(message: discord.Message) -> bool:
    if (
        not hasattr(message, "channel")
        or not hasattr(message.channel, "type")
        or not hasattr(message.channel, "guild")
        or not hasattr(message.channel, "permissions_for")
        or message.channel.type != discord.ChannelType.text
    ):
        return False
    perms = message.channel.permissions_for(message.channel.guild.me)  # type: ignore
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


def bot_can_read(channel: MessageableChannel) -> bool:
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


def bot_can_delete_channel(channel: MessageableChannel) -> bool:
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
    channel_id = getattr(channel, "id", None)
    logger.info("bot permissions (%s): %s", channel_id, str(perms.value))

    for req in ("manage_channels",):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def is_admin(interaction: discord.Interaction) -> bool:
    guild = getattr(interaction, "guild", None)
    channel = getattr(interaction, "channel", None)
    if not guild or not channel:
        raise AdminOnlyError()
    if interaction.user.id == guild.owner_id:
        return True
    if (perms := channel.permissions_for(interaction.user)) and perms.administrator:
        return True
    if not hasattr(interaction.user, "roles"):
        raise AdminOnlyError()
    author_roles = interaction.user.roles  # type: ignore
    settings = Settings()
    has_admin_role = any(
        role.name == settings.ADMIN_ROLE for role in cast(list[discord.Role], author_roles)
    )
    if not has_admin_role:
        raise AdminOnlyError()
    return True


def is_guild(interaction: discord.Interaction) -> bool:
    guild = getattr(interaction, "guild", None)
    if guild is None:
        raise GuildOnlyError()
    return True


def user_can_moderate(
    author: Optional[Union[discord.User, discord.Member]],
    guild: Optional[discord.Guild],
    channel: Optional[MessageableChannel],
) -> bool:
    if not guild or not channel or not author:
        return False
    if not hasattr(author, "id"):
        return False
    author_id = author.id  # type: ignore
    if author_id == guild.owner_id:
        return True
    if not hasattr(author, "roles"):
        return False
    member: discord.Member = cast(discord.Member, author)
    if (perms := channel.permissions_for(member)) and perms.administrator:
        return True
    author_roles = author.roles  # type: ignore
    settings = Settings()
    return any(
        role.name == settings.ADMIN_ROLE or role.name.startswith(settings.MOD_PREFIX)
        for role in cast(list[discord.Role], author_roles)
        if role is not None
    )


class suppress(AbstractContextManager[None]):
    """
    Suppresses any exceptions from the given set.

    Logs the given message whenever an exception is suppressed. String interpolation
    parameters should be embedded into the log message as `%(name)s` and provided
    corresponding values via keyword argument. For example:

        with suppress(YourError, log="whatever %s(wotnot)s", wotnot="I don't know"):
            ...

    Note that you should NOT use `return` within the context of `suppress()`. Instead
    use The Single Return Law pattern. This is because static analysis tools will not
    be able to understand that code following the context is reachable.
    """

    def __init__(self, *exceptions: Type[Exception], log: str, **kwargs: Any):
        self._exceptions = exceptions
        self._log = log
        self._kwargs = kwargs

    def __enter__(self):
        pass

    def __exit__(self, exctype: Type[Exception], excinst: Exception, exctb: Traceback):
        if captured := exctype is not None and issubclass(exctype, self._exceptions):
            log_warning(self._log, exec_info=True, **self._kwargs)
            if span := tracer.current_span():  # pragma: no cover
                span.set_exc_info(exctype, excinst, exctb)
            if root := tracer.current_root_span():  # pragma: no cover
                root.set_tags(
                    {
                        ERROR_TYPE: "OperationalError",
                        ERROR_MSG: "An error occurred during bot operation",
                    },
                )
                root.error = 1
        return captured


# I have no idea how to properly type hint this.
def for_all_callbacks(decorator: Any) -> Any:
    def decorate(cls: Any):
        for attr in cls.__dict__:
            method = getattr(cls, attr)
            if isinstance(method, (AppCommand, ExtCommand)):
                setattr(cls, attr, decorator(method))

        return cls

    return decorate


async def handle_interaction_errors(interaction: discord.Interaction, error: Exception) -> None:
    from .operations import safe_send_user

    if isinstance(error, AdminOnlyError):
        return await safe_send_user(interaction.user, "You do not have permission to do that.")
    if isinstance(error, GuildOnlyError):
        return await safe_send_user(interaction.user, "This command only works in a guild.")
    if isinstance(error, NoPrivateMessage):
        return await safe_send_user(interaction.user, "This command is not supported in DMs.")
    if isinstance(error, UserBannedError):
        return await safe_send_user(interaction.user, "You have been banned from using SpellBot.")
    if isinstance(error, UserUnverifiedError):
        return await safe_send_user(interaction.user, "Only verified users can do that here.")
    if isinstance(error, UserVerifiedError):
        return await safe_send_user(interaction.user, "Only unverified users can do that here.")

    add_span_error(error)
    ref = (
        f"command `{interaction.command.qualified_name}`"
        if interaction.command is not None and isinstance(interaction, (AppCommand, ExtCommand))
        else f"component `{interaction.command.qualified_name}`"
        if interaction.command is not None and isinstance(interaction, ContextMenu)
        else f"interaction `{interaction.id}`"
    )
    logger.error("error: unhandled exception in %s: %s: %s", ref, error.__class__.__name__, error)
    traceback.print_tb(error.__traceback__)


async def handle_view_errors(
    interaction: discord.Interaction,
    error: Exception,
    item: Item[Any],
) -> None:
    return await handle_interaction_errors(interaction, error)


async def handle_command_errors(interaction: discord.Interaction, error: AppCommandError) -> None:
    return await handle_interaction_errors(interaction, error)


async def load_extensions(bot: AutoShardedBot, do_sync: bool = False) -> None:
    from .cogs import load_all_cogs

    settings = Settings()
    guild = settings.GUILD_OBJECT

    if do_sync:
        if guild:  # pragma: no cover
            logger.info("syncing commands to debug guild: %s", guild.id)
        else:
            logger.info("syncing global commands")

        logger.info("clearing commands...")
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)

        logger.info("waiting to avoid rate limit...")
        await asyncio.sleep(1)

    logger.info("loading cogs...")
    await load_all_cogs(bot)
    commands = [c.name for c in bot.tree.get_commands(guild=guild)]
    logger.info("registered commands: %s", ", ".join(commands))

    if do_sync:
        logger.info("syncing commands...")
        await bot.tree.sync(guild=guild)

    bot.tree.on_error = handle_command_errors
