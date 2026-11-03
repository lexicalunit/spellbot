# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import functools
import logging
import types
from typing import TYPE_CHECKING, Any, cast

import discord
from ddtrace.trace import tracer
from discord.app_commands import AppCommandError, CommandOnCooldown, NoPrivateMessage
from discord.app_commands import Command as AppCommand
from discord.ext.commands import AutoShardedBot
from discord.ext.commands import Command as ExtCommand

from .errors import AdminOnlyError, GuildBannedError, GuildOnlyError, ModOnlyError, UserBannedError
from .i18n import t, user_locale
from .metrics import add_span_context, add_span_error
from .settings import settings

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterable

    from discord.abc import MessageableChannel
    from discord.ui import Item


logger = logging.getLogger(__name__)

# Discord API error code indicating that we can not send messages to this user.
CANT_SEND_CODE = 50007

# Discord API error code indicating that the user's privacy settings prevent DMs
# from the bot (commonly reported by Discord as "no mutual guilds" even when the
# bot and user are in the same server, if the user has disabled DMs from server
# members, blocked the bot, or restricted DMs to friends).
NO_MUTUAL_GUILDS_CODE = 50278

# Discord API error code indicating that the bot lacks access to the resource.
# This can happen when the bot no longer has permissions to a channel or message.
MISSING_ACCESS_CODE = 50001

# Discord API error code indicating that the interaction token has expired.
# This can happen when the bot takes too long to respond to an interaction.
UNKNOWN_INTERACTION_CODE = 10062

# Discord API error code indicating that the message no longer exists.
# This can happen when the message was deleted before we could edit it.
UNKNOWN_MESSAGE_CODE = 10008

# Discord API error code indicating that the channel no longer exists.
# This can happen when the channel was deleted before we could fetch it.
UNKNOWN_CHANNEL_CODE = 10003

# Discord API error code indicating that the interaction has already been acknowledged.
# This can happen when we try to defer an interaction that was already responded to.
ALREADY_ACKNOWLEDGED_CODE = 40060


def log_warning(log: str, exc_info: bool = False, **kwargs: Any) -> None:
    if kwargs:
        log = log % kwargs
    message = f"warning: discord: {log}"
    logger.warning(message, exc_info=exc_info)


def log_info(log: str, exc_info: bool = False, **kwargs: Any) -> None:
    if kwargs:
        log = log % kwargs
    message = f"info: discord: {log}"
    logger.info(message, exc_info=exc_info)


def safe_permissions_for(obj: Any, *args: Any) -> discord.Permissions | None:
    try:
        return obj.permissions_for(*args)
    except Exception:
        log_info("failed to get permissions object", exc_info=True)
        return None


def bot_guild_permission(guild: discord.Guild | None, name: str) -> bool:
    """Whether the bot has the guild wide permission `name` in `guild`."""
    if not guild or not guild.me:
        return False
    return bool(getattr(guild.me.guild_permissions, name, False))


def bot_channel_permissions(channel: MessageableChannel, *names: str) -> bool:
    """Whether the bot has every permission in `names` in the guild channel `channel`."""
    if not hasattr(channel, "type") or channel.type == discord.ChannelType.private:
        return False
    guild_channel = cast("discord.abc.GuildChannel", channel)
    if not hasattr(guild_channel, "guild"):
        return False
    perms = safe_permissions_for(guild_channel, guild_channel.guild.me)
    if perms is None:
        return False
    logger.info("bot permissions (%s): %s", getattr(channel, "id", None), str(perms.value))
    return all(getattr(perms, name, False) for name in names)


def bot_can_role(guild: discord.Guild, role: discord.Role | None = None) -> bool:
    if not bot_guild_permission(guild, "manage_roles"):
        return False
    return not (role is not None and role > guild.me.top_role)


def bot_can_read(channel: MessageableChannel) -> bool:
    if not hasattr(channel, "type"):
        return False
    channel_type = channel.type
    if channel_type == discord.ChannelType.private:
        return True
    guild_channel = cast("discord.abc.GuildChannel", channel)
    if not hasattr(guild_channel, "guild"):
        return True
    guild: discord.Guild = guild_channel.guild
    perms = safe_permissions_for(guild_channel, guild.me)
    for req in ("read_messages", "read_message_history"):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_manage_channels(guild: discord.Guild) -> bool:
    return bot_guild_permission(guild, "manage_channels")


def bot_can_delete_message(message: discord.Message | discord.PartialMessage) -> bool:
    return bot_guild_permission(getattr(message, "guild", None), "manage_messages")


def bot_can_delete_channel(channel: MessageableChannel) -> bool:
    return bot_channel_permissions(channel, "manage_channels")


def bot_can_read_messages(guild: discord.Guild) -> bool:
    return bot_guild_permission(guild, "read_messages")


def bot_can_send_messages(channel: MessageableChannel) -> bool:
    return bot_channel_permissions(channel, "send_messages")


def is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.id == settings.OWNER_XID:
        return True
    guild = getattr(interaction, "guild", None)
    channel = getattr(interaction, "channel", None)
    if not guild or not channel:
        raise AdminOnlyError
    if interaction.user.id == guild.owner_id:
        return True
    perms = safe_permissions_for(channel, interaction.user)
    if perms is not None and perms.administrator:
        return True
    author_roles = getattr(interaction.user, "roles", None)
    if author_roles is None:
        raise AdminOnlyError
    has_admin_role = any(
        role.name == settings.ADMIN_ROLE for role in cast("list[discord.Role]", author_roles)
    )
    if not has_admin_role:
        raise AdminOnlyError
    return True


