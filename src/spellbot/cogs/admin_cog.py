# pylint: disable=too-many-arguments

import logging
from typing import Optional

import discord
from ddtrace import tracer
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.context import ComponentContext
from discord_slash.model import SlashCommandOptionType

from .. import SpellBot
from ..interactions import AdminInteraction
from ..utils import for_all_callbacks, is_admin

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.check(is_admin))
@for_all_callbacks(commands.guild_only())
class AdminCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(name="setup", description="Setup SpellBot on your server.")
    @tracer.wrap(name="command", resource="setup")
    async def setup(self, ctx: SlashContext):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.setup()

    @cog_ext.cog_component()
    @tracer.wrap(name="command", resource="refresh_setup")
    async def refresh_setup(self, ctx: ComponentContext):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.refresh_setup()

    @cog_ext.cog_component()
    @tracer.wrap(name="command", resource="toggle_show_links")
    async def toggle_show_links(self, ctx: ComponentContext):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.toggle_show_links()

    @cog_ext.cog_component()
    @tracer.wrap(name="command", resource="toggle_show_points")
    async def toggle_show_points(self, ctx: ComponentContext):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.toggle_show_points()

    @cog_ext.cog_component()
    @tracer.wrap(name="command", resource="toggle_voice_create")
    async def toggle_voice_create(self, ctx: ComponentContext):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.toggle_voice_create()

    @cog_ext.cog_subcommand(
        base="set",
        name="motd",
        description="Set your server's message of the day. Leave blank to unset.",
        options=[
            {
                "name": "message",
                "required": False,
                "description": "Message content",
                "type": SlashCommandOptionType.STRING.value,
            },
        ],
    )
    @tracer.wrap(name="command", resource="set_motd")
    async def motd(self, ctx: SlashContext, message: Optional[str] = None):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_motd(message)

    @cog_ext.cog_subcommand(
        base="set",
        name="channel_motd",
        description="Set this channel's message of the day. Leave blank to unset.",
        options=[
            {
                "name": "message",
                "required": False,
                "description": "Message content",
                "type": SlashCommandOptionType.STRING.value,
            },
        ],
    )
    @tracer.wrap(name="command", resource="set_channel_motd")
    async def channel_motd(self, ctx: SlashContext, message: Optional[str] = None):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_channel_motd(message)

    @cog_ext.cog_slash(
        name="channels",
        description="Show the current configurations for channels on your server.",
    )
    @tracer.wrap(name="command", resource="channels")
    async def channels(self, ctx: SlashContext):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.channels()

    @cog_ext.cog_slash(
        name="awards",
        description="Setup player awards on your server.",
    )
    @tracer.wrap(name="command", resource="awards")
    async def awards(self, ctx: SlashContext):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
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
    @tracer.wrap(name="command", resource="award_add")
    async def award_add(
        self,
        ctx: SlashContext,
        count: int,
        role: discord.Role,
        message: str,
        repeating: Optional[bool] = False,
    ):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
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
    @tracer.wrap(name="command", resource="award_delete")
    async def award_delete(self, ctx: SlashContext, id: int):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
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
    @tracer.wrap(name="command", resource="set_default_seats")
    async def default_seats(self, ctx: SlashContext, seats: int):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
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
    @tracer.wrap(name="command", resource="set_auto_verify")
    async def auto_verify(self, ctx: SlashContext, setting: bool):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
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
    @tracer.wrap(name="command", resource="set_verified_only")
    async def verified_only(self, ctx: SlashContext, setting: bool):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
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
    @tracer.wrap(name="command", resource="set_unverified_only")
    async def unverified_only(self, ctx: SlashContext, setting: bool):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
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
    @tracer.wrap(name="command", resource="info")
    async def info(self, ctx: SlashContext, game_id: str):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.info(game_id)

    @cog_ext.cog_subcommand(
        base="set",
        name="voice_category",
        description="Set the voice category prefix for games in this channel.",
        options=[
            {
                "name": "prefix",
                "required": True,
                "description": "Setting",
                "type": SlashCommandOptionType.STRING.value,
            },
        ],
    )
    @tracer.wrap(name="command", resource="set_voice_category")
    async def voice_category(self, ctx: SlashContext, prefix: str):
        async with AdminInteraction.create(self.bot, ctx) as interaction:
            await interaction.set_voice_category(prefix)


def setup(bot: SpellBot):
    bot.add_cog(AdminCog(bot))
