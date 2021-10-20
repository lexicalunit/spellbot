import logging
from typing import Optional, Union

import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.context import ComponentContext
from discord_slash.model import SlashCommandOptionType

from spellbot.client import SpellBot
from spellbot.interactions.admin_interaction import AdminInteraction
from spellbot.interactions.config_interaction import ConfigInteraction
from spellbot.interactions.watch_interaction import WatchInteraction
from spellbot.utils import for_all_callbacks, is_admin

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.check(is_admin))
@for_all_callbacks(commands.guild_only())
class AdminCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(name="setup", description="Setup SpellBot on your server.")
    async def setup(self, ctx: SlashContext):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.setup()

    @cog_ext.cog_component()
    async def refresh_setup(self, ctx: ComponentContext):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.refresh_setup()

    @cog_ext.cog_component()
    async def toggle_show_links(self, ctx: ComponentContext):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.toggle_show_links()

    @cog_ext.cog_component()
    async def toggle_show_points(self, ctx: ComponentContext):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.toggle_show_points()

    @cog_ext.cog_component()
    async def toggle_voice_create(self, ctx: ComponentContext):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.toggle_voice_create()

    @cog_ext.cog_subcommand(
        base="set",
        name="motd",
        description="Set your server's message of the day.",
        options=[
            {
                "name": "message",
                "required": True,
                "description": "Message content",
                "type": SlashCommandOptionType.STRING.value,
            },
        ],
    )
    async def motd(self, ctx: SlashContext, message: str):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_motd(message)

    @cog_ext.cog_slash(
        name="channels",
        description="Show the current configurations for channels on your server.",
    )
    async def channels(self, ctx: SlashContext):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.channels()

    @cog_ext.cog_slash(
        name="awards",
        description="Setup player awards on your server.",
    )
    async def awards(self, ctx: SlashContext):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.awards()

    @cog_ext.cog_subcommand(
        base="award",
        name="add",
        description="Add a new award level to the list of awards.",
        options=[
            {
                "name": "count",
                "required": True,
                "description": "The number of games needed for this award",
                "type": SlashCommandOptionType.INTEGER.value,
            },
            {
                "name": "role",
                "required": True,
                "description": "The role to assign when a player gets this award",
                "type": SlashCommandOptionType.ROLE.value,
            },
            {
                "name": "message",
                "required": True,
                "description": "The message to send players you get this award",
                "type": SlashCommandOptionType.STRING.value,
            },
            {
                "name": "repeating",
                "required": False,
                "description": "Repeatedly give this award every X games?",
                "type": SlashCommandOptionType.BOOLEAN.value,
            },
        ],
    )
    async def award_add(
        self,
        ctx: SlashContext,
        count: int,
        role: discord.Role,
        message: str,
        repeating: Optional[bool] = False,
    ):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.award_add(count, str(role), message, repeating)

    @cog_ext.cog_subcommand(
        base="award",
        name="delete",
        description="Delete an existing award level from the server.",
        options=[
            {
                "name": "id",
                "required": True,
                "description": "The ID number of the award to delete",
                "type": SlashCommandOptionType.INTEGER.value,
            },
        ],
    )
    async def award_delete(self, ctx: SlashContext, id: int):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.award_delete(id)

    @cog_ext.cog_subcommand(
        base="set",
        name="default_seats",
        description="Set the default number of seats for new games in this channel.",
        options=[
            {
                "name": "seats",
                "required": True,
                "description": "Default number of seats",
                "type": SlashCommandOptionType.INTEGER.value,
                "choices": [
                    {"name": "2", "value": 2},
                    {"name": "3", "value": 3},
                    {"name": "4", "value": 4},
                ],
            },
        ],
    )
    async def default_seats(self, ctx: SlashContext, seats: int):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_default_seats(seats)

    @cog_ext.cog_subcommand(
        base="set",
        name="auto_verify",
        description="Should posting in this channel automatically verify users?",
        options=[
            {
                "name": "setting",
                "required": True,
                "description": "Setting",
                "type": SlashCommandOptionType.BOOLEAN.value,
            },
        ],
    )
    async def auto_verify(self, ctx: SlashContext, setting: bool):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_auto_verify(setting)

    @cog_ext.cog_subcommand(
        base="set",
        name="verified_only",
        description="Should only verified users be allowed to post in this channel?",
        options=[
            {
                "name": "setting",
                "required": True,
                "description": "Setting",
                "type": SlashCommandOptionType.BOOLEAN.value,
            },
        ],
    )
    async def verified_only(self, ctx: SlashContext, setting: bool):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_verified_only(setting)

    @cog_ext.cog_subcommand(
        base="set",
        name="unverified_only",
        description="Should only unverified users be allowed to post in this channel?",
        options=[
            {
                "name": "setting",
                "required": True,
                "description": "Setting",
                "type": SlashCommandOptionType.BOOLEAN.value,
            },
        ],
    )
    async def unverified_only(self, ctx: SlashContext, setting: bool):
        async with ConfigInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_unverified_only(setting)

    @cog_ext.cog_slash(
        name="info",
        description="Request a DM with full game information.",
        options=[
            {
                "name": "game_id",
                "required": True,
                "description": "SpellBot ID of the game",
                "type": SlashCommandOptionType.STRING.value,
            },
        ],
    )
    async def info(self, ctx: SlashContext, game_id: str):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.info(game_id)

    @cog_ext.cog_slash(
        name="watched",
        description="View the current list of watched users with notes.",
    )
    async def watched(self, ctx: SlashContext):
        async with WatchInteraction.create(self.bot, ctx) as interaction:
            await interaction.watched()

    @cog_ext.cog_slash(
        name="watch",
        description="Moderators should receive notifications about this user's activity.",
        options=[
            {
                "name": "target",
                "required": True,
                "description": "User to watch",
                "type": SlashCommandOptionType.USER.value,
            },
            {
                "name": "note",
                "required": False,
                "description": "A note about why this using is being watched",
                "type": SlashCommandOptionType.STRING.value,
            },
        ],
    )
    async def watch(
        self,
        ctx: SlashContext,
        target: Union[discord.User, discord.Member],
        note: Optional[str] = None,
    ):
        async with WatchInteraction.create(self.bot, ctx) as interaction:
            await interaction.watch(target=target, note=note)

    @cog_ext.cog_slash(
        name="unwatch",
        description="No longer receive notifications about this user's activity.",
        options=[
            {
                "name": "target",
                "required": True,
                "description": "User to unwatch",
                "type": SlashCommandOptionType.USER.value,
            },
        ],
    )
    async def unwatch(
        self,
        ctx: SlashContext,
        target: Union[discord.User, discord.Member],
    ):
        async with WatchInteraction.create(self.bot, ctx) as interaction:
            await interaction.unwatch(target=target)


def setup(bot: SpellBot):
    bot.add_cog(AdminCog(bot))