def is_guild(interaction: discord.Interaction) -> bool:
    guild = getattr(interaction, "guild", None)
    if guild is None:
        raise GuildOnlyError
    return True


def is_mod(interaction: discord.Interaction) -> bool:
    if interaction.user.id == settings.OWNER_XID:
        return True
    guild = getattr(interaction, "guild", None)
    channel = getattr(interaction, "channel", None)
    if not user_can_moderate(interaction.user, guild, channel):
        raise ModOnlyError
    return True


def is_moderator(
    *,
    is_guild_owner: bool,
    has_admin: bool,
    has_ban_members: bool,
    role_names: Iterable[str],
) -> bool:
    """
    Decide moderator/admin status from already-resolved permission primitives.

    Shared by the bot (`user_can_moderate`) and the web tier so both apply identical
    rules. A member is a moderator when they own the guild, have the administrator or
    ban-members permission, or hold a role named after `ADMIN_ROLE` / `MOD_PREFIX`.
    """
    if is_guild_owner:
        return True
    if has_admin or has_ban_members:
        return True
    return any(
        name == settings.ADMIN_ROLE or name.startswith(settings.MOD_PREFIX) for name in role_names
    )


def user_can_moderate(
    author: discord.User | discord.Member | None,
    guild: discord.Guild | None,
    channel: MessageableChannel | None,
) -> bool:
    if not guild or not channel or not author:
        return False
    if not hasattr(author, "id"):
        return False
    if author.id == settings.OWNER_XID:
        return True
    is_guild_owner = author.id == guild.owner_id
    has_admin = False
    has_ban_members = False
    role_names: list[str] = []
    if hasattr(author, "roles"):
        member: discord.Member = cast("discord.Member", author)
        if perms := safe_permissions_for(channel, member):
            has_admin = perms.administrator
            has_ban_members = perms.ban_members
        role_names = [role.name for role in member.roles if role is not None]
    return is_moderator(
        is_guild_owner=is_guild_owner,
        has_admin=has_admin,
        has_ban_members=has_ban_members,
        role_names=role_names,
    )


# I have no idea how to properly type hint this.
def for_all_callbacks(decorator: Any) -> Any:
    def decorate(cls: Any) -> Any:
        for attr in cls.__dict__:
            method = getattr(cls, attr)
            if isinstance(method, AppCommand | ExtCommand):
                setattr(cls, attr, decorator(method))

        return cls

    return decorate


def traced_interaction[F: Callable[..., Coroutine[Any, Any, Any]]](
    resource: str | None = None,
) -> Callable[[F], F]:
    """
    Trace a command callback as an `interaction` span tagged with its interaction's context.

    The span's resource defaults to the callback's name. discord.py resolves a callback's
    parameter annotations against `callback.__globals__`, so the wrapper is rebuilt with the
    wrapped callback's globals: annotations like `discord.User` resolve exactly as they would
    without the wrapper. The wrapper only uses names from its closure, never those globals.
    """

    def decorate(fn: F) -> F:
        function = cast("types.FunctionType", fn)
        trace = tracer.trace
        tag = add_span_context
        name = resource or function.__name__
        # The interaction (or `commands.Context`) is the parameter right after `self`.
        context_name = function.__code__.co_varnames[1]

        async def traced(*args: Any, **kwargs: Any) -> Any:
            with trace("interaction", resource=name):
                tag(args[1] if len(args) > 1 else kwargs.get(context_name))
                return await fn(*args, **kwargs)

        wrapper = types.FunctionType(
            traced.__code__,
            function.__globals__,
            function.__name__,
            traced.__defaults__,
            traced.__closure__,
        )
        return cast("F", functools.update_wrapper(wrapper, function))

    return decorate


# Expected errors and the translation key of the message sent to the user for each.
ERROR_MESSAGE_KEYS: dict[type[Exception], str] = {
    AdminOnlyError: "errors.no_permission",
    ModOnlyError: "errors.no_permission",
    GuildOnlyError: "errors.guild_only",
    NoPrivateMessage: "errors.no_dms",
    UserBannedError: "errors.banned",
    GuildBannedError: "errors.banned",
}


async def handle_interaction_errors(interaction: discord.Interaction, error: Exception) -> None:
    from .operations import safe_send_user  # allow_inline: circular import

    locale = user_locale(interaction)
    if isinstance(error, CommandOnCooldown):
        seconds = max(1, round(error.retry_after))
        return await safe_send_user(
            interaction.user,
            t("errors.cooldown", locale=locale, seconds=seconds),
        )
    for error_type, key in ERROR_MESSAGE_KEYS.items():
        if isinstance(error, error_type):
            return await safe_send_user(interaction.user, t(key, locale=locale))

    add_span_error(error)
    command = interaction.command
    ref = (
        f"command `{command.qualified_name}`"
        if command is not None
        else f"interaction `{interaction.id}`"
    )
    logger.error(
        "error: unhandled exception in %s: %s: %s",
        ref,
        error.__class__.__name__,
        error,
        exc_info=error,
    )
    return None


async def handle_view_errors(
    interaction: discord.Interaction[Any],
    error: Exception,
    _item: Item[Any],
) -> None:  # pragma: no cover
    return await handle_interaction_errors(interaction, error)


async def handle_command_errors(
    interaction: discord.Interaction[Any],
    error: AppCommandError,
) -> None:  # pragma: no cover
    return await handle_interaction_errors(interaction, error)


async def load_extensions(bot: AutoShardedBot, do_sync: bool = False) -> None:  # pragma: no cover
    from .cogs import load_all_cogs  # allow_inline

    guild = settings.GUILD_OBJECT

    if do_sync:
        if guild:
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

    bot.tree.error(handle_command_errors)
