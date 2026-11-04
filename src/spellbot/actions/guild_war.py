# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

from spellbot import services
from spellbot.enums import GameService
from spellbot.i18n import t
from spellbot.integrations import convoke
from spellbot.operations import safe_followup_channel

if TYPE_CHECKING:
    from spellbot.data import GameData

    from .lfg_action import LookingForGameAction


class GuildWar:
    """Guild War handling for a `LookingForGameAction`; Guild Wars only exist on Convoke."""

    def __init__(self, action: LookingForGameAction) -> None:
        self.action = action

    async def reply_guild_war_seats(self, locale: str) -> None:
        """Tell the user a Guild War game can not be seated the way they asked."""
        await safe_followup_channel(
            self.action.interaction,
            t(
                "lfg.guild_war_seats",
                locale=locale,
                min=convoke.MIN_WAR_SEATS,
                max=convoke.MAX_WAR_SEATS,
            ),
        )

    async def resolve_guild_war(
        self,
        guild_war: str | None,
        *,
        service: int | None,
        seats: int | None,
        locale: str,
    ) -> tuple[str | None, str | None, int | None, int | None] | None:
        """
        Resolve the optional `/war` guild war into Convoke war fields.

        Returns (war_id, war_title, service, seats), or None when an error reply
        was already sent to the user. Guild Wars only exist on Convoke, so a war game
        always comes back as a Convoke game whatever service was asked for, seated
        within the bounds Convoke allows. Since the seat count returned here is always
        in range, nothing downstream needs to re-check it — `resolve_criteria` can only shrink
        it further, and a war game never falls back to the channel's default seats.
        """
        if not guild_war:
            return None, None, service, seats

        live_war = await convoke.resolve_live_guild_war(guild_war.strip())
        if live_war is None:
            await safe_followup_channel(
                self.action.interaction,
                t("lfg.guild_war_invalid", locale=locale),
            )
            return None

        if seats is not None and not convoke.MIN_WAR_SEATS <= seats <= convoke.MAX_WAR_SEATS:
            await self.reply_guild_war_seats(locale)
            return None

        return (
            live_war["id"],
            live_war["title"],
            GameService.CONVOKE.value,
            seats or convoke.DEFAULT_WAR_SEATS,
        )

    async def ensure_guild_war_convoke_link(self, game_data: GameData) -> GameData:
        """Open the Convoke table as soon as a Guild War /lfg queue exists."""
        if not game_data.war_id or game_data.game_link:
            return game_data
        # No pins yet: players only get theirs once the queue fills, and `make_game_ready()`
        # sends them to Convoke along with the final roster.
        details = await self.action.bot.create_game_link(game_data)
        if not details.link:
            return game_data
        return await services.games.attach_game_link(game_data, details)
