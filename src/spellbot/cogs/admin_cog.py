# pylint: disable=too-many-arguments
import logging
from typing import Optional

import discord
from ddtrace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from .. import SpellBot
from ..actions import AdminAction
from ..metrics import add_span_context
from ..utils import for_all_callbacks, is_admin, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_admin))
@for_all_callbacks(app_commands.check(is_guild))
class AdminCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup SpellBot on your server.")
    @tracer.wrap(name="interaction", resource="setup")
    async def setup(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.setup()

    set_group = app_commands.Group(name="set", description="...")

    @set_group.command(
        name="motd",
        description="Set your server's message of the day. Leave blank to unset.",
    )
    @app_commands.describe(message="Message content")
    @tracer.wrap(name="interaction", resource="set_motd")
    async def motd(self, interaction: discord.Interaction, message: Optional[str] = None) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_motd(message)

    @set_group.command(
        name="channel_motd",
        description="Set this channel's message of the day. Leave blank to unset.",
    )
    @tracer.wrap(name="interaction", resource="set_channel_motd")
    async def channel_motd(
        self,
        interaction: discord.Interaction,
        message: Optional[str] = None,
    ) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_channel_motd(message)

    @app_commands.command(
        name="channels",
        description="Show the current configurations for channels on your server.",
    )
    @app_commands.describe(page="If there are multiple pages of output, which one?")
    @tracer.wrap(name="interaction", resource="channels")
    async def channels(self, interaction: discord.Interaction, page: Optional[int] = 1) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            assert page and page >= 1
            await action.channels(page=page)

    @app_commands.command(name="awards", description="Setup player awards on your server.")
    @app_commands.describe(page="If there are multiple pages of output, which one?")
    @tracer.wrap(name="interaction", resource="awards")
    async def awards(self, interaction: discord.Interaction, page: Optional[int] = 1) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            assert page and page >= 1
            await action.awards(page=page)

    award_group = app_commands.Group(name="award", description="...")

    @award_group.command(name="add", description="Add a new award level to the list of awards.")
    @app_commands.describe(count="The number of games needed for this award")
    @app_commands.describe(role="The role to assign when a player gets this award")
    @app_commands.describe(message="The message to send players you get this award")
    @app_commands.describe(repeating="Repeatedly give this award every X games?")
    @app_commands.describe(
        remove="Instead of assigning the role, remove it from the player",
    )
    @tracer.wrap(name="interaction", resource="award_add")
    async def award_add(
        self,
        interaction: discord.Interaction,
        count: int,
        role: discord.Role,
        message: str,
        repeating: Optional[bool] = False,
        remove: Optional[bool] = False,
        verified_only: Optional[bool] = False,
        unverified_only: Optional[bool] = False,
    ) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.award_add(
                count,
                str(role),
                message,
                repeating=repeating,
                remove=remove,
                verified_only=verified_only,
                unverified_only=unverified_only,
            )

    @award_group.command(
        name="delete",
        description="Delete an existing award level from the server.",
    )
    @app_commands.describe(id="The ID number of the award to delete")
    @tracer.wrap(name="interaction", resource="award_delete")
    async def award_delete(self, interaction: discord.Interaction, id: int) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.award_delete(id)

    @set_group.command(
        name="default_seats",
        description="Set the default number of seats for new games in this channel.",
    )
    @app_commands.describe(seats="Default number of seats")
    @app_commands.choices(
        seats=[
            Choice(name="2", value=2),
            Choice(name="3", value=3),
            Choice(name="4", value=4),
        ],
    )
    @tracer.wrap(name="interaction", resource="set_default_seats")
    async def default_seats(self, interaction: discord.Interaction, seats: int) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_default_seats(seats)

    @set_group.command(
        name="auto_verify",
        description="Should posting in this channel automatically verify users?",
    )
    @app_commands.describe(setting="Setting")
    @tracer.wrap(name="interaction", resource="set_auto_verify")
    async def auto_verify(self, interaction: discord.Interaction, setting: bool) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_auto_verify(setting)

    @set_group.command(
        name="verified_only",
        description="Should only verified users be allowed to post in this channel?",
    )
    @app_commands.describe(setting="Setting")
    @tracer.wrap(name="interaction", resource="set_verified_only")
    async def verified_only(self, interaction: discord.Interaction, setting: bool) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_verified_only(setting)

    @set_group.command(
        name="unverified_only",
        description="Should only unverified users be allowed to post in this channel?",
    )
    @app_commands.describe(setting="Setting")
    @tracer.wrap(name="interaction", resource="set_unverified_only")
    async def unverified_only(self, interaction: discord.Interaction, setting: bool) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_unverified_only(setting)

    @app_commands.command(name="info", description="Request a DM with full game information.")
    @app_commands.describe(game_id="SpellBot ID of the game")
    @tracer.wrap(name="interaction", resource="info")
    async def info(self, interaction: discord.Interaction, game_id: str) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.info(game_id)

    @set_group.command(
        name="voice_category",
        description="Set the voice category prefix for games in this channel.",
    )
    @app_commands.describe(prefix="Setting")
    @tracer.wrap(name="interaction", resource="set_voice_category")
    async def voice_category(self, interaction: discord.Interaction, prefix: str) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_voice_category(prefix)

    @set_group.command(
        name="delete_expired",
        description="Set the option for deleting expired games in this channel.",
    )
    @app_commands.describe(setting="Setting")
    @tracer.wrap(name="interaction", resource="set_delete_expired")
    async def delete_expired(self, interaction: discord.Interaction, setting: bool) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_delete_expired(setting)

    @set_group.command(
        name="show_points",
        description="Set the option for showing points on games in this channel.",
    )
    @app_commands.describe(setting="Setting")
    @tracer.wrap(name="interaction", resource="set_show_points")
    async def show_points(self, interaction: discord.Interaction, setting: bool) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_show_points(setting)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(AdminCog(bot), guild=bot.settings.GUILD_OBJECT)
