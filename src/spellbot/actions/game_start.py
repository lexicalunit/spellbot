# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import TYPE_CHECKING

from ddtrace.trace import tracer

from spellbot import services
from spellbot.data import GameLinkDetails
from spellbot.enums import GameBracket
from spellbot.i18n import t
from spellbot.metrics import tag_span
from spellbot.models import generate_pin
from spellbot.operations import (
    VoiceChannelSuggestion,
    safe_add_role,
    safe_create_channel_invite,
    safe_create_voice_channel,
    safe_ensure_voice_category,
    safe_fetch_user,
    safe_followup_channel,
    safe_send_user,
    safe_suggest_voice_channel,
)

if TYPE_CHECKING:
    import discord

    from spellbot.data import GameData

    from .lfg_action import LookingForGameAction


class GameStart:
    """Start a fully seated game for a `LookingForGameAction`: link, voice, DMs and awards."""

    def __init__(self, action: LookingForGameAction) -> None:
        self.action = action

    @tracer.wrap()
    async def start_game(
        self,
        game_data: GameData,
        *,
        new: bool,
        origin: bool,
        rematch: bool = False,
        force_start: bool = False,
        original_seats: int | None = None,
    ) -> None:
        """Start a fully seated game: link it, post it, DM its players, and refresh their queues."""
        assert self.action.guild
        # Starting pulls the players out of every other queue, so those posts need a refresh.
        other_game_ids = await services.games.other_game_ids(game_data)
        game_data, suggested_vc = await self.make_game_ready(
            game_data,
            [player.xid for player in game_data.players],
            original_seats=original_seats,
        )
        game_data = await self.handle_voice_creation(game_data, self.action.guild.id)
        game_data = await self.action.game_posts.handle_embed_creation(
            game_data,
            new=new,
            origin=origin,
            suggested_vc=suggested_vc,
            rematch=rematch,
            force_start=force_start,
        )
        await self.handle_direct_messages(game_data, suggested_vc=suggested_vc, rematch=rematch)
        await self.action.game_posts.update_other_game_posts(other_game_ids)

    @tracer.wrap()
    async def make_game_ready(
        self,
        game_data: GameData,
        player_xids: list[int],
        original_seats: int | None = None,
    ) -> tuple[GameData, VoiceChannelSuggestion | None]:
        # Convoke needs player pins, so we have to generate them before creating the game link.
        # Initially the design was to let the DB do this later, in the `make_ready()` method.
        # This could be revisited later to better factor this code. Note that we always generate
        # pin for a player, even if Mythic Track is not enabled for the guild. The `player_pins()`
        # method of the Game object will return None for players if MT is not enabled.
        pins = {xid: generate_pin() for xid in player_xids}

        if game_data.game_link:
            # Guild War tables are opened before the queue fills, so the link already exists.
            # Send the service the final roster along with the pins players are about to get.
            await self.action.bot.update_game_players(game_data, pins)
            details = GameLinkDetails(
                game_data.game_link,
                game_data.password,
                game_data.convoke_guild_name,
                game_data.convoke_guild_url,
            )
        else:
            details = await self.action.bot.create_game_link(
                game_data,
                pins,
                original_seats=original_seats,
            )

        suggested_vc = None
        if (
            not game_data.voice_xid
            and not game_data.voice_invite_link
            and self.action.guild_data
            and (suggest_voice_category := self.action.guild_data.suggest_voice_category)
            and self.action.guild is not None
        ):
            suggested_vc = safe_suggest_voice_channel(
                guild=self.action.guild,
                category=suggest_voice_category,
                player_xids=player_xids,
            )

        tag_span(
            game_id=game_data.id,
            game=game_data,
            voice_xid=game_data.voice_xid,
            voice_invite_link=game_data.voice_invite_link,
            guild_data__isnull=bool(self.action.guild_data is None),
            already_picked=suggested_vc.already_picked if suggested_vc else None,
            random_empty=suggested_vc.random_empty if suggested_vc else None,
        )

        ready_game = await services.games.make_ready(
            game_data,
            details,
            pins,
        )
        return ready_game, suggested_vc

    @tracer.wrap()
    async def handle_voice_creation(self, game_data: GameData, guild_xid: int) -> GameData:
        assert self.action.guild_data is not None
        if not self.action.guild_data.voice_create:
            return game_data

        category_prefix = self.action.channel_data.voice_category
        if not category_prefix:
            return game_data
        category = await safe_ensure_voice_category(self.action.bot, guild_xid, category_prefix)
        if not category:
            return game_data

        voice_channel = await safe_create_voice_channel(
            self.action.bot,
            guild_xid,
            f"Game-SB{game_data.id}",
            category=category,
            use_max_bitrate=self.action.guild_data.use_max_bitrate,
        )
        if not voice_channel:
            return game_data

        should_create_invite = self.action.channel_data.voice_invite
        invite: discord.Invite | None = None
        if should_create_invite:
            invite = await safe_create_channel_invite(
                voice_channel,
                max_age=2 * 60 * 60,  # 2 hours
                max_uses=0,  # unlimited uses
                temporary=True,
                reason=f"Creating temporary voice channel invite for Game-SB{game_data.id}",
            )

        return await services.games.set_voice(
            game_data,
            voice_xid=voice_channel.id,
            voice_invite_link=invite.url if invite else None,
        )

    @tracer.wrap()
    async def handle_direct_messages(
        self,
        game_data: GameData,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
    ) -> None:
        guild_locale_fallback = game_data.locale
        player_pins = game_data.player_pins
        player_names = {player.xid: player.name for player in game_data.players}
        player_xids = list(player_pins.keys())

        # Fetch stored user locales from the database
        player_data_list = await services.users.get_players_by_xid(player_xids)
        player_locales = {pd.xid: pd.locale or guild_locale_fallback for pd in player_data_list}

        # notify players
        fetched_players: dict[int, discord.User] = {}
        failed_xids: list[int] = []

        def mythic_track_link(player_xid: int) -> str:
            assert self.action.guild
            players_data = urllib.parse.quote(
                json.dumps(
                    [
                        {
                            "user_xid": f"{pid}",
                            "username": pn,
                        }
                        for pid, pn in player_names.items()
                    ],
                    separators=(",", ":"),
                ),
                safe="",
                encoding=None,
                errors=None,
            )
            return (
                "https://www.mythictrack.com/gamelobby"
                f"/{self.action.guild.id}"
                f"/{game_data.id}"
                f"/{game_data.format}"
                f"/{game_data.service}"
                f"/{player_xid}"
                f"/{players_data}"
                f"/{GameBracket(game_data.bracket).level}"
            )

        async def notify_player(player_xid: int) -> None:
            player = await safe_fetch_user(self.action.bot, player_xid)
            if not player:
                failed_xids.append(player_xid)
                return

            fetched_players[player_xid] = player

            # Use the stored locale from database, falling back to guild locale
            player_locale = player_locales.get(player_xid, guild_locale_fallback)

            # Generate a personalized embed for this player with their locale
            embed = self.action.game_embed(
                game_data,
                dm=True,
                suggested_vc=suggested_vc,
                rematch=rematch,
                locale_override=player_locale,
            )

            if pin := player_pins[player_xid]:
                mt_emoji = ""
                emojis = self.action.bot.emojis_cache
                if emoji := next((e for e in emojis if e.name == "mythic_track"), None):
                    mt_emoji = f"{emoji} "
                embed.description = f"{embed.description}\n\n" + t(
                    "lfg.mythic_track",
                    locale=player_locale,
                    emoji=mt_emoji,
                    link=mythic_track_link(player_xid),
                    pin=pin,
                )

            await safe_send_user(player, embed=embed)

        notify_player_tasks = [notify_player(player_xid) for player_xid in player_xids]
        await asyncio.gather(*notify_player_tasks)

        # give out awards
        assert self.action.interaction.guild_id is not None
        new_roles = await services.awards.give_awards(
            self.action.interaction.guild_id,
            player_xids,
        )
        assert self.action.interaction.guild
        for player_xid, new_awards in new_roles.items():
            for new_award in new_awards:
                if player_xid not in fetched_players:
                    key = "lfg.award_failure_take" if new_award.remove else "lfg.award_failure_give"
                    warning = t(
                        key,
                        locale=guild_locale_fallback,
                        role=new_award.role,
                        user_id=player_xid,
                    )
                    await safe_followup_channel(self.action.interaction, warning)
                    continue
                player = fetched_players[player_xid]
                await safe_add_role(
                    player,
                    self.action.interaction.guild,
                    new_award.role,
                    new_award.remove,
                )
                await safe_send_user(player, new_award.message)

        # notify issues with player permissions
        if failed_xids:
            failures = ", ".join(f"<@!{xid}>" for xid in failed_xids)
            warning = t("lfg.dm_failures", locale=guild_locale_fallback, players=failures)
            await safe_followup_channel(self.action.interaction, warning)
