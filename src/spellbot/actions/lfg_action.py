from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import MAX_RULES_LENGTH, GameStatus
from spellbot.operations import (
    VoiceChannelSuggestion,
    safe_add_role,
    safe_channel_reply,
    safe_create_channel_invite,
    safe_create_voice_channel,
    safe_ensure_voice_category,
    safe_fetch_text_channel,
    safe_fetch_user,
    safe_followup_channel,
    safe_get_partial_message,
    safe_send_user,
    safe_suggest_voice_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.settings import settings
from spellbot.views import BaseView, GameView

from .base_action import BaseAction

if TYPE_CHECKING:
    from spellbot import SpellBot
    from spellbot.models import GameDict

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
    async def get_bracket(self, format: int | None, bracket: int | None = None) -> int:
        if format == GameFormat.CEDH.value:
            return GameBracket.BRACKET_5.value
        if format == GameFormat.PRE_CONS.value:
            return GameBracket.BRACKET_2.value
        if bracket is not None:
            return bracket
        if self.channel_data["default_bracket"] is not None:
            return self.channel_data["default_bracket"].value
        return GameBracket.NONE.value

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
        rules: str | None,
        format: int,
        bracket: int,
        service: int,
        message_xid: int | None,
    ) -> bool | None:
        """Return True if the game is new, False if existing, or None of user can not join."""
        assert self.guild
        assert self.channel

        # True if user clicked on a Join Game button.
        # False if user issued a /lfg command in chat.
        origin = bool(message_xid is not None)

        assert isinstance(service, int), "Expected service to be an integer."

        if not origin:
            assert self.interaction.guild_id is not None
            return await self.services.games.upsert(
                guild_xid=self.interaction.guild_id,
                channel_xid=self.channel.id,
                author_xid=self.interaction.user.id,
                friends=friend_xids,
                seats=seats,
                rules=rules,
                format=format,
                bracket=bracket,
                service=service,
                blind=bool(self.channel_data["blind_games"]),
            )

        assert message_xid
        found = await self.services.games.select_by_message_xid(message_xid)
        if not found or await self.services.games.blocked(self.interaction.user.id):
            await safe_send_user(self.interaction.user, "You can not join this game.")
            return None

        if found["status"] == GameStatus.STARTED.value:
            logger.warning("User tried to join a game that has already started.")
            # inform the player that their interaction failed
            await safe_send_user(
                self.interaction.user,
                "Sorry, that game has already started.",
            )
            return None

        await self.services.games.add_player(self.interaction.user.id)
        return False

    @tracer.wrap()
    async def execute_rematch(self) -> None:
        if not self.guild or not self.channel:
            # Someone tried to lfg in a Discord thread rather than in the channel itself.
            await safe_send_user(
                self.interaction.user,
                "Please run this command in the same channel as your last played game.",
            )
            return

        if await self.services.users.pending_games():
            await safe_followup_channel(
                self.interaction,
                "You're already in a pending game, leave that one first.",
            )
            return

        game_data = await self.services.games.select_last_game(
            user_xid=self.interaction.user.id,
            guild_xid=self.guild.id,
        )
        if not game_data:
            await safe_followup_channel(
                self.interaction,
                "You have not played a game in this guild yet.",
            )
            return

        player_xids = await self.services.games.player_xids()
        players = " ".join(f"<@{xid}>" for xid in player_xids)

        await self.create_game(
            players=players,
            format=game_data["format"],
            bracket=game_data["bracket"],
            service=GameService.NOT_ANY.value,
            rematch=True,
        )

    @tracer.wrap()
    async def execute(
        self,
        friends: str | None = None,
        seats: int | None = None,
        rules: str | None = None,
        format: int | None = None,
        bracket: int | None = None,
        service: int | None = None,
        message_xid: int | None = None,
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
        actual_bracket: int = await self.get_bracket(actual_format, bracket)
        actual_seats: int = await self.get_seats(actual_format, seats)
        actual_service: int = await self.get_service(service)
        rules = None if not rules else rules[:MAX_RULES_LENGTH]

        if await self.services.users.is_waiting(self.channel.id):
            msg = "You're already in a game in this channel."
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
            rules,
            actual_format,
            actual_bracket,
            actual_service,
            message_xid,
        )
        if new is None:
            return None

        fully_seated = await self.services.games.fully_seated()
        started_game_id: int | None = None
        other_game_ids: list[int] = []
        suggested_vc = None
        if fully_seated:
            other_game_ids = await self.services.games.other_game_ids()
            game_data = await self.services.games.to_dict()
            player_xids = await self.services.games.player_xids()
            started_game_id, suggested_vc = await self.make_game_ready(game_data, player_xids)
            await self._handle_voice_creation(self.guild.id)

        await self._handle_embed_creation(
            new=new,
            origin=origin,
            fully_seated=fully_seated,
            suggested_vc=suggested_vc,
        )

        if fully_seated:
            assert started_game_id is not None
            await self._handle_direct_messages(suggested_vc=suggested_vc)
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
                message := safe_get_partial_message(channel, guild_xid, message_xid)
            ):
                embed = await self.services.games.to_embed(guild=self.guild)
                await safe_update_embed(
                    message,
                    embed=embed,
                    view=GameView(bot=self.bot),
                )

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

        game_format = GameFormat(format or GameFormat.COMMANDER.value)
        game_bracket = GameBracket(bracket or GameBracket.NONE.value)
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
            rules=None,
            format=game_format.value,
            bracket=game_bracket.value,
            service=game_service.value,
            create_new=True,
            blind=bool(self.channel_data["blind_games"]),
        )
        game_data = await self.services.games.to_dict()
        _, suggested_vc = await self.make_game_ready(game_data, player_xids)
        await self._handle_voice_creation(self.interaction.guild_id)
        await self._handle_embed_creation(
            new=True,
            origin=False,
            fully_seated=True,
            suggested_vc=suggested_vc,
            rematch=rematch,
        )
        await self._handle_direct_messages(suggested_vc=suggested_vc, rematch=rematch)

    @tracer.wrap()
    async def make_game_ready(
        self,
        game: GameDict,
        player_xids: list[int],
    ) -> tuple[int, VoiceChannelSuggestion | None]:
        details = await self.bot.create_game_link(game)

        suggested_vc = None
        if (
            not game["voice_xid"]
            and not game["voice_invite_link"]
            and self.guild_data
            and (suggest_voice_category := self.guild_data["suggest_voice_category"])
            and self.guild is not None
        ):
            suggested_vc = safe_suggest_voice_channel(
                guild=self.guild,
                category=suggest_voice_category,
                player_xids=player_xids,
            )

        if span := tracer.current_span():  # pragma: no cover
            span.set_tags(
                {
                    "game_id": str(game["id"]),
                    "voice_xid": str(game["voice_xid"]),
                    "voice_invite_link": str(game["voice_invite_link"]),
                    "guild_data__isnull": str(bool(self.guild_data is None)),
                    "already_picked": str(suggested_vc.already_picked if suggested_vc else None),
                    "random_empty": str(suggested_vc.random_empty if suggested_vc else None),
                },
            )

        return await self.services.games.make_ready(details.link, details.password), suggested_vc

    @tracer.wrap()
    async def _handle_voice_creation(self, guild_xid: int) -> None:
        if not await self.services.guilds.should_voice_create():
            return
        use_max_bitrate = await self.services.guilds.get_use_max_bitrate()

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
            category=category,
            use_max_bitrate=use_max_bitrate,
        )
        if not voice_channel:
            return

        should_create_invite = self.channel_data.get("voice_invite", False)
        invite: discord.Invite | None = None
        if should_create_invite:
            invite = await safe_create_channel_invite(
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

    @tracer.wrap()
    async def _handle_embed_creation(
        self,
        *,
        new: bool,
        origin: bool,
        fully_seated: bool,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
    ) -> None:
        assert self.guild
        assert self.channel

        # build the game post's embed and view:
        embed: discord.Embed = await self.services.games.to_embed(
            guild=self.guild,
            suggested_vc=suggested_vc,
            rematch=rematch,
        )
        content = self.channel_data.get("extra", None)
        game_data = await self.services.games.to_dict()

        view = None if fully_seated else GameView(bot=self.bot)
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
        format = game_data["format"]
        embed.set_author(name=f"I found a {GameFormat(format)} game for you!")
        embed.color = settings.INFO_EMBED_COLOR
        if link := links.get(self.guild.id):
            embed.description = f"You can [jump to the game post]({link}) to see it!"
        else:
            game_id = game_data["id"]
            embed.description = f"You have joined the game SB{game_id}!"
        await safe_followup_channel(self.interaction, embed=embed)

    @tracer.wrap()
    async def _handle_direct_messages(
        self,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
    ) -> None:
        player_pins = await self.services.games.player_pins()
        player_names = await self.services.games.player_names()
        player_xids = list(player_pins.keys())
        game_data = await self.services.games.to_dict()
        base_embed = await self.services.games.to_embed(
            guild=self.guild,
            dm=True,
            suggested_vc=suggested_vc,
            rematch=rematch,
        )

        # notify players
        fetched_players: dict[int, discord.User] = {}
        failed_xids: list[int] = []

        def mythic_track_link(player_xid: int) -> str:
            assert self.guild
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
                f"/{self.guild.id}"
                f"/{game_data['id']}"
                f"/{game_data['format']}"
                f"/{game_data['service']}"
                f"/{player_xid}"
                f"/{players_data}"
                f"/{game_data['bracket'] - 1}"
            )

        async def notify_player(player_xid: int) -> None:
            embed = base_embed.copy()
            if pin := player_pins[player_xid]:
                embed.description = (
                    f"{embed.description}\n\n"
                    f"Track your game on [Mythic Track]({mythic_track_link(player_xid)}) "
                    f"with PIN code: `{pin}`"
                )
            if player := await safe_fetch_user(self.bot, player_xid):
                fetched_players[player_xid] = player
                await safe_send_user(player, embed=embed)
            else:
                failed_xids.append(player_xid)

        notify_player_tasks = [notify_player(player_xid) for player_xid in player_xids]
        await asyncio.gather(*notify_player_tasks)

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
        description += "\n\n**Users:**"
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
