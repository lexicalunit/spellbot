from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from spellbot.actions import AdminAction
from spellbot.enums import GAME_BRACKET_ORDER, GAME_FORMAT_ORDER, GAME_SERVICE_ORDER
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_admin, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_admin))
@for_all_callbacks(app_commands.check(is_guild))
class AdminCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(name="setup", description="Setup SpellBot on your server.")
    @tracer.wrap(name="interaction", resource="setup")
    async def setup(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.setup()

    @app_commands.command(
        name="setup_mythic_track",
        description="Setup Mythic Track on your server.",
    )
    @tracer.wrap(name="interaction", resource="setup")
    async def setup_mythic_track(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.setup_mythic_track()

    @app_commands.command(name="forget_channel", description="Forget settings for a channel.")
    @app_commands.describe(channel="What is the Discord ID of the channel?")
    @tracer.wrap(name="interaction", resource="forget_channel")
    async def forget_channel(self, interaction: discord.Interaction, channel: str) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.forget_channel(channel)

    set_group = app_commands.Group(name="set", description="...")

    @set_group.command(
        name="suggest_vc_category",
        description="Set the category prefix to use for suggested voice channels.",
    )
    @app_commands.describe(category="Category prefix")
    @tracer.wrap(name="interaction", resource="set_suggest_vc_category")
    async def set_suggest_vc_category(
        self,
        interaction: discord.Interaction,
        category: str | None = None,
    ) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_suggest_vc_category(category)

    @set_group.command(
        name="motd",
        description="Set your server's message of the day. Leave blank to unset.",
    )
    @app_commands.describe(message="Message content")
    @tracer.wrap(name="interaction", resource="set_motd")
    async def motd(self, interaction: discord.Interaction, message: str | None = None) -> None:
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
        message: str | None = None,
    ) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_channel_motd(message)

    @set_group.command(
        name="channel_extra",
        description="Set this channel's extra message. Leave blank to unset.",
    )
    @tracer.wrap(name="interaction", resource="set_channel_extra")
    async def channel_extra(
        self,
        interaction: discord.Interaction,
        message: str | None = None,
    ) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_channel_extra(message)

    @app_commands.command(
        name="channels",
        description="Show the current configurations for channels on your server.",
    )
    @app_commands.describe(page="If there are multiple pages of output, which one?")
    @tracer.wrap(name="interaction", resource="channels")
    async def channels(self, interaction: discord.Interaction, page: int | None = 1) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            page = page or 1
            await action.channels(page=page)

    @app_commands.command(name="awards", description="Setup player awards on your server.")
    @app_commands.describe(page="If there are multiple pages of output, which one?")
    @tracer.wrap(name="interaction", resource="awards")
    async def awards(self, interaction: discord.Interaction, page: int | None = 1) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            page = page or 1
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
    # @tracer.wrap(name="interaction", resource="award_add")
    # There's a bug when combining `@tracer.wrap`, `@app_commands.describe` and discord.Role.
    # See: https://github.com/Rapptz/discord.py/issues/10317.
    async def award_add(
        self,
        interaction: discord.Interaction,
        count: int,
        role: discord.Role,
        message: str,
        repeating: bool | None = False,
        remove: bool | None = False,
        verified_only: bool | None = False,
        unverified_only: bool | None = False,
    ) -> None:
        with tracer.trace("interaction", resource="award_add"):
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
        name="default_format",
        description="Set the default game format for new games in this channel.",
    )
    @app_commands.describe(format="Default game format")
    @app_commands.choices(
        format=[Choice(name=str(format), value=format.value) for format in GAME_FORMAT_ORDER],
    )
    @tracer.wrap(name="interaction", resource="set_default_format")
    async def default_format(self, interaction: discord.Interaction, format: int) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_default_format(format)

    @set_group.command(
        name="default_bracket",
        description="Set the default commander bracket for new games in this channel.",
    )
    @app_commands.describe(bracket="Default commander bracket")
    @app_commands.choices(
        bracket=[Choice(name=str(bracket), value=bracket.value) for bracket in GAME_BRACKET_ORDER],
    )
    @tracer.wrap(name="interaction", resource="set_default_format")
    async def default_bracket(self, interaction: discord.Interaction, bracket: int) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_default_bracket(bracket)

    @set_group.command(
        name="default_service",
        description="Set the default game service for new games in this channel.",
    )
    @app_commands.describe(service="Default service")
    @app_commands.choices(
        service=[Choice(name=str(service), value=service.value) for service in GAME_SERVICE_ORDER],
    )
    @tracer.wrap(name="interaction", resource="set_default_service")
    async def default_service(self, interaction: discord.Interaction, service: int) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_default_service(service)

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
        name="blind_games",
        description="Should player names be hidden in public game posts?",
    )
    @app_commands.describe(setting="Setting")
    @tracer.wrap(name="interaction", resource="set_blind_games")
    async def blind_games(self, interaction: discord.Interaction, setting: bool) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_blind_games(setting)

    @set_group.command(
        name="voice_invite",
        description="Set the option for voice invite creation on games in this channel.",
    )
    @app_commands.describe(setting="Setting")
    @tracer.wrap(name="interaction", resource="set_voice_invite")
    async def voice_invite(self, interaction: discord.Interaction, setting: bool) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_voice_invite(setting)

    @app_commands.command(name="move_user", description="Move one user's data to another user.")
    @tracer.wrap(name="interaction", resource="move_user")
    @app_commands.describe(from_user_id="User ID of the old user")
    @app_commands.describe(to_user_id="User ID of the new user")
    async def move_user(
        self,
        interaction: discord.Interaction,
        from_user_id: str,
        to_user_id: str,
    ) -> None:  # pragma: no cover
        add_span_context(interaction)
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


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(AdminCog(bot), guild=settings.GUILD_OBJECT)
