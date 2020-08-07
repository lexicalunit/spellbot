import logging

import discord

from spellbot.assets import s

logger = logging.getLogger(__name__)


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
        logger.exception("warning: discord: could not remove reaction: %s", e)


async def safe_clear_reactions(message: discord.Message) -> None:
    try:
        await message.clear_reactions()
    except discord.errors.Forbidden:
        await message.channel.send(s("reaction_permissions_required"))
    except discord.errors.HTTPException as e:
        logger.exception("warning: discord: could not clear reactions: %s", e)
