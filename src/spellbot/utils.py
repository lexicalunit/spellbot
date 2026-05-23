from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from typing import TYPE_CHECKING, Any, cast

import discord
from discord.app_commands import AppCommandError, ContextMenu, NoPrivateMessage
from discord.app_commands import Command as AppCommand
from discord.ext.commands import AutoShardedBot
from discord.ext.commands import Command as ExtCommand

from .errors import (
    AdminOnlyError,
    GuildBannedError,
    GuildOnlyError,
    ModOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from .i18n import t, user_locale
from .metrics import add_span_error
from .settings import settings

if TYPE_CHECKING:
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

# Discord API error code indicating that the interaction has already been acknowledged.
# This can happen when we try to defer an interaction that was already responded to.
ALREADY_ACKNOWLEDGED_CODE = 40060

EMBED_DESCRIPTION_SIZE_LIMIT = 4096


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


def bot_can_reply_to(message: discord.Message) -> bool:
    if (
        not hasattr(message, "channel")
        or not hasattr(message.channel, "type")
        or not hasattr(message.channel, "guild")
        or not hasattr(message.channel, "permissions_for")
        or message.channel.type != discord.ChannelType.text
    ):
        return False
    if message.channel.guild is None:
        return False
    perms = safe_permissions_for(message.channel, message.channel.guild.me)
    if perms is None:
        return False
    for req in ("send_messages",):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_role(guild: discord.Guild, role: discord.Role | None = None) -> bool:
    if not guild.me:
        return False
    perms = guild.me.guild_permissions
    req = "manage_roles"
    if not hasattr(perms, req) or not getattr(perms, req):
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
    if not guild.me:
        return False
    perms = guild.me.guild_permissions
    req = "manage_channels"
    return hasattr(perms, req) and getattr(perms, req)


def bot_can_delete_message(message: discord.Message | discord.PartialMessage) -> bool:
    if not hasattr(message, "guild"):
        return False
    guild = message.guild
    if not guild or not guild.me:
        return False
    perms = guild.me.guild_permissions
    req = "manage_messages"
    return hasattr(perms, req) and getattr(perms, req)


def bot_can_delete_channel(channel: MessageableChannel) -> bool:
    if not hasattr(channel, "type"):
        return False
    channel_type = channel.type
    if channel_type == discord.ChannelType.private:
        return False
    guild_channel = cast("discord.abc.GuildChannel", channel)
    if not hasattr(guild_channel, "guild"):
        return False
    guild: discord.Guild = guild_channel.guild
    perms = safe_permissions_for(guild_channel, guild.me)
    if perms is None:
        return False
    channel_id = getattr(channel, "id", None)
    logger.info("bot permissions (%s): %s", channel_id, str(perms.value))
    for req in ("manage_channels",):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


def bot_can_read_messages(guild: discord.Guild) -> bool:
    if not guild.me:
        return False
    perms = guild.me.guild_permissions
    req = "read_messages"
    return hasattr(perms, req) and getattr(perms, req)


def bot_can_send_messages(channel: MessageableChannel) -> bool:
    if not hasattr(channel, "type"):
        return False
    channel_type = channel.type
    if channel_type == discord.ChannelType.private:
        return False
    guild_channel = cast("discord.abc.GuildChannel", channel)
    if not hasattr(guild_channel, "guild"):
        return False
    guild: discord.Guild = guild_channel.guild
    perms = safe_permissions_for(guild_channel, guild.me)
    if perms is None:
        return False
    channel_id = getattr(channel, "id", None)
    logger.info("bot permissions (%s): %s", channel_id, str(perms.value))
    for req in ("send_messages",):
        if not hasattr(perms, req) or not getattr(perms, req):
            return False
    return True


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
    if not hasattr(interaction.user, "roles"):
        raise AdminOnlyError
    author_roles = interaction.user.roles  # type: ignore
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


def user_can_moderate(
    author: discord.User | discord.Member | None,
    guild: discord.Guild | None,
    channel: MessageableChannel | None,
) -> bool:
    if not guild or not channel or not author:
        return False
    if not hasattr(author, "id"):
        return False
    author_id = author.id
    if author_id == guild.owner_id:
        return True
    if not hasattr(author, "roles"):
        return False
    member: discord.Member = cast("discord.Member", author)
    if (perms := safe_permissions_for(channel, member)) and perms.administrator:
        return True
    author_roles = author.roles  # type: ignore
    return any(
        role.name == settings.ADMIN_ROLE or role.name.startswith(settings.MOD_PREFIX)
        for role in cast("list[discord.Role]", author_roles)
        if role is not None
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


async def handle_interaction_errors(interaction: discord.Interaction, error: Exception) -> None:
    from .operations import safe_send_user  # allow_inline: circular import

    locale = user_locale(interaction)
    if isinstance(error, AdminOnlyError):
        return await safe_send_user(interaction.user, t("errors.no_permission", locale=locale))
    if isinstance(error, ModOnlyError):
        return await safe_send_user(interaction.user, t("errors.no_permission", locale=locale))
    if isinstance(error, GuildOnlyError):
        return await safe_send_user(interaction.user, t("errors.guild_only", locale=locale))
    if isinstance(error, NoPrivateMessage):
        return await safe_send_user(interaction.user, t("errors.no_dms", locale=locale))
    if isinstance(error, UserBannedError):
        return await safe_send_user(interaction.user, t("errors.banned", locale=locale))
    if isinstance(error, GuildBannedError):
        return await safe_send_user(interaction.user, t("errors.banned", locale=locale))
    if isinstance(error, UserUnverifiedError):
        return await safe_send_user(interaction.user, t("errors.verified_only", locale=locale))
    if isinstance(error, UserVerifiedError):
        return await safe_send_user(interaction.user, t("errors.unverified_only", locale=locale))

    add_span_error(error)
    ref = (
        f"command `{interaction.command.qualified_name}`"
        if interaction.command is not None and isinstance(interaction, AppCommand | ExtCommand)
        else f"component `{interaction.command.qualified_name}`"
        if interaction.command is not None and isinstance(interaction, ContextMenu)
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
    interaction: discord.Interaction,
    error: Exception,
    _item: Item[Any],
) -> None:  # pragma: no cover
    return await handle_interaction_errors(interaction, error)


async def handle_command_errors(
    interaction: discord.Interaction,
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

    bot.tree.on_error = handle_command_errors


def generate_signed_url(guild_xid: int, expires_in_minutes: int = 15) -> str:
    """Generate an HMAC-signed analytics URL for a guild."""
    expires = int(time.time()) + (expires_in_minutes * 60)
    message = f"{guild_xid}:{expires}"
    secret = (settings.SECRET_TOKEN or "").encode()
    sig = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
    return f"{settings.API_BASE_URL}/g/{guild_xid}/analytics?expires={expires}&sig={sig}"


def validate_signature(guild_xid: int, expires: int, sig: str) -> bool:
    """Validate an HMAC-signed analytics URL."""
    if not settings.CHECK_SIGNATURE:
        return True
    if time.time() > expires:
        return False
    message = f"{guild_xid}:{expires}"
    secret = (settings.SECRET_TOKEN or "").encode()
    expected = hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)
