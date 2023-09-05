from __future__ import annotations

import logging
import re
from typing import Optional, Union

import discord
from ddtrace import tracer
from discord.embeds import Embed
from discord.message import Message

from .. import SpellBot
from ..models import GameFormat, GameStatus
from ..operations import (
    safe_add_role,
    safe_channel_reply,
    safe_create_voice_channel,
    safe_ensure_voice_category,
    safe_fetch_text_channel,
    safe_fetch_user,
    safe_followup_channel,
    safe_get_partial_message,
    safe_send_user,
    safe_update_embed,
    safe_update_embed_origin,
)
from ..settings import Settings
from ..views import BaseView, PendingGameView, StartedGameView
from .base_action import BaseAction

logger = logging.getLogger(__name__)


class LookingForGameAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)
        self.settings = Settings()

    @tracer.wrap()
    async def get_friends(self, friends: Optional[str] = None) -> str:
        return friends or ""

    @tracer.wrap()
    async def get_seats(
        self,
        format: Optional[int] = None,
        seats: Optional[int] = None,
    ) -> int:
        if format and not seats:
            return GameFormat(format).players
        return seats or self.channel_data["default_seats"]

    @tracer.wrap()
    async def get_format(self, format: Optional[int] = None) -> int:
        return format or GameFormat.COMMANDER.value  # type: ignore

    @tracer.wrap()
    async def filter_friend_xids(self, friend_xids: list[int]) -> list[int]:
        assert self.guild
        if friend_xids:
            friend_xids = await self.ensure_users_exist(friend_xids)
        if friend_xids:
            friend_xids = await self.services.games.filter_blocked_list(
                self.interaction.user.id,
                friend_xids,
            )
        if friend_xids:
            friend_xids = await self.services.games.filter_pending_games(friend_xids, self.guild.id)
        return friend_xids

    @tracer.wrap()
    async def upsert_game(
        self,
        friend_xids: list[int],
        seats: int,
        format: int,
        message_xid: Optional[int],
    ) -> Optional[bool]:
        assert self.guild
        assert self.channel

        # True if user clicked on a Join Game button.
        # False if user issued a /lfg command in chat.
        origin = bool(message_xid is not None)

        if not origin:
            assert self.interaction.guild_id is not None
            return await self.services.games.upsert(
                guild_xid=self.interaction.guild_id,
                channel_xid=self.channel.id,
                author_xid=self.interaction.user.id,
                friends=friend_xids,
                seats=seats,
                format=format,
            )

        assert message_xid
        found = await self.services.games.select_by_message_xid(message_xid)
        if not found or await self.services.games.blocked(self.interaction.user.id):
            await safe_send_user(self.interaction.user, "You can not join this game.")
            return None

        # Sometimes game posts have Join/Leave buttons on them even though
        # the game has started. This can happen if an interaction fails on
        # Discord's side of things. This makes it appear like a user can still
        # join a game, even though it's already started. We need to handle this
        # by informing the user and updating the game post they tried to join.
        if found["status"] == GameStatus.STARTED.value:
            # inform the player that their interaction failed
            await safe_send_user(
                self.interaction.user,
                "Sorry, that game has already started.",
            )

            # attempt to update the problematic game post
            if message := safe_get_partial_message(
                self.channel,
                self.guild.id,
                message_xid,
            ):
                embed = await self.services.games.to_embed()
                fully_seated = await self.services.games.fully_seated()
                view: Optional[BaseView] = None
                if fully_seated:
                    if self.channel_data.get("show_points", False):
                        view = StartedGameView(bot=self.bot)
                else:
                    view = PendingGameView(bot=self.bot)
                await safe_update_embed(
                    message,
                    embed=embed,
                    view=view,
                )

            return None

        await self.services.games.add_player(self.interaction.user.id)
        return False

    @tracer.wrap()
    async def execute(
        self,
        friends: Optional[str] = None,
        seats: Optional[int] = None,
        format: Optional[int] = None,
        message_xid: Optional[int] = None,
    ) -> None:
        if not self.guild or not self.channel:
            # Someone tried to lfg in a Discord thread rather than in the channel itself.
            await safe_send_user(
                self.interaction.user,
                "Sorry, that command is not supported in this context.",
            )
            return

        # True if user clicked on a Join Game button.
        # False if user issued a /lfg command in chat.
        origin = bool(message_xid is not None)

        actual_friends: str = await self.get_friends(friends)
        actual_seats: int = await self.get_seats(format, seats)
        actual_format: int = await self.get_format(format)

        if await self.services.users.is_waiting(self.channel.id):
            msg = "You're already in a game in this channel."
            if origin:
                return await safe_send_user(self.interaction.user, msg)
            await safe_followup_channel(self.interaction, msg)
            return

        if await self.services.users.pending_games() + 1 > self.settings.MAX_PENDING_GAMES:
            msg = "You're in too many pending games to join another one at this time."
            if origin:
                return await safe_send_user(self.interaction.user, msg)
            await safe_followup_channel(self.interaction, msg)
            return

        if await self.services.users.queued_in_another_guild(self.guild.id):
            msg = "You're in a pending game in another server, leave that one first."
            if origin:
                return await safe_send_user(self.interaction.user, msg)
            await safe_followup_channel(self.interaction, msg)
            return

        friend_xids = list(map(int, re.findall(r"<@!?(\d+)>", actual_friends)))

        if len(friend_xids) + 1 > actual_seats:
            await safe_send_user(
                self.interaction.user,
                "You mentioned too many players.",
            )
            return

        friend_xids = await self.filter_friend_xids(friend_xids)

        new = await self.upsert_game(
            friend_xids,
            actual_seats,
            actual_format,
            message_xid,
        )
        if new is None:
            return

        fully_seated = await self.services.games.fully_seated()
        started_game_id: Optional[int] = None
        other_game_ids: list[int] = []
        if fully_seated:
            other_game_ids = await self.services.games.other_game_ids()
            started_game_id = await self.make_game_ready()
            await self._handle_voice_creation(self.guild.id)

        await self._handle_embed_creation(
            new=new,
            origin=origin,
            fully_seated=fully_seated,
        )

        if fully_seated:
            assert started_game_id is not None
            await self._handle_direct_messages()
            await self._update_other_game_posts(other_game_ids)

    @tracer.wrap()
    async def _update_other_game_posts(self, other_game_ids: list[int]) -> None:
        """Update any other pending games to show that some players are no longer available."""
        assert self.channel is not None
        assert self.guild is not None
        if not other_game_ids:
            return

        message_xids = await self.services.games.message_xids(other_game_ids)
        for message_xid in message_xids:
            data = await self.services.games.select_by_message_xid(message_xid)
            if not data:
                continue

            channel_xid = data["channel_xid"]
            guild_xid = data["guild_xid"]
            if channel := await safe_fetch_text_channel(self.bot, guild_xid, channel_xid):
                if message := safe_get_partial_message(
                    channel,
                    guild_xid,
                    message_xid,
                ):
                    embed = await self.services.games.to_embed()
                    await safe_update_embed(
                        message,
                        embed=embed,
                        view=PendingGameView(bot=self.bot),
                    )

    @tracer.wrap()
    async def add_points(self, message: Message, points: int) -> None:
        found = await self.services.games.select_by_message_xid(message.id)
        if not found:
            return

        if not await self.services.games.players_included(self.interaction.user.id):
            await safe_send_user(
                self.interaction.user,
                "You are not one of the players in this game.",
            )
            return

        await self.services.games.add_points(self.interaction.user.id, points)
        embed = await self.services.games.to_embed()
        await safe_update_embed(message, embed=embed)

    @tracer.wrap()
    async def create_game(self, players: str, format: Optional[int] = None) -> None:
        assert self.channel

        game_format = GameFormat(format or GameFormat.COMMANDER.value)  # type: ignore
        player_xids = list(map(int, re.findall(r"<@!?(\d+)>", players)))
        requested_seats = len(player_xids)
        if requested_seats < 2 or requested_seats > game_format.players:
            await safe_followup_channel(
                self.interaction,
                f"You can't create a {game_format} game with {requested_seats} players.",
            )
            return

        found_players: list[int] = []
        found_players = await self.ensure_users_exist(player_xids, exclude_self=False)

        if len(found_players) != requested_seats:
            excluded_player_xids = set(player_xids) - set(found_players)
            excluded_players_s = ", ".join(f"<@{xid}>" for xid in excluded_player_xids)
            await safe_followup_channel(
                self.interaction,
                (
                    "Some of the players you mentioned can not"
                    f" be added to a game: {excluded_players_s}"
                ),
            )
            return

        assert self.interaction.guild_id
        await self.services.games.upsert(
            guild_xid=self.interaction.guild_id,
            channel_xid=self.channel.id,
            author_xid=found_players[0],
            friends=found_players[1:],
            seats=requested_seats,
            format=game_format.value,
            create_new=True,
        )
        await self.make_game_ready()
        await self._handle_voice_creation(self.interaction.guild_id)
        await self._handle_embed_creation(new=True, origin=False, fully_seated=True)
        await self._handle_direct_messages()

    @tracer.wrap()
    async def make_game_ready(self) -> int:
        spelltable_link = await self.bot.create_spelltable_link()
        return await self.services.games.make_ready(spelltable_link)

    @tracer.wrap()
    async def _handle_voice_creation(self, guild_xid: int) -> None:
        if not await self.services.guilds.should_voice_create():
            return

        category_prefix = self.channel_data["voice_category"]
        category = await safe_ensure_voice_category(
            self.bot,
            guild_xid,
            category_prefix,
        )
        if not category:
            return

        game_data = await self.services.games.to_dict()
        voice_channel = await safe_create_voice_channel(
            self.bot,
            guild_xid,
            f"Game-SB{game_data['id']}",
            category,
        )
        if not voice_channel:
            return

        await self.services.games.set_voice(voice_channel.id)

    @tracer.wrap()
    async def _handle_embed_creation(  # pylint: disable=too-many-branches
        self,
        new: bool,
        origin: bool,
        fully_seated: bool,
    ) -> None:
        assert self.guild
        assert self.channel

        # build the game post's embed and view:
        embed: discord.Embed = await self.services.games.to_embed()
        content = self.channel_data.get("extra", None)

        view: Optional[BaseView] = None
        if fully_seated:
            if self.channel_data.get("show_points", False):
                view = StartedGameView(bot=self.bot)
        else:
            view = PendingGameView(bot=self.bot)

        if new:  # create the initial game post:
            if message := await safe_followup_channel(
                self.interaction,
                content=content,
                embed=embed,
                view=view,
            ):
                await self.services.games.set_message_xid(message.id)
            elif message := await safe_channel_reply(
                self.channel,
                content=content,
                embed=embed,
                view=view,
            ):
                await self.services.games.set_message_xid(message.id)
            return

        message: Optional[Union[discord.Message, discord.PartialMessage]] = None
        game_data = await self.services.games.to_dict()
        message_xid = game_data["message_xid"]
        if message_xid:
            message = safe_get_partial_message(self.channel, self.guild.id, message_xid)

        # update the existing game post:

        if origin:
            # Try to update the origin embed. Sometimes this can fail.
            # If it does fail, we will fallback to doing a standard
            # message.edit() call, which should hopefully at least update
            # the game embed, even if the interaction shows as "failed".
            content = self.channel_data.get("extra", None)
            if await safe_update_embed_origin(
                self.interaction,
                content=content,
                embed=embed,
                view=view,
            ):
                return

        if message:
            if await safe_update_embed(message, embed=embed, view=view):
                pass
            elif updated := await safe_channel_reply(
                self.channel,
                content=content,
                embed=embed,
                view=view,
            ):
                await self.services.games.set_message_xid(updated.id)

        if not origin:
            await self._reply_found_embed()

    @tracer.wrap()
    async def _reply_found_embed(self) -> None:
        embed = Embed()
        embed.set_thumbnail(url=self.settings.ICO_URL)
        embed.set_author(name="I found a game for you!")
        game_data = await self.services.games.to_dict()
        link = game_data["jump_link"]
        embed.description = f"You can [jump to the game post]({link}) to see it!"
        embed.color = self.settings.EMBED_COLOR
        await safe_followup_channel(self.interaction, embed=embed)

    @tracer.wrap()
    async def _handle_direct_messages(self) -> None:
        player_xids = await self.services.games.player_xids()
        embed = await self.services.games.to_embed(dm=True)
        failed_xids: list[int] = []

        # notify players
        fetched_players: dict[int, discord.User] = {}
        for player_xid in player_xids:
            player = await safe_fetch_user(self.bot, player_xid)
            if player:
                fetched_players[player_xid] = player
                await safe_send_user(player, embed=embed)
            else:
                failed_xids.append(player_xid)

        # give out awards
        assert self.interaction.guild_id is not None
        new_roles = await self.services.awards.give_awards(
            self.interaction.guild_id,
            player_xids,
        )
        assert self.interaction.guild
        for player_xid, new_awards in new_roles.items():
            for new_award in new_awards:
                if player_xid not in fetched_players:
                    warning = (
                        f"Unable to {'take' if new_award.remove else 'give'}"
                        f" role {new_award.role}"
                        f" {'from' if new_award.remove else 'to'}"
                        f" user <@{player_xid}>"
                    )
                    await safe_followup_channel(self.interaction, warning)
                    continue
                player = fetched_players[player_xid]
                await safe_add_role(
                    player,
                    self.interaction.guild,
                    new_award.role,
                    new_award.remove,
                )
                await safe_send_user(player, new_award.message)

        # notify issues with player permissions
        if failed_xids:
            failures = ", ".join(f"<@!{xid}>" for xid in failed_xids)
            warning = f"Unable to send Direct Messages to some players: {failures}"
            await safe_followup_channel(self.interaction, warning)

        await self._handle_watched_players(player_xids)

    @tracer.wrap()
    async def _handle_watched_players(self, player_xids: list[int]) -> None:
        """Notify moderators about watched players."""
        assert self.interaction.guild
        mod_role: Optional[discord.Role] = None
        for role in self.interaction.guild.roles:
            if role.name.startswith(self.settings.MOD_PREFIX):
                mod_role = role
                break

        if not mod_role:
            return

        watch_notes = await self.services.games.watch_notes(player_xids)
        if not watch_notes:
            return

        data = await self.services.games.to_dict()

        embed = Embed()
        embed.set_thumbnail(url=self.settings.ICO_URL)
        embed.set_author(name="Watched user(s) joined a game")
        embed.color = self.settings.EMBED_COLOR
        description = (
            f"[⇤ Jump to the game post]({data['jump_link']})\n"
            f"[➤ Spectate the game on SpellTable]({data['spectate_link']})\n\n"
            f"**Users:**"
        )
        for user_xid, note in watch_notes.items():
            description += f"\n• <@{user_xid}>: {note}"
        embed.description = description

        for member in mod_role.members:
            await safe_send_user(member, embed=embed)

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
        for user_xid in user_xids:
            if exclude_self and user_xid == self.interaction.user.id:
                continue
            user = await safe_fetch_user(self.bot, user_xid)
            if not user:
                continue
            data = await self.services.users.upsert(user)
            if data["banned"]:
                continue
            found_users.append(user_xid)
        return found_users
