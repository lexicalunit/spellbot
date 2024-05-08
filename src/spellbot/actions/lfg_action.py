from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import discord
from ddtrace import tracer

from spellbot.enums import GameFormat, GameService
from spellbot.models import GameStatus
from spellbot.operations import (
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
    save_create_channel_invite,
)
from spellbot.settings import settings
from spellbot.views import BaseView, PendingGameView, StartedGameView, StartedGameViewWithConfirm

from .base_action import BaseAction

if TYPE_CHECKING:
    from discord.message import Message

    from spellbot import SpellBot

logger = logging.getLogger(__name__)


class LookingForGameAction(BaseAction):
    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        super().__init__(bot, interaction)

    @tracer.wrap()
    async def get_friends(self, friends: str | None = None) -> str:
        return friends or ""

    @tracer.wrap()
    async def get_seats(
        self,
        format: int | None = None,
        seats: int | None = None,
    ) -> int:
        if format and not seats:
            return GameFormat(format).players
        return seats or self.channel_data["default_seats"]

    @tracer.wrap()
    async def get_service(self, service: int | None = None) -> int:
        if service is not None:
            return service
        if self.channel_data["default_service"] is not None:
            return self.channel_data["default_service"].value
        return GameService.SPELLTABLE.value

    @tracer.wrap()
    async def get_format(self, format: int | None = None) -> int:
        if format is not None:
            return format
        if self.channel_data["default_format"] is not None:
            return self.channel_data["default_format"].value
        return GameFormat.COMMANDER.value

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
            friend_xids = await self.services.games.filter_pending_games(friend_xids)
        return friend_xids

    @tracer.wrap()
    async def upsert_game(
        self,
        friend_xids: list[int],
        seats: int,
        format: int,
        service: int,
        message_xid: int | None,
    ) -> bool | None:
        assert self.guild
        assert self.channel

        # True if user clicked on a Join Game button.
        # False if user issued a /lfg command in chat.
        origin = bool(message_xid is not None)

        assert isinstance(service, int), "Expected service to be an integer."

        if not origin:
            assert self.interaction.guild_id is not None
            mirrors = await self.services.mirrors.get(self.guild.id, self.channel.id)
            return await self.services.games.upsert(
                guild_xid=self.interaction.guild_id,
                channel_xid=self.channel.id,
                author_xid=self.interaction.user.id,
                friends=friend_xids,
                seats=seats,
                format=format,
                service=service,
                mirrors=mirrors,
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
                view: BaseView | None = None
                if self.channel_data.get("show_points", False) and not found["confirmed"]:
                    if self.channel_data.get("require_confirmation", False):
                        view = StartedGameViewWithConfirm(bot=self.bot)
                    else:
                        view = StartedGameView(bot=self.bot)
                await safe_update_embed(message, embed=embed, view=view)

            return None

        await self.services.games.add_player(self.interaction.user.id)
        return False

    @tracer.wrap()
    async def execute(  # noqa: C901
        self,
        friends: str | None = None,
        seats: int | None = None,
        format: int | None = None,
        message_xid: int | None = None,
        service: int | None = None,
    ) -> None:
        if not self.guild or not self.channel:
            # Someone tried to lfg in a Discord thread rather than in the channel itself.
            await safe_send_user(
                self.interaction.user,
                "Sorry, that command is not supported in this context.",
            )
            return None

        # True if user clicked on a Join Game button.
        # False if user issued a /lfg command in chat.
        origin = bool(message_xid is not None)

        actual_friends: str = await self.get_friends(friends)
        actual_format: int = await self.get_format(format)
        actual_seats: int = await self.get_seats(actual_format, seats)
        actual_service: int = await self.get_service(service)

        if await self.services.users.is_waiting(self.channel.id):
            msg = "You're already in a game in this channel."
            if origin:
                return await safe_send_user(self.interaction.user, msg)
            await safe_followup_channel(self.interaction, msg)
            return None

        req_confirm = self.channel_data["require_confirmation"]
        if req_confirm and not await self.services.users.is_confirmed(self.channel.id):
            msg = "You need to confirm your points before joining another game."
            if origin:
                return await safe_send_user(self.interaction.user, msg)
            await safe_followup_channel(self.interaction, msg)
            return None

        if await self.services.users.pending_games() + 1 > settings.MAX_PENDING_GAMES:
            msg = "You're in too many pending games to join another one at this time."
            if origin:
                return await safe_send_user(self.interaction.user, msg)
            await safe_followup_channel(self.interaction, msg)
            return None

        friend_xids = list(map(int, re.findall(r"<@!?(\d+)>", actual_friends)))

        if len(friend_xids) + 1 > actual_seats:
            await safe_send_user(
                self.interaction.user,
                "You mentioned too many players.",
            )
            return None

        friend_xids = await self.filter_friend_xids(friend_xids)

        new = await self.upsert_game(
            friend_xids,
            actual_seats,
            actual_format,
            actual_service,
            message_xid,
        )
        if new is None:
            return None

        fully_seated = await self.services.games.fully_seated()
        started_game_id: int | None = None
        other_game_ids: list[int] = []
        if fully_seated:
            other_game_ids = await self.services.games.other_game_ids()
            started_game_id = await self.make_game_ready(GameService(actual_service))
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
            return None
        return None

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
            if (channel := await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)) and (
                message := safe_get_partial_message(
                    channel,
                    guild_xid,
                    message_xid,
                )
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
                f"You are not one of the players in game SB{found.get('id')}.",
            )
            return

        plays = await self.services.games.get_plays()
        if plays.get(self.interaction.user.id, {}).get("confirmed_at", None):
            await safe_send_user(
                self.interaction.user,
                f"You've already confirmed your points for game SB{found.get('id')}.",
            )
            return

        # if at least one player has confirmed their points, then changing points not allowed
        if any(play.get("confirmed_at") is not None for play in plays.values()):
            await safe_send_user(
                self.interaction.user,
                (
                    f"Points for game SB{found.get('id')} are locked in,"
                    " please confirm them or contact a mod."
                ),
            )
            return

        await self.services.games.add_points(self.interaction.user.id, points)
        embed = await self.services.games.to_embed()
        await safe_update_embed(message, embed=embed)

    @tracer.wrap()
    async def confirm_points(self, message: Message) -> None:
        found = await self.services.games.select_by_message_xid(message.id)
        if not found:
            return

        if not await self.services.games.players_included(self.interaction.user.id):
            await safe_send_user(
                self.interaction.user,
                f"You are not one of the players in game SB{found.get('id')}.",
            )
            return

        plays = await self.services.games.get_plays()
        if plays.get(self.interaction.user.id, {}).get("confirmed_at", None):
            await safe_send_user(
                self.interaction.user,
                f"You've already confirmed your points for game SB{found.get('id')}",
            )
            return

        if any(play.get("points") is None for play in plays.values()):
            await safe_send_user(
                self.interaction.user,
                (
                    "Please wait until all players have reported"
                    f" before confirming points for game SB{found.get('id')}"
                ),
            )
            return

        confirmed_at = await self.services.games.confirm_points(player_xid=self.interaction.user.id)
        embed = await self.services.games.to_embed()
        data = await self.services.games.to_dict()
        if data["confirmed"]:
            await safe_update_embed(message, embed=embed, view=None)
        else:
            await safe_update_embed(message, embed=embed)
        plays[self.interaction.user.id]["confirmed_at"] = confirmed_at
        if all(play["confirmed_at"] is not None for play in plays.values()):
            await self.services.games.update_records(plays)

    @tracer.wrap()
    async def create_game(
        self,
        players: str,
        format: int | None = None,
        service: int | None = None,
    ) -> None:
        assert self.channel

        game_format = GameFormat(format or GameFormat.COMMANDER.value)
        game_service = GameService(service or GameService.SPELLTABLE.value)
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
            service=game_service.value,
            create_new=True,
        )
        await self.make_game_ready(game_service)
        await self._handle_voice_creation(self.interaction.guild_id)
        await self._handle_embed_creation(new=True, origin=False, fully_seated=True)
        await self._handle_direct_messages()

    @tracer.wrap()
    async def make_game_ready(self, service: GameService) -> int:
        spelltable_link = (
            await self.bot.create_spelltable_link() if service == GameService.SPELLTABLE else None
        )
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
        game_id = game_data["id"]
        voice_channel = await safe_create_voice_channel(
            self.bot,
            guild_xid,
            f"Game-SB{game_id}",
            category,
        )
        if not voice_channel:
            return

        should_create_invite = self.channel_data.get("voice_invite", False)
        invite: discord.Invite | None = None
        if should_create_invite:
            invite = await save_create_channel_invite(
                voice_channel,
                max_age=2 * 60 * 60,  # 2 hours
                max_uses=0,  # unlimited uses
                temporary=True,
                reason=f"Creating temporary voice channel invite for Game-SB{game_id}",
            )

        await self.services.games.set_voice(
            voice_xid=voice_channel.id,
            voice_invite_link=invite.url if invite else None,
        )

    @tracer.wrap()
    async def _create_initial_post(
        self,
        embed: discord.Embed,
        view: BaseView | None = None,
        content: str | None = None,
    ) -> None:
        assert self.guild
        assert self.channel

        if message := await safe_followup_channel(
            self.interaction,
            content=content,
            embed=embed,
            view=view,
        ) or (
            message := await safe_channel_reply(
                self.channel,
                content=content,
                embed=embed,
                view=view,
            )
        ):
            await self.services.games.add_post(self.guild.id, self.channel.id, message.id)

        # also send the game post to all configured mirrors
        mirrors = await self.services.mirrors.get(self.guild.id, self.channel.id)
        for mirror in mirrors:
            to_guild_xid = mirror["to_guild_xid"]
            to_channel_xid = mirror["to_channel_xid"]
            logger.info("Mirroring game post to %s/%s ...", to_guild_xid, to_channel_xid)

            to_channel = await safe_fetch_text_channel(self.bot, to_guild_xid, to_channel_xid)
            if to_channel is None:
                logger.error("Failed to fetch channel %s", to_channel_xid)
                continue
            logger.info("Mirroring game post to %s ...", to_channel)

            to_message = await safe_channel_reply(
                to_channel, content=content, embed=embed, view=view
            )
            if to_message is None:
                logger.error("Failed to create post in channel %s", to_channel)
                continue
            logger.info("Mirrored game post to %s", to_message)
            await self.services.games.add_post(to_guild_xid, to_channel_xid, to_message.id)

    @tracer.wrap()
    async def _handle_embed_creation(  # noqa: C901,PLR0912
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
        game_data = await self.services.games.to_dict()

        view: BaseView | None = None
        if fully_seated:
            if self.channel_data.get("show_points", False) and not game_data["confirmed"]:
                if self.channel_data.get("require_confirmation", False):
                    view = StartedGameViewWithConfirm(bot=self.bot)
                else:
                    view = StartedGameView(bot=self.bot)
        else:
            view = PendingGameView(bot=self.bot)

        if new:  # create the initial game post:
            await self._create_initial_post(embed, view, content)
            return

        # update the game post(s) for this game, which should already exist

        for post in game_data.get("posts", []):
            message: discord.Message | discord.PartialMessage | None = None
            guild_xid = post["guild_xid"]
            channel_xid = post["channel_xid"]
            message_xid = post["message_xid"]

            channel: discord.TextChannel | None = None
            if self.guild.id == guild_xid and self.channel.id == channel_xid:
                # this post is for the current channel and guild
                channel = self.channel
            else:
                # the post is in a different channel/guild, so we need to fetch it
                channel = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)

            if channel is None:
                # failed for find the channel for this post
                continue

            # The post we're going to update here is the origin post:
            if self.interaction.message and self.interaction.message.id == message_xid:
                content = self.channel_data.get("extra", None)
                if await safe_update_embed_origin(
                    self.interaction,
                    content=content,
                    embed=embed,
                    view=view,
                ):
                    # successfully updated the origin post
                    continue

            message = safe_get_partial_message(channel, guild_xid, message_xid)
            if not message:
                # failed to find the message for this post
                continue

            if not await safe_update_embed(message, embed=embed, view=view):
                # failed to update the message for this post
                continue

        if not origin:
            await self._reply_found_embed()

    @tracer.wrap()
    async def _reply_found_embed(self) -> None:
        assert self.guild is not None
        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        game_data = await self.services.games.to_dict()
        links = game_data["jump_links"]
        link = links[self.guild.id]
        format = game_data["format"]
        embed.set_author(name=f"I found a {GameFormat(format)} game for you!")
        embed.description = f"You can [jump to the game post]({link}) to see it!"
        embed.color = settings.INFO_EMBED_COLOR
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
        mod_role: discord.Role | None = None
        for role in self.interaction.guild.roles:
            if role.name.startswith(settings.MOD_PREFIX):
                mod_role = role
                break

        if not mod_role:
            return

        watch_notes = await self.services.games.watch_notes(player_xids)
        if not watch_notes:
            return

        data = await self.services.games.to_dict()

        embed = discord.Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name="Watched user(s) joined a game")
        embed.color = settings.INFO_EMBED_COLOR
        description = ""
        for jump_link in data["jump_links"].values():
            description += f"[⇤ Jump to the game post]({jump_link})\n"
        description += f"[➤ Spectate the game on SpellTable]({data['spectate_link']})\n\n**Users:**"
        for user_xid, note in watch_notes.items():
            description += f"\n• <@{user_xid}>: {note}"
        embed.description = description
        embed.add_field(name="Game ID", value=f"SB{data['id']}", inline=False)

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
