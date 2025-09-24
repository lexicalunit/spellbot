from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock, patch

import discord
import pytest

from spellbot.actions import lfg_action
from spellbot.cogs import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat, GameService
from spellbot.models import Channel, Game, GameStatus, Queue, User
from spellbot.views import GameView
from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object, mock_operations

if TYPE_CHECKING:
    from collections.abc import Callable

    from spellbot.client import SpellBot

pytestmark = pytest.mark.use_db


@pytest.fixture
def cog(bot: SpellBot) -> LookingForGameCog:
    return LookingForGameCog(bot)


@pytest.mark.asyncio
class TestCogLookingForGame(InteractionMixin):
    async def test_lfg(self, cog: LookingForGameCog, channel: Channel) -> None:
        with mock_operations(lfg_action):
            message = MagicMock(spec=discord.Message)
            message.id = 123
            lfg_action.safe_followup_channel.return_value = message

            await self.run(cog.lfg)

            lfg_action.safe_followup_channel.assert_called_once_with(
                self.interaction,
                content=None,
                embed=ANY,
                view=ANY,
            )
            # check that the view (join/leave buttons) exists for pending games:
            assert isinstance(lfg_action.safe_followup_channel.call_args.kwargs["view"], GameView)

        user = DatabaseSession.query(User).one()
        game = DatabaseSession.query(Game).one()
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
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Your game is ready!**",
                "type": "rich",
                "flags": 0,
            }
            # check that the view (join/leave buttons) is removed from fully seated games:
            assert mock_call.call_args_list[0].kwargs["view"] is None

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

    async def test_lfg_with_friends_blocked(self, user: User, message: discord.Message) -> None:
        friend1 = self.factories.user.create()
        friend2 = self.factories.user.create()
        self.factories.block.create(user_xid=self.user.xid, blocked_user_xid=friend1.xid)
        players = [mock_discord_object(x) for x in (self.user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = self.message

            cog = LookingForGameCog(self.bot)
            await self.run(cog.lfg, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        queues = DatabaseSession.query(Queue).all()
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

    async def test_lfg_with_friends_blocked_by(self, user: User, message: discord.Message) -> None:
        friend1 = self.factories.user.create()
        friend2 = self.factories.user.create()
        self.factories.block.create(user_xid=friend1.xid, blocked_user_xid=self.user.xid)
        players = [mock_discord_object(x) for x in (self.user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = self.message

            cog = LookingForGameCog(self.bot)
            await self.run(cog.lfg, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        queues = DatabaseSession.query(Queue).all()
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

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


@pytest.mark.asyncio
class TestCogLookingForGameJoinButton(InteractionMixin):
    async def test_join(self, game: Game, user: User, message: discord.Message) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_original_response",
                return_value=message,
            ),
        ):
            lfg_action.safe_update_embed_origin.return_value = message
            self.interaction.message = message
            view = GameView(bot=self.bot)

            await view.join.callback(self.interaction)

            mock_call = lfg_action.safe_update_embed_origin
            mock_call.assert_called_once()
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.PENDING_EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    f"\n{self.guild.motd}\n"
                    f"\n{self.channel.motd}"
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"• <@{user.xid}> (user-{user.xid})",
                    },
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_join_when_no_original_response(
        self,
        game: Game,
        user: User,
        message: discord.Message,
    ) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_original_response",
                return_value=None,
            ),
        ):
            lfg_action.safe_update_embed_origin.return_value = message
            self.interaction.message = message
            view = GameView(bot=self.bot)

            await view.join.callback(self.interaction)

            lfg_action.safe_update_embed_origin.assert_not_called()

    async def test_join_when_blocked(
        self,
        game: Game,
        user: User,
        message: discord.Message,
    ) -> None:
        other_user = self.factories.user.create(xid=user.xid + 1, game=game)
        self.factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)

        with mock_operations(
            lfg_action,
            users=[
                mock_discord_object(user),
                mock_discord_object(other_user),
            ],
        ):
            self.interaction.message = message
            view = GameView(bot=self.bot)

            await view.join.callback(self.interaction)

            lfg_action.safe_send_user.assert_called_once_with(
                self.interaction.user,
                "You can not join this game.",
            )

        assert DatabaseSession.query(Game).count() == 1

    async def test_join_when_started(
        self,
        game: Game,
        user: User,
        message: discord.Message,
    ) -> None:
        # fully seat and start the game
        self.factories.user.create(game=game)
        self.factories.user.create(game=game)
        self.factories.user.create(game=game)
        self.factories.user.create(game=game)
        game.started_at = datetime.now(tz=UTC)  # type: ignore
        game.status = GameStatus.STARTED.value
        DatabaseSession.commit()

        # then try to join it
        with mock_operations(
            lfg_action,
            users=[mock_discord_object(user)],
        ):
            self.interaction.message = message
            view = GameView(bot=self.bot)

            await view.join.callback(self.interaction)

            lfg_action.safe_send_user.assert_called_once_with(
                self.interaction.user,
                "Sorry, that game has already started.",
            )

        assert DatabaseSession.query(Game).count() == 1
