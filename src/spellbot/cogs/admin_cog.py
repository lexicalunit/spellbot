# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from spellbot.actions import AdminAction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_admin, is_guild, is_mod, traced_interaction

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class AdminCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.check(is_admin)
    @app_commands.command(name="setup", description="Setup SpellBot on your server.")
    @traced_interaction()
    async def setup(self, interaction: discord.Interaction) -> None:
        async with AdminAction.create(self.bot, interaction) as action:
            await action.setup()

    @app_commands.check(is_admin)
    @app_commands.command(
        name="setup_mythic_track",
        description="Setup Mythic Track on your server.",
    )
    @traced_interaction()
    async def setup_mythic_track(self, interaction: discord.Interaction) -> None:
        async with AdminAction.create(self.bot, interaction) as action:
            await action.setup_mythic_track()

    @app_commands.check(is_admin)
    @app_commands.command(
        name="game_info",
        description="Get a link to a game's details page.",
    )
    @app_commands.describe(game_id="SpellBot ID of the game")
    @traced_interaction()
    async def game_info(self, interaction: discord.Interaction, game_id: str) -> None:
        async with AdminAction.create(self.bot, interaction) as action:
            await action.game_info(game_id)

    @app_commands.check(is_admin)
    @app_commands.command(name="move_user", description="Move one user's data to another user.")
    @app_commands.describe(from_user_id="User ID of the old user")
    @app_commands.describe(to_user_id="User ID of the new user")
    @traced_interaction()
    async def move_user(
        self,
        interaction: discord.Interaction,
        from_user_id: str,
        to_user_id: str,
    ) -> None:
        assert interaction.guild_id is not None
        # note: no user input validation is being done here
        from_user_xid = int(from_user_id)
        to_user_xid = int(to_user_id)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.move_user(
                guild_xid=interaction.guild_id,
                from_user_xid=from_user_xid,
                to_user_xid=to_user_xid,
            )

    @app_commands.check(is_mod)
    @app_commands.command(
        name="expire_games",
        description="Expire all inactive games on your server.",
    )
    @traced_interaction()
    async def expire_games(self, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        async with AdminAction.create(self.bot, interaction) as action:
            await action.expire_games(guild_xid=interaction.guild_id)

    @app_commands.check(is_mod)
    @app_commands.command(
        name="user_info",
        description="Get detailed information about a user (games played, blocks, etc.).",
    )
    @app_commands.describe(target="User to get info about")
    @traced_interaction()
    async def user_info(
        self,
        interaction: discord.Interaction,
        target: discord.User | discord.Member,
    ) -> None:
        async with AdminAction.create(self.bot, interaction) as action:
            await action.user_info(target=target)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(AdminCog(bot), guild=settings.GUILD_OBJECT)
