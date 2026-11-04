# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ddtrace.trace import tracer

from spellbot import services
from spellbot.data import ChannelModes, GameCriteria
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.i18n import guild_locale, t, user_locale
from spellbot.integrations import playgroup_live
from spellbot.models import MAX_RULES_LENGTH, GameStatus
from spellbot.operations import (
    safe_fetch_user,
    safe_followup_channel,
    safe_send_user,
)
from spellbot.settings import settings

from .base_action import BaseAction
from .game_posts import GamePosts
from .game_start import GameStart
from .guild_war import GuildWar

if TYPE_CHECKING:
    import discord

    from spellbot import SpellBot
    from spellbot.data import GameData

logger = logging.getLogger(__name__)

# Fewest players a force started game can have. `/start` shrinks the game to whoever is
# already queued, so below this there is no opponent and no link service will seat the table.
MIN_START_PLAYERS = 2


class LookingForGameAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)
        self.game_start = GameStart(self)
        self.game_posts = GamePosts(self)
        self.guild_war = GuildWar(self)

    async def block_if_no_player_linked(self, game_data: GameData) -> bool:
        if game_data.service != GameService.PLAYGROUP_LIVE.value:
            return False
        if playgroup_live.find_linked_player(game_data) is not None:
            return False
        locale = guild_locale(self.guild)
        await safe_followup_channel(
            self.interaction,
            t("lfg.playgroup_link_required", locale=locale),
        )
        return True

    def resolve_criteria(
        self,
        *,
        seats: int | None = None,
        rules: str | None = None,
        format: int | None = None,
        bracket: int | None = None,
        service: int | None = None,
        war_id: str | None = None,
        war_title: str | None = None,
    ) -> GameCriteria:
        """Fill in whatever the user didn't ask for from the channel's defaults."""
        if format is None:
            format = self.channel_data.default_format.value
        if format == GameFormat.CEDH.value:
            bracket = GameBracket.BRACKET_5.value
        elif format == GameFormat.PRE_CONS.value:
            bracket = GameBracket.BRACKET_2.value
        elif bracket is None:
            bracket = self.channel_data.default_bracket.value
        if service is None:
            service = self.channel_data.default_service.value
        requested_seats = seats or GameFormat(format).players
        return GameCriteria(
            seats=min(requested_seats, GameService(service).max_seats),
            format=format,
            bracket=bracket,
            service=service,
            rules=rules[:MAX_RULES_LENGTH] if rules else None,
            war_id=war_id,
            war_title=war_title,
        )

    @tracer.wrap()
    async def filter_friend_xids(self, friend_xids: list[int]) -> list[int]:
        assert self.guild
        if friend_xids:
            friend_xids = await self.ensure_users_exist(friend_xids)
        if friend_xids:
            friend_xids = await services.users.filter_blocked_list(
                self.interaction.user.id,
                friend_xids,
            )
        if friend_xids:
            friend_xids = await services.users.filter_pending_games(friend_xids)
        return friend_xids

    @tracer.wrap()
    async def upsert_game(
        self,
        *,
        author_xid: int,
        friend_xids: list[int],
        criteria: GameCriteria,
        create_new: bool = False,
    ) -> tuple[bool, GameData]:
        """Queue the players into a game matching `criteria`. Returns whether the game is new."""
        assert self.guild
        assert self.channel
        return await services.games.upsert(
            guild_xid=self.guild.id,
            channel_xid=self.channel.id,
            author_xid=author_xid,
            friends=friend_xids,
            criteria=criteria,
            modes=ChannelModes.from_channel(self.channel_data),
            locale=guild_locale(self.guild),
            create_new=create_new,
        )

    @tracer.wrap()
    async def join_game(self, message_xid: int) -> GameData | None:
        """Add the user to the game posted as `message_xid`, or tell them why they can't join."""
        found = await services.games.get_by_message_xid(message_xid)
        locale = found.locale if found else "en"
        # Tournament organizer mode disables block enforcement for this channel.
        enforce_blocks = not self.channel_data.to_mode
        if not found or (
            enforce_blocks and await services.games.blocked(found, self.interaction.user.id)
        ):
            await safe_send_user(self.interaction.user, t("lfg.cannot_join", locale=locale))
            return None

        if found.status == GameStatus.STARTED.value:
            logger.warning("User tried to join a game that has already started.")
            await safe_send_user(self.interaction.user, t("lfg.game_started", locale=locale))
            return None

        joined = await services.games.add_player(found, self.interaction.user.id)
        if joined is None:
            # The game filled up without yet being marked as started, this can happen
            await safe_send_user(self.interaction.user, t("lfg.game_full", locale=locale))
        return joined

    async def reply(self, message: str, *, origin: bool) -> None:
        """Reply privately to a button click, or in the channel to a command."""
        if origin:
            await safe_send_user(self.interaction.user, message)
        else:
            await safe_followup_channel(self.interaction, message)

    @tracer.wrap()
    async def execute_rematch(self) -> None:
        locale = guild_locale(self.guild)
        if not self.guild or not self.channel:
            # Someone tried to lfg in a Discord thread rather than in the channel itself.
            await safe_send_user(
                self.interaction.user,
                t("lfg.run_in_channel", locale=locale),
            )
            return

        assert self.user_data is not None
        if await services.users.pending_games(self.user_data):
            await safe_followup_channel(
                self.interaction,
                t("lfg.already_pending", locale=locale),
            )
            return

        game_data = await services.games.get_last_game(
            user_xid=self.interaction.user.id,
            guild_xid=self.guild.id,
        )
        if not game_data:
            await safe_followup_channel(
                self.interaction,
                t("lfg.no_previous_game", locale=locale),
            )
            return

        player_xids = [player.xid for player in game_data.players]
        players = " ".join(f"<@{xid}>" for xid in player_xids)

        await self.create_game(
            players=players,
            format=game_data.format,
            bracket=game_data.bracket,
            service=GameService.NOT_ANY.value,
            rematch=True,
        )

    @tracer.wrap()
    async def execute_start(self) -> None:
        locale = user_locale(self.interaction)
        if not self.guild or not self.channel:
            await safe_send_user(
                self.interaction.user,
                t("lfg.run_in_game_channel", locale=locale),
                ephemeral=True,
            )
            return

        assert self.user_data
        game_data = await services.users.is_waiting(self.user_data, self.channel.id)
        if not game_data:
            await safe_followup_channel(
                self.interaction,
                t("lfg.not_pending_here", locale=locale),
                ephemeral=True,
            )
            return

        if await self.block_if_no_player_linked(game_data):
            return

        # Force starting shrinks the game to the players already queued, and a game of one is
        # not a game: nobody has anyone to play against, and the link services reject a table
        # seating fewer than two. Stop here rather than burn a game link on it.
        if len(game_data.players) < MIN_START_PLAYERS:
            await safe_followup_channel(
                self.interaction,
                t("lfg.start_needs_players", locale=locale),
                ephemeral=True,
            )
            return

        original_seats = (
            game_data.seats if game_data.service == GameService.PLAYGROUP_LIVE.value else None
        )
        game_data = await services.games.shrink_game(game_data)
        await self.game_start.start_game(
            game_data,
            new=False,
            origin=False,
            force_start=True,
            original_seats=original_seats,
        )

    @tracer.wrap()
    async def execute(
        self,
        *,
        friends: str | None = None,
        seats: int | None = None,
        rules: str | None = None,
        format: int | None = None,
        bracket: int | None = None,
        service: int | None = None,
        message_xid: int | None = None,
        guild_war: str | None = None,
    ) -> None:
        """Handle `/lfg` (no `message_xid`) or a click on a game's Join button."""
        locale = guild_locale(self.guild)
        if not self.guild or not self.channel:
            # Someone tried to lfg in a Discord thread rather than in the channel itself.
            await safe_send_user(
                self.interaction.user,
                t("lfg.unsupported_context", locale=locale),
            )
            return

        game_data: GameData | None
        if message_xid is not None:
            if await self.reject_if_busy(locale, origin=True):
                return
            new, game_data = False, await self.join_game(message_xid)
        else:
            new, game_data = await self.execute_command(
                friends=friends,
                seats=seats,
                rules=rules,
                format=format,
                bracket=bracket,
                service=service,
                guild_war=guild_war,
                locale=locale,
            )
        if game_data is None:
            return

        origin = message_xid is not None
        if game_data.fully_seated:
            if await self.block_if_no_player_linked(game_data):
                return
            await self.game_start.start_game(game_data, new=new, origin=origin)
            return
        game_data = await self.guild_war.ensure_guild_war_convoke_link(game_data)
        await self.game_posts.handle_embed_creation(game_data, new=new, origin=origin)

    async def execute_command(
        self,
        *,
        friends: str | None,
        seats: int | None,
        rules: str | None,
        format: int | None,
        bracket: int | None,
        service: int | None,
        guild_war: str | None,
        locale: str,
    ) -> tuple[bool, GameData | None]:
        """Queue the user and their friends for a game matching their `/lfg` options."""
        resolved = await self.guild_war.resolve_guild_war(
            guild_war,
            service=service,
            seats=seats,
            locale=locale,
        )
        if resolved is None:
            return False, None
        war_id, war_title, service, seats = resolved
        criteria = self.resolve_criteria(
            seats=seats,
            rules=rules,
            format=format,
            bracket=bracket,
            service=service,
            war_id=war_id,
            war_title=war_title,
        )
        if await self.reject_if_busy(locale, origin=False):
            return False, None

        friend_xids = list(map(int, re.findall(r"<@!?(\d+)>", friends or "")))
        if len(friend_xids) + 1 > criteria.seats:
            await safe_send_user(self.interaction.user, t("lfg.too_many_friends", locale=locale))
            return False, None

        return await self.upsert_game(
            author_xid=self.interaction.user.id,
            friend_xids=await self.filter_friend_xids(friend_xids),
            criteria=criteria,
        )

    async def reject_if_busy(self, locale: str, *, origin: bool) -> bool:
        """Tell the user and return True if they can't queue for another game right now."""
        assert self.channel
        assert self.user_data
        if await services.users.is_waiting(self.user_data, self.channel.id):
            await self.reply(t("lfg.already_in_channel", locale=locale), origin=origin)
            return True
        if await services.users.pending_games(self.user_data) + 1 > settings.MAX_PENDING_GAMES:
            await self.reply(t("lfg.too_many_pending", locale=locale), origin=origin)
            return True
        return False

    @tracer.wrap()
    async def create_game(
        self,
        players: str,
        format: int | None = None,
        bracket: int | None = None,
        service: int | None = None,
        rematch: bool = False,
    ) -> None:
        assert self.channel
        locale = guild_locale(self.guild)

        game_format = GameFormat(format or GameFormat.COMMANDER.value)
        game_bracket = GameBracket(bracket or GameBracket.NONE.value)
        game_service = GameService(service or GameService.CONVOKE.value)
        player_xids = list(map(int, re.findall(r"<@!?(\d+)>", players)))
        requested_seats = len(player_xids)
        if requested_seats < 2 or requested_seats > game_format.players:
            await safe_followup_channel(
                self.interaction,
                t(
                    "lfg.invalid_player_count",
                    locale=locale,
                    format=str(game_format),
                    count=requested_seats,
                ),
            )
            return

        found_players: list[int] = []
        found_players = await self.ensure_users_exist(player_xids, exclude_self=False)

        if len(found_players) != requested_seats:
            excluded_player_xids = set(player_xids) - set(found_players)
            excluded_players_s = ", ".join(f"<@{xid}>" for xid in excluded_player_xids)
            await safe_followup_channel(
                self.interaction,
                t("lfg.excluded_players", locale=locale, players=excluded_players_s),
            )
            return

        _, game_data = await self.upsert_game(
            author_xid=found_players[0],
            friend_xids=found_players[1:],
            criteria=GameCriteria(
                seats=requested_seats,
                format=game_format.value,
                bracket=game_bracket.value,
                service=game_service.value,
            ),
            create_new=True,
        )
        await self.game_start.start_game(game_data, new=True, origin=False, rematch=rematch)

    @tracer.wrap()
    async def ensure_users_exist(
        self,
        user_xids: list[int],
        *,
        exclude_self: bool = True,
    ) -> list[int]:
        """
        Ensure DB users exist for the given list of external IDs.

        When exclude_self is True, don't create a user for IDs matching the author's.
        """
        found_users: list[int] = []
        guild_xid = self.interaction.guild_id
        for user_xid in user_xids:
            if exclude_self and user_xid == self.interaction.user.id:
                continue
            user = await safe_fetch_user(self.bot, user_xid)
            if not user:
                continue
            user_data = await services.users.upsert(user, guild_xid=guild_xid)
            if user_data.banned:
                continue
            found_users.append(user_xid)
        return found_users
