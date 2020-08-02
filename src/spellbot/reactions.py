import logging

import discord

logger = logging.getLogger(__name__)


async def safe_remove_reaction(
    message: discord.Message, emoji: str, user: discord.User
) -> None:  # pragma: no cover
    try:
        await message.remove_reaction(emoji, user)
    except (
        discord.errors.HTTPException,
        discord.errors.Forbidden,
        discord.errors.NotFound,
        discord.errors.InvalidArgument,
    ) as e:
        logger.exception("warning: discord: could not remove reaction", e)


async def safe_clear_reactions(message: discord.Message) -> None:  # pragma: no cover
    try:
        await message.clear_reactions()
    except (discord.errors.HTTPException, discord.errors.Forbidden) as e:
        logger.exception("warning: discord: could not clear reactions", e)
