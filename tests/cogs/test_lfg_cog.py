from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import discord
import pytest
from spellbot.actions import lfg_action
from spellbot.cogs import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat, GameService
from spellbot.models import Channel, Game, Queue, User

from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object, mock_operations

if TYPE_CHECKING:
    from collections.abc import Callable

    from spellbot.client import SpellBot


@pytest.fixture()
def cog(bot: SpellBot) -> LookingForGameCog:
    return LookingForGameCog(bot)


@pytest.mark.asyncio()
class TestCogLookingForGame(InteractionMixin):
    async def test_lfg(self, cog: LookingForGameCog, channel: Channel) -> None:
        await self.run(cog.lfg)
        game = DatabaseSession.query(Game).one()
        user = DatabaseSession.query(User).one()
        assert game.channel_xid == channel.xid
        assert game.guild_xid == self.guild.xid
        assert self.interaction.channel is not None
        user_game = user.game(self.interaction.channel.id)
        assert user_game is not None
        assert user_game.id == game.id

    async def test_lfg_fully_seated(
        self,
        cog: LookingForGameCog,
        add_channel: Callable[..., Channel],
    ) -> None:
        channel = add_channel(
            default_format=GameFormat.MODERN.value,
            default_service=GameService.COCKATRICE.value,
            default_seats=2,
            xid=self.interaction.channel_id,
        )
        game = self.factories.game.create(
            guild=self.guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            service=GameService.COCKATRICE.value,
        )
        self.factories.post.create(guild=self.guild, channel=channel, game=game, message_xid=123)

        other_user = self.factories.user.create(xid=self.interaction.user.id + 1, game=game)
        other_player = mock_discord_object(other_user)

        with mock_operations(lfg_action, users=[other_player]):
            message = MagicMock(spec=discord.Message)
            message.id = game.posts[0].message_xid
            lfg_action.safe_get_partial_message.return_value = message

            await self.run(cog.lfg)

            DatabaseSession.expire_all()
            game = DatabaseSession.query(Game).one()
            mock_call = lfg_action.safe_update_embed
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.STARTED_EMBED_COLOR,
                "description": (
                    "Please check your Direct Messages for your game details.\n\n"
                    f"{self.guild.motd}\n\n{channel.motd}"
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": (
                            f"• <@{self.interaction.user.id}> "
                            f"({self.interaction.user.display_name})\n"
                            f"• <@{other_player.id}> ({other_player.display_name})"
                        ),
                    },
                    {"inline": True, "name": "Format", "value": "Modern"},
                    {
                        "inline": True,
                        "name": "Started at",
                        "value": f"<t:{game.started_at_timestamp}>",
                    },
                    {"inline": False, "name": "Service", "value": "Cockatrice"},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Your game is ready!**",
                "type": "rich",
            }

    async def test_lfg_when_blocked(self, game: Game, user: User) -> None:
        other_user = self.factories.user.create(game=game)
        self.factories.block.create(user_xid=other_user.xid, blocked_user_xid=self.user.xid)

        cog = LookingForGameCog(self.bot)
        await self.run(cog.lfg)

        other_game = DatabaseSession.query(Game).filter(Game.id == game.id).one()
        user_game = DatabaseSession.query(Game).filter(Game.id != game.id).one()
        assert other_game.id != user_game.id

    async def test_lfg_when_already_in_game(self, game: Game, player: User) -> None:
        with mock_operations(lfg_action, users=[mock_discord_object(player)]):
            cog = LookingForGameCog(self.bot)
            await self.run(cog.lfg)

            lfg_action.safe_followup_channel.assert_called_once_with(
                self.interaction,
                "You're already in a game in this channel.",
            )

        found = DatabaseSession.query(User).one()
        assert found.game(self.channel.xid).id == game.id
        assert DatabaseSession.query(Game).count() == 1

    async def test_lfg_with_format(self) -> None:
        cog = LookingForGameCog(self.bot)
        await self.run(cog.lfg, format=GameFormat.MODERN.value)
        assert DatabaseSession.query(Game).one().format == GameFormat.MODERN.value

    async def test_lfg_with_seats(self) -> None:
        cog = LookingForGameCog(self.bot)
        await self.run(cog.lfg, seats=2)
        assert DatabaseSession.query(Game).one().seats == 2

    async def test_lfg_with_friends(self, user: User, message: discord.Message) -> None:
        friend1 = self.factories.user.create()
        friend2 = self.factories.user.create()
        players = [mock_discord_object(x) for x in (self.user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = self.message

            cog = LookingForGameCog(self.bot)
            await self.run(cog.lfg, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        queues = DatabaseSession.query(Queue).all()
        assert len(queues) == 3
        assert all(queue.game_id == game.id for queue in queues)

    async def test_lfg_with_too_many_friends(self, user: User, message: discord.Message) -> None:
        friend1 = self.factories.user.create()
        friend2 = self.factories.user.create()
        friend3 = self.factories.user.create()
        friend4 = self.factories.user.create()
        players = [mock_discord_object(x) for x in (self.user, friend1, friend2, friend3, friend4)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = self.message

            cog = LookingForGameCog(self.bot)
            await self.run(
                cog.lfg,
                friends=f"<@{friend1.xid}><@{friend2.xid}><@{friend3.xid}><@{friend4.xid}>",
            )

        assert not DatabaseSession.query(Game).one_or_none()

    async def test_lfg_multiple_times(self, cog: LookingForGameCog, channel: Channel) -> None:
        await self.run(cog.lfg)
        await self.run(cog.lfg)
        assert DatabaseSession.query(Game).count() == 1


# TODO: Refactor all this:
# @pytest.mark.asyncio()
# class TestCogLookingForGameJoinButton(ComponentContextMixin):
#     async def test_join(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild, motd=None)
#         game = ctx_game(self.ctx, guild, channel)
#         user = ctx_user(self.ctx)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             mock_call = lfg_action.safe_update_embed_origin
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.PENDING_EMBED_COLOR,
#                 "description": (
#                     "_A SpellTable link will be created when all players have joined._\n"
#                     "\n"
#                     f"{guild.motd}"
#                 ),
#                 "fields": [
#                     {"inline": False, "name": "Players", "value": f"<@{user.xid}>"},
#                     {"inline": True, "name": "Format", "value": "Commander"},
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Waiting for 3 more players to join...**",
#                 "type": "rich",
#             }

#     async def test_join_with_show_points(self, snapshot: SnapshotAssertion):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, show_points=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             DatabaseSession.expire_all()
#             game = DatabaseSession.query(Game).one()
#             mock_call = lfg_action.safe_update_embed_origin
#             mock_call.assert_called_once()
#             assert mock_call.call_args_list[0].kwargs["components"] == snapshot
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.STARTED_EMBED_COLOR,
#                 "description": (
#                     "Please check your Direct Messages for your game details.\n\n"
#                     "When your game is over use the drop down to report your points.\n\n"
#                     f"{guild.motd}\n\n{channel.motd}"
#                 ),
#                 "fields": [
#                     {
#                         "inline": False,
#                         "name": "Players",
#                         "value": f"<@{self.ctx.author_id}>, <@{other_user.xid}>",
#                     },
#                     {"inline": True, "name": "Format", "value": "Commander"},
#                     {
#                         "inline": True,
#                         "name": "Started at",
#                         "value": f"<t:{game.started_at_timestamp}>",
#                     },
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Your game is ready!**",
#                 "type": "rich",
#             }

#     async def test_join_when_blocked(self):
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel)
#         author_user = ctx_user(self.ctx)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)
#         self.factories.block.create(
#             user_xid=other_user.xid,
#             blocked_user_xid=author_user.xid,
#         )

#         with mock_operations(lfg_action, users=[author_user, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             mock_call = lfg_action.safe_send_user
#             mock_call.assert_called_once_with(
#                 self.ctx.author,
#                 "You can not join this game.",
#             )

#         assert DatabaseSession.query(Game).count() == 1

#     async def test_join_when_started(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         ctx_game(self.ctx, guild, channel, status=GameStatus.STARTED.value)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_called_once_with(
#                 self.ctx.author,
#                 "Sorry, that game has already started.",
#             )
#             lfg_action.safe_update_embed.assert_called_once_with(
#                 ANY,
#                 components=[],
#                 embed=ANY,
#             )

#     async def test_join_when_started_and_fetch_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         ctx_game(self.ctx, guild, channel, status=GameStatus.STARTED.value)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_called_once_with(
#                 self.ctx.author,
#                 "Sorry, that game has already started.",
#             )
#             lfg_action.safe_update_embed.assert_not_called()

#     async def test_join_when_update_embed_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel)
#         user = ctx_user(self.ctx)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             lfg_action.safe_update_embed_origin.return_value = False

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             mock_call = lfg_action.safe_update_embed_origin
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.PENDING_EMBED_COLOR,
#                 "description": (
#                     "_A SpellTable link will be created when all players have joined._\n"
#                     "\n"
#                     f"{guild.motd}\n\n{channel.motd}"
#                 ),
#                 "fields": [
#                     {"inline": False, "name": "Players", "value": f"<@{user.xid}>"},
#                     {"inline": True, "name": "Format", "value": "Commander"},
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Waiting for 3 more players to join...**",
#                 "type": "rich",
#             }


# @pytest.mark.asyncio()
# class TestCogLookingForGameUserNotifications(InteractionContextMixin):
#     async def test_happy_path(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2, motd=None)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             DatabaseSession.expire_all()
#             game = DatabaseSession.query(Game).one()
#             mock_call = lfg_action.safe_send_user
#             mock_call.assert_any_call(self.ctx.author, embed=ANY)
#             mock_call.assert_any_call(other_player, embed=ANY)
#             embed = mock_call.call_args_list[0].kwargs["embed"].to_dict()
#             assert embed == {
#                 "color": self.settings.STARTED_EMBED_COLOR,
#                 "description": (
#                     f"[Join your SpellTable game now!]({game.spelltable_link})"
#                     f" (or [spectate this game]({game.spectate_link}))\n\n"
#                     f"You can also [jump to the original game post]({game.jump_link}) in"
#                     f" <#{game.channel_xid}>."
#                 ),
#                 "fields": [
#                     {
#                         "inline": False,
#                         "name": "Players",
#                         "value": f"<@{self.ctx.author_id}>, <@{other_user.xid}>",
#                     },
#                     {"inline": True, "name": "Format", "value": game.format_name},
#                     {
#                         "inline": True,
#                         "name": "Started at",
#                         "value": f"<t:{game.started_at_timestamp}>",
#                     },
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Your game is ready!**",
#                 "type": "rich",
#             }

#     async def test_lfg_when_mentioned_friend_is_blocked_by_current_player(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=4, motd=None)
#         game = ctx_game(self.ctx, guild, channel)
#         blocking_user = self.factories.user.create(
#             xid=self.ctx.author_id + 2,
#             game=game,
#         )
#         blocking_discord_user = mock_discord_user(blocking_user)

#         blocked_user = self.factories.user.create(xid=self.ctx.author_id + 1)
#         blocked_discord_user = mock_discord_user(blocked_user)

#         self.factories.block.create(
#             user_xid=blocking_user.xid,
#             blocked_user_xid=blocked_user.xid,
#         )

#         with mock_operations(
#             lfg_action,
#             users=[self.ctx.author, blocking_discord_user, blocked_discord_user],
#         ):
#             new_post = MagicMock(spec=discord.Message)
#             new_post.id = game.message_xid + 1
#             lfg_action.safe_send_channel.return_value = new_post

#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx, friends=f"<@{blocked_user.xid}>")

#         DatabaseSession.expire_all()
#         assert DatabaseSession.query(Game).count() == 2
#         blocked_user = DatabaseSession.query(User).get(blocked_discord_user.id)
#         blocking_user = DatabaseSession.query(User).get(blocking_discord_user.id)
#         assert blocked_user and blocked_user.game_id is not None
#         assert blocking_user and blocking_user.game_id != blocked_user.game_id

#     async def test_when_fetch_user_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_fetch_user = AsyncMock(return_value=None)

#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_not_called()
#             # TODO: Refactor how this works.
#             # lfg_interaction.safe_send_channel.assert_any_call(
#             #     self.ctx,
#             #     (
#             #         "Unable to send Direct Messages to some players:"
#             #         f" <@!{other_player.id}>, <@!{self.ctx.author.id}>"
#             #     ),
#             # )


# @pytest.mark.asyncio()
# class TestCogLookingForGameUserAwards(InteractionContextMixin):
#     async def test_happy_path(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)
#         guild_award = self.factories.guild_award.create(guild=guild, count=1)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_add_role.assert_any_call(
#                 self.ctx.author,
#                 self.ctx.guild,
#                 guild_award.role,
#                 False,
#             )
#             lfg_action.safe_add_role.assert_any_call(
#                 other_player,
#                 self.ctx.guild,
#                 guild_award.role,
#                 False,
#             )
#             lfg_action.safe_send_user.assert_any_call(
#                 self.ctx.author,
#                 guild_award.message,
#             )
#             lfg_action.safe_send_user.assert_any_call(
#                 other_player,
#                 guild_award.message,
#             )

#         awards = DatabaseSession.query(UserAward).all()
#         assert len(awards) == 2
#         for award in awards:
#             assert award.guild_award_id == guild_award.id

#     async def test_fetch_user_fails(self):
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         # other_player = \
#         mock_discord_user(other_user)
#         guild_award = self.factories.guild_award.create(guild=guild, count=1)

#         with mock_operations(lfg_action):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             # TODO: Refactor how this works.
#             # lfg_interaction.safe_send_channel.assert_any_call(
#             #     self.ctx,
#             #     (
#             #         f"Unable to give role {guild_award.role}"
#             #         f" to user <@{self.ctx.author_id}>"
#             #     ),
#             # )
#             # lfg_interaction.safe_send_channel.assert_any_call(
#             #     self.ctx,
#             #     f"Unable to give role {guild_award.role} to user <@{other_player.id}>",
#             # )
#             lfg_action.safe_add_role.assert_not_called()
#             lfg_action.safe_send_user.assert_not_called()

#         awards = DatabaseSession.query(UserAward).all()
#         assert len(awards) == 2
#         for award in awards:
#             assert award.guild_award_id == guild_award.id


# @pytest.mark.asyncio()
# class TestCogLookingForGameWatchedUsers(InteractionContextMixin):
#     async def test_happy_path(self, monkeypatch):
#         assert self.ctx.guild
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2, motd=None)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)
#         watch = self.factories.watch.create(guild_xid=guild.xid, user_xid=other_user.xid)
#         db_mod = self.factories.user.create(xid=self.ctx.author_id + 2)
#         dpy_mod = mock_discord_user(db_mod)
#         mod_role = MagicMock(spec=discord.Role)
#         mod_role.name = self.settings.MOD_PREFIX
#         mod_role.members = [dpy_mod]
#         other_role = MagicMock(spec=discord.Role)
#         other_role.name = "nothing"
#         monkeypatch.setattr(self.ctx.guild, "roles", [other_role, mod_role])

#         with mock_operations(
#             lfg_action,
#             users=[
#                 self.ctx.author,
#                 other_player,
#                 dpy_mod,
#             ],
#         ):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             DatabaseSession.expire_all()
#             game = DatabaseSession.query(Game).one()
#             mock_call = lfg_action.safe_send_user
#             mock_call.assert_any_call(dpy_mod, embed=ANY)
#             assert mock_call.call_args_list[-1].kwargs["embed"].to_dict() == {
#                 "author": {"name": "Watched user(s) joined a game"},
#                 "color": self.settings.STARTED_EMBED_COLOR,
#                 "description": (
#                     f"[⇤ Jump to the game post]({game.jump_link})\n"
#                     f"[➤ Spectate the game on SpellTable]({game.spectate_link})\n\n"
#                     "**Users:**\n"
#                     f"• <@{other_player.id}>: {watch.note}"
#                 ),
#                 "thumbnail": {"url": self.settings.ICO_URL},
#                 "type": "rich",
#             }

#     async def test_when_no_mod_role(self, monkeypatch):
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         self.factories.watch.create(guild_xid=guild.xid, user_xid=other_user.xid)
#         db_mod = self.factories.user.create(xid=self.ctx.author_id + 2)
#         dpy_mod = mock_discord_user(db_mod)
#         monkeypatch.setattr(self.ctx.guild, "roles", [])

#         with mock_operations(lfg_action, users=[dpy_mod]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_not_called()

#     async def test_when_no_watched_users(self, monkeypatch):
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         db_mod = self.factories.user.create(xid=self.ctx.author_id + 2)
#         dpy_mod = mock_discord_user(db_mod)
#         mod_role = MagicMock(spec=discord.Role)
#         mod_role.name = self.settings.MOD_PREFIX
#         mod_role.members = [dpy_mod]
#         monkeypatch.setattr(self.ctx.guild, "roles", [mod_role])

#         with mock_operations(lfg_action, users=[dpy_mod]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_not_called()


# @pytest.mark.asyncio()
# class TestCogLookingForGameLeaveButton(ComponentContextMixin):
#     async def test_leave(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel)
#         ctx_user(self.ctx, game=game)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             leave_action.safe_fetch_text_channel.return_value = self.ctx.channel
#             leave_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             mock_call = leave_action.safe_update_embed_origin
#             mock_call.assert_called_once()
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.PENDING_EMBED_COLOR,
#                 "description": (
#                     "_A SpellTable link will be created when all players have joined._\n"
#                     "\n"
#                     f"{guild.motd}\n\n{channel.motd}"
#                 ),
#                 "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Waiting for 4 more players to join...**",
#                 "type": "rich",
#             }

#     async def test_leave_when_not_in_game(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         ctx_user(self.ctx)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             leave_action.safe_update_embed_origin.assert_not_called()
#             leave_action.safe_send_channel.assert_not_called()

#     async def test_leave_when_missing_game_post(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, message_xid=None)
#         ctx_user(self.ctx, game=game)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             leave_action.safe_update_embed_origin.assert_not_called()
#             leave_action.safe_send_channel.assert_not_called()

#     async def test_leave_message_mismatch(self):
#         assert self.ctx.message
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         wrong_message_xid = self.ctx.message.id + 1
#         game = ctx_game(self.ctx, guild, channel, seats=2, message_xid=wrong_message_xid)
#         ctx_user(self.ctx, xid=self.ctx.author_id, game=game)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             leave_action.safe_fetch_text_channel.return_value = self.ctx.channel
#             leave_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             leave_action.safe_send_user.assert_called_once_with(
#                 self.ctx.author,
#                 "You're not in that game. Use the /leave command to leave a game.",
#             )


# @pytest.mark.asyncio()
# class TestCogLookingForGameVoiceCreate(ComponentContextMixin):
#     async def test_join_happy_path(self):
#         assert self.ctx.guild
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, voice_create=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = ctx_user(self.ctx, xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             voice_channel = build_voice_channel(self.ctx.guild)
#             lfg_action.safe_create_voice_channel.return_value = voice_channel

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#         found = DatabaseSession.query(Game).one()
#         assert found.voice_xid == voice_channel.id

#     async def test_join_when_category_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, voice_create=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = ctx_user(self.ctx, xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             lfg_action.safe_ensure_voice_category.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#         found = DatabaseSession.query(Game).one()
#         assert not found.voice_xid

#     async def test_join_when_channel_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, voice_create=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = ctx_user(self.ctx, xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             lfg_action.safe_create_voice_channel.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#         found = DatabaseSession.query(Game).one()
#         assert not found.voice_xid
