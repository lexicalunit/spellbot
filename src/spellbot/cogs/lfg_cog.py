from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from spellbot.actions.lfg_action import LookingForGameAction
from spellbot.enums import (
    GAME_BRACKET_ORDER,
    GAME_FORMAT_ORDER,
    GAME_SERVICE_ORDER,
    GameService,
)
from spellbot.integrations import convoke
from spellbot.metrics import add_span_context
from spellbot.operations import safe_defer_interaction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


async def guild_war_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[Choice[str]]:
    """Autocomplete live Convoke Guild Wars for /war."""
    wars = await convoke.get_live_guild_wars()
    needle = current.strip().lower()
    choices: list[Choice[str]] = []
    for war in wars:
        label = war["title"]
        if needle and needle not in label.lower() and needle not in war["slug"].lower():
            continue
        # Note: Discord choice names max out at 100 characters.
        name = label if len(label) <= 100 else f"{label[:97]}..."
        choices.append(Choice(name=name, value=war["id"]))
        if len(choices) >= 25:
            break
    return choices


@for_all_callbacks(app_commands.check(is_guild))
class LookingForGameCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(name="lfg", description="Looking for game.")
    @app_commands.describe(friends="Mention friends to join this game with.")
    @app_commands.describe(seats="How many players can be seated at this game?")
    @app_commands.choices(
        seats=[
            Choice(name="2", value=2),
            Choice(name="3", value=3),
            Choice(name="4", value=4),
            Choice(name="5", value=5),
            Choice(name="6", value=6),
            Choice(name="7", value=7),
            Choice(name="8", value=8),
            Choice(name="9", value=9),
            Choice(name="10", value=10),
        ],
    )
    @app_commands.describe(rules="Any additional rules or requests for this game.")
    @app_commands.describe(service="What service do you want to use to play this game?")
    @app_commands.choices(
        service=[Choice(name=str(service), value=service.value) for service in GAME_SERVICE_ORDER],
    )
    @app_commands.describe(format="What game format do you want to play?")
    @app_commands.choices(
        format=[Choice(name=str(format), value=format.value) for format in GAME_FORMAT_ORDER],
    )
    @app_commands.describe(bracket="What commander bracket do you want to play?")
    @app_commands.choices(
        bracket=[Choice(name=str(bracket), value=bracket.value) for bracket in GAME_BRACKET_ORDER],
    )
    @tracer.wrap(name="interaction", resource="lfg")
    async def lfg(
        self,
        interaction: discord.Interaction,
        friends: str | None = None,
        seats: int | None = None,
        rules: str | None = None,
        service: int | None = None,
        format: int | None = None,
        bracket: int | None = None,
    ) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        if not await safe_defer_interaction(interaction):  # pragma: no cover
            return
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LookingForGameAction.create(self.bot, interaction) as action,
        ):
            await action.execute(
                friends=friends,
                seats=seats,
                rules=rules,
                format=format,
                bracket=bracket,
                service=service,
            )

    @app_commands.command(name="war", description="Looking for a Convoke Guild War game.")
    @app_commands.describe(war="Which live Guild War is this game for?")
    @app_commands.autocomplete(war=guild_war_autocomplete)
    @app_commands.describe(friends="Mention friends to join this game with.")
    @app_commands.describe(seats="How many players can be seated at this game?")
    @app_commands.choices(
        seats=[
            Choice(name=str(count), value=count)
            for count in range(convoke.MIN_WAR_SEATS, convoke.MAX_WAR_SEATS + 1)
        ],
    )
    @app_commands.describe(rules="Any additional rules or requests for this game.")
    @app_commands.describe(format="What game format do you want to play?")
    @app_commands.choices(
        format=[Choice(name=str(format), value=format.value) for format in GAME_FORMAT_ORDER],
    )
    @app_commands.describe(bracket="What commander bracket do you want to play?")
    @app_commands.choices(
        bracket=[Choice(name=str(bracket), value=bracket.value) for bracket in GAME_BRACKET_ORDER],
    )
    @tracer.wrap(name="interaction", resource="war")
    async def war(
        self,
        interaction: discord.Interaction,
        war: str,
        friends: str | None = None,
        seats: int | None = None,
        rules: str | None = None,
        format: int | None = None,
        bracket: int | None = None,
    ) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        if not await safe_defer_interaction(interaction):  # pragma: no cover
            return
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LookingForGameAction.create(self.bot, interaction) as action,
        ):
            await action.execute(
                friends=friends,
                seats=seats,
                rules=rules,
                format=format,
                bracket=bracket,
                service=GameService.CONVOKE.value,
                guild_war=war,
            )

    @app_commands.command(name="rematch", description="Play another game with the last group.")
    @tracer.wrap(name="interaction", resource="rematch")
    async def rematch(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        if not await safe_defer_interaction(interaction):  # pragma: no cover
            return
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LookingForGameAction.create(self.bot, interaction) as action,
        ):
            await action.execute_rematch()

    @app_commands.command(name="start", description="Start your current game immediately.")
    @tracer.wrap(name="interaction", resource="start")
    async def start(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        if not await safe_defer_interaction(interaction):  # pragma: no cover
            return
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LookingForGameAction.create(self.bot, interaction) as action,
        ):
            await action.execute_start()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(LookingForGameCog(bot), guild=settings.GUILD_OBJECT)
