import logging
import re
from typing import Optional, cast

import discord
import discord_slash.utils.manage_components as comp
from discord.embeds import Embed
from discord.message import Message
from discord_slash.context import ComponentContext, InteractionContext
from discord_slash.model import ButtonStyle

from spellbot.client import SpellBot
from spellbot.interactions import BaseInteraction
from spellbot.models.game import GameFormat, GameStatus
from spellbot.operations import (
    safe_add_role,
    safe_create_invite,
    safe_create_voice_channel,
    safe_ensure_voice_category,
    safe_fetch_message,
    safe_fetch_user,
    safe_send_channel,
    safe_send_user,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.settings import Settings

logger = logging.getLogger(__name__)


class LookingForGameInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot, ctx: InteractionContext):
        super().__init__(bot, ctx)

    async def execute(
        self,
        friends: Optional[str] = None,
        seats: Optional[int] = None,
        format: Optional[int] = None,
        message_xid: Optional[int] = None,
    ):
        assert self.ctx
        assert self.guild
        assert self.channel

        # True if user clicked on a Join Game button.
        # False if user issued a /lfg command in chat.
        origin = bool(message_xid is not None)

        friends = friends or ""
        if format and not seats:
            seats = GameFormat(format).players
        else:
            seats = seats or self.channel_data["default_seats"]
        format = format or GameFormat.COMMANDER.value  # type: ignore
        friend_xids = list(map(int, re.findall(r"<@!?(\d+)>", friends)))

        assert seats is not None
        if len(friend_xids) + 1 > seats:
            return await safe_send_channel(
                self.ctx,
                "You mentioned too many players.",
                hidden=True,
            )

        if await self.services.users.is_waiting():
            return await safe_send_channel(
                self.ctx,
                "You're already in a game.",
                hidden=True,
            )

        found_friends: list[int] = []
        if friends:
            found_friends = await self.ensure_users_exist(friend_xids)
            found_friends = await self.services.games.filter_blocked(
                self.ctx.author_id,
                found_friends,
            )

        fully_seated: bool = False
        new: bool
        if origin:
            assert message_xid
            new = False
            found = await self.services.games.select_by_message_xid(message_xid)
            if not found or await self.services.games.blocked(self.ctx.author_id):
                return await safe_send_channel(
                    self.ctx,
                    "You can not join this game.",
                    hidden=True,
                )

            # Sometimes game posts have Join/Leave buttons on them even though
            # the game has started. This can happen if an interaction fails on
            # Discord's side of things. This makes it appear like a user can still
            # join a game, even though it's already started. We need to handle this
            # by informing the user and updating the game post they tried to join.
            if found["status"] == GameStatus.STARTED.value:
                # inform the player that their interaction failed
                await safe_send_channel(
                    self.ctx,
                    "Sorry, that game has already started.",
                    hidden=True,
                )

                # attempt to update the problematic game post
                message = await safe_fetch_message(
                    self.channel,
                    self.guild.id,
                    message_xid,
                )
                if message:
                    embed = await self.services.games.to_embed()
                    components = await self._fully_seated_components()
                    await safe_update_embed(message, embed=embed, components=components)

                return

            await self.services.games.add_player(self.ctx.author_id)
        else:
            new = await self.services.games.upsert(
                guild_xid=self.ctx.guild_id,
                channel_xid=self.channel.id,
                author_xid=self.ctx.author_id,
                friends=found_friends,
                seats=seats,
                format=format,
            )

        fully_seated = await self.services.games.fully_seated()
        if fully_seated:
            await self._handle_link_creation()
            await self._handle_voice_creation(self.guild.id)

        await self._handle_embed_creation(
            new=new,
            origin=origin,
            fully_seated=fully_seated,
        )

        if fully_seated:
            await self.services.games.record_plays()
            await self._handle_direct_messages()

    async def add_points(self, message: Message, points: int):
        assert self.ctx
        found = await self.services.games.select_by_message_xid(message.id)
        if not found:
            return

        if not await self.services.games.players_included(self.ctx.author_id):
            return await safe_send_channel(
                self.ctx,
                "You are not one of the players in this game.",
                hidden=True,
            )

        await self.services.games.add_points(self.ctx.author_id, points)
        embed = await self.services.games.to_embed()
        await safe_update_embed(message, embed=embed)

    async def create_game(self, players: str, format: Optional[int] = None):
        assert self.ctx
        assert self.channel

        game_format = GameFormat(format or GameFormat.COMMANDER.value)  # type: ignore
        player_xids = list(map(int, re.findall(r"<@!?(\d+)>", players)))
        requested_seats = len(player_xids)
        if requested_seats < 2 or requested_seats > game_format.players:
            return await safe_send_channel(
                self.ctx,
                f"You can't create a {game_format} game with {requested_seats} players.",
                hidden=True,
            )

        found_players: list[int] = []
        found_players = await self.ensure_users_exist(player_xids, exclude_self=False)

        # TODO: Make the players leave any games they're currently pending in?

        if len(found_players) != requested_seats:
            excluded_player_xids = set(player_xids) - set(found_players)
            excluded_players_s = ", ".join(f"<@{xid}>" for xid in excluded_player_xids)
            return await safe_send_channel(
                self.ctx,
                (
                    "Some of the players you mentioned can not"
                    f" be added to a game: {excluded_players_s}"
                ),
                hidden=True,
            )

        assert self.ctx.guild_id
        await self.services.games.upsert(
            guild_xid=self.ctx.guild_id,
            channel_xid=self.channel.id,
            author_xid=found_players[0],
            friends=found_players[1:],
            seats=requested_seats,
            format=game_format.value,
            create_new=True,
        )
        await self._handle_link_creation()
        await self._handle_voice_creation(self.ctx.guild_id)
        await self._handle_embed_creation(new=True, origin=False, fully_seated=True)
        await self.services.games.record_plays()
        await self._handle_direct_messages()

    async def _handle_link_creation(self):
        spelltable_link = await self.bot.create_spelltable_link()
        await self.services.games.make_ready(spelltable_link)

    async def _handle_voice_creation(self, guild_xid: int):
        if not await self.services.guilds.should_voice_create():
            return

        settings = Settings()
        category = await safe_ensure_voice_category(
            self.bot,
            guild_xid,
            settings.VOICE_CATEGORY_PREFIX,
        )
        if not category:
            return

        game_id = await self.services.games.current_id()
        voice_channel = await safe_create_voice_channel(
            self.bot,
            guild_xid,
            f"Game-SB{game_id}",
            category,
        )
        if not voice_channel:
            return

        # This can fail, but it's ok if it does, users don't NEED
        # an invite link to find their game's voice channel.
        voice_invite_link = await safe_create_invite(
            voice_channel,
            guild_xid,
            settings.VOICE_INVITE_EXPIRE_TIME_S,
        )
        await self.services.games.set_voice(voice_channel.id, voice_invite_link)

    async def _pending_components(self):
        buttons = [
            comp.create_button(
                style=ButtonStyle.blurple,
                emoji="✋",
                label="Join this game!",
                custom_id="join",
            ),
            comp.create_button(
                style=ButtonStyle.gray,
                emoji="🚫",
                label="Leave",
                custom_id="leave",
            ),
        ]
        action_row = comp.create_actionrow(*buttons)
        return [action_row]

    async def _fully_seated_components(self):
        if not await self.services.guilds.should_show_points():
            return []
        select = comp.create_select(
            options=[
                comp.create_select_option("No points", value="0", emoji="0️⃣"),
                comp.create_select_option("One point", value="1", emoji="1️⃣"),
                comp.create_select_option("Two points", value="2", emoji="2️⃣"),
                comp.create_select_option("Three points", value="3", emoji="3️⃣"),
                comp.create_select_option("Four points", value="4", emoji="4️⃣"),
                comp.create_select_option("Five points", value="5", emoji="5️⃣"),
                comp.create_select_option("Six points", value="6", emoji="6️⃣"),
                comp.create_select_option("Seven points", value="7", emoji="7️⃣"),
                comp.create_select_option("Eight points", value="8", emoji="8️⃣"),
                comp.create_select_option("Nine points", value="9", emoji="9️⃣"),
                comp.create_select_option("Ten points", value="10", emoji="🔟"),
            ],
            placeholder="How many points do you have to report?",
            custom_id="points",
        )
        action_row = comp.create_actionrow(select)
        return [action_row]

    async def _handle_embed_creation(self, new: bool, origin: bool, fully_seated: bool):
        assert self.ctx
        assert self.guild
        assert self.channel

        # build the game post's embed and components:
        embed: discord.Embed = await self.services.games.to_embed()
        components: list[dict] = (
            await self._fully_seated_components()
            if fully_seated
            else await self._pending_components()
        )

        if new:  # create the initial game post:
            message = await safe_send_channel(
                self.ctx,
                embed=embed,
                components=components,
            )
            if message:
                await self.services.games.set_message_xid(message.id)
            return

        message: Optional[discord.Message] = None
        message_xid = await self.services.games.current_message_xid()
        if message_xid:
            message = await safe_fetch_message(self.channel, self.guild.id, message_xid)

        if not message:  # repost the game post, we lost track of the original:
            message = await safe_send_channel(
                self.ctx,
                embed=embed,
                components=components,
            )
            if message:
                await self.services.games.set_message_xid(message.id)
            return

        # update the existing game post:

        if origin:
            # self.ctx should be a ComponentContext from a button click
            ctx: ComponentContext = cast(ComponentContext, self.ctx)

            # Try to update the origin embed. Sometimes this can fail.
            # If it does fail, we will fallback to doing a standard
            # message.edit() call, which should hopefully at least update
            # the game embed, even if the interaction shows as "failed".
            success = await safe_update_embed_origin(
                ctx,
                embed=embed,
                components=components,
            )
            if success:
                return

        await safe_update_embed(message, embed=embed, components=components)

        if not origin:
            await self._reply_found_embed()

    async def _reply_found_embed(self):
        assert self.ctx
        settings = Settings()
        embed = Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name="I found a game for you!")
        link = await self.services.games.jump_link()
        embed.description = f"You can [jump to the game post]({link}) to see it!"
        embed.color = settings.EMBED_COLOR
        await safe_send_channel(self.ctx, embed=embed, hidden=True)

    async def _handle_direct_messages(self):
        assert self.ctx
        settings = Settings()
        player_xids = await self.services.games.current_player_xids()
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
        new_roles = await self.services.awards.give_awards(self.ctx.guild_id, player_xids)
        assert self.ctx.guild
        for player_xid, new_award in new_roles.items():
            if player_xid not in fetched_players:
                warning = f"Unable to give role {new_award.role} to user <@{player_xid}>"
                await safe_send_channel(self.ctx, warning)
                continue
            player = fetched_players[player_xid]
            await safe_add_role(player, self.ctx.guild, new_award.role)
            await safe_send_user(player, new_award.message)

        # notifiy issues with player permissions
        if failed_xids:
            failures = ", ".join(f"<@!{xid}>" for xid in failed_xids)
            warning = f"Unable to send Direct Messages to some players: {failures}"
            await safe_send_channel(self.ctx, warning)

        # notify moderators about watched players
        assert self.ctx.guild
        mod_role: Optional[discord.Role] = None
        for role in self.ctx.guild.roles:
            if role.name.startswith(settings.MOD_PREFIX):
                mod_role = role
                break

        if not mod_role:
            return

        watch_notes = await self.services.games.watch_notes(player_xids)
        if not watch_notes:
            return

        data = await self.services.games.to_dict()

        embed = Embed()
        embed.set_thumbnail(url=settings.ICO_URL)
        embed.set_author(name="Watched user(s) joined a game")
        embed.color = settings.EMBED_COLOR
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
        assert self.ctx
        found_users: list[int] = []
        for user_xid in user_xids:
            if exclude_self and user_xid == self.ctx.author_id:
                continue
            user = await safe_fetch_user(self.bot, user_xid)
            if not user:
                continue
            data = await self.services.users.upsert(user)
            if data["banned"]:
                continue
            found_users.append(user_xid)
        return found_users
