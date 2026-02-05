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
from spellbot.models import Channel, Game, GameStatus, Guild, Queue, User
from spellbot.views import GameView
from tests.fixtures import Factories, run_command
from tests.mocks import mock_discord_object, mock_operations

if TYPE_CHECKING:
    from collections.abc import Callable

    from spellbot import SpellBot
    from spellbot.settings import Settings

pytestmark = pytest.mark.use_db

SPELLTABLE_PENDING_MSG = (
    "_A [SpellTable](https://spelltable.wizards.com/) link will "
    "be created when all players have joined._"
)


@pytest.fixture
def cog(bot: SpellBot) -> LookingForGameCog:
    return LookingForGameCog(bot)


@pytest.mark.asyncio
class TestCogLookingForGame:
    async def test_lfg(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        with mock_operations(lfg_action):
            message = MagicMock(spec=discord.Message)
            message.id = 123
            lfg_action.safe_followup_channel.return_value = message

            await run_command(cog.lfg, interaction)

            lfg_action.safe_followup_channel.assert_called_once_with(
                interaction,
                content=None,
                embed=ANY,
                view=ANY,
                allowed_mentions=ANY,
            )
            # check that the view (join/leave buttons) exists for pending games:
            assert isinstance(lfg_action.safe_followup_channel.call_args.kwargs["view"], GameView)

        user = DatabaseSession.query(User).one()
        game = DatabaseSession.query(Game).one()
        assert game.channel_xid == channel.xid
        assert game.guild_xid == guild.xid
        assert interaction.channel is not None
        user_game = user.game(interaction.channel.id)
        assert user_game is not None
        assert user_game.id == game.id

    async def test_lfg_fully_seated(
        self,
        cog: LookingForGameCog,
        add_channel: Callable[..., Channel],
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        settings: Settings,
    ) -> None:
        channel = add_channel(
            default_format=GameFormat.MODERN.value,
            default_service=GameService.COCKATRICE.value,
            default_seats=2,
            xid=interaction.channel_id,
        )
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            service=GameService.COCKATRICE.value,
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=123)

        other_user = factories.user.create(xid=interaction.user.id + 1, game=game)
        other_player = mock_discord_object(other_user)

        with mock_operations(lfg_action, users=[other_player]):
            message = MagicMock(spec=discord.Message)
            message.id = game.posts[0].message_xid
            lfg_action.safe_get_partial_message.return_value = message

            await run_command(cog.lfg, interaction)

            DatabaseSession.expire_all()
            game = DatabaseSession.query(Game).one()
            mock_call = lfg_action.safe_update_embed
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": settings.STARTED_EMBED_COLOR,
                "description": (
                    "Please check your Direct Messages for your game details.\n\n"
                    f"{guild.motd}\n\n{channel.motd}"
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": (
                            f"• <@{interaction.user.id}> "
                            f"({interaction.user.display_name})\n"
                            f"• <@{other_player.id}> ({other_player.display_name})"
                        ),
                    },
                    {"inline": True, "name": "Format", "value": "Modern"},
                    {
                        "inline": True,
                        "name": "Started at",
                        "value": f"<t:{game.started_at_timestamp}>",
                    },
                    {"inline": False, "name": "Support SpellBot", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Cockatrice"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Your game is ready!**",
                "type": "rich",
                "flags": 0,
            }
            # check that the view (join/leave buttons) is removed from fully seated games:
            assert mock_call.call_args_list[0].kwargs["view"] is None

    async def test_lfg_when_blocked(
        self,
        game: Game,
        user: User,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        other_user = factories.user.create(game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)

        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction)

        other_game = DatabaseSession.query(Game).filter(Game.id == game.id).one()
        user_game = DatabaseSession.query(Game).filter(Game.id != game.id).one()
        assert other_game.id != user_game.id

    async def test_lfg_when_already_in_game(
        self,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        channel: Channel,
        bot: SpellBot,
    ) -> None:
        with mock_operations(lfg_action, users=[mock_discord_object(player)]):
            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction)

            lfg_action.safe_followup_channel.assert_called_once_with(
                interaction,
                "You're already in a game in this channel.",
            )

        found = DatabaseSession.query(User).one()
        assert found.game(channel.xid).id == game.id
        assert DatabaseSession.query(Game).count() == 1

    async def test_lfg_with_format(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
    ) -> None:
        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction, format=GameFormat.MODERN.value)
        assert DatabaseSession.query(Game).one().format == GameFormat.MODERN.value

    async def test_lfg_with_seats(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
    ) -> None:
        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction, seats=2)
        assert DatabaseSession.query(Game).one().seats == 2

    async def test_lfg_with_friends(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        players = [mock_discord_object(x) for x in (user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        queues = DatabaseSession.query(Queue).all()
        assert len(queues) == 3
        assert all(queue.game_id == game.id for queue in queues)

    async def test_lfg_with_friends_blocked(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        factories.block.create(user_xid=user.xid, blocked_user_xid=friend1.xid)
        players = [mock_discord_object(x) for x in (user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        queues = DatabaseSession.query(Queue).all()
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

    async def test_lfg_with_friends_blocked_by(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        factories.block.create(user_xid=friend1.xid, blocked_user_xid=user.xid)
        players = [mock_discord_object(x) for x in (user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        queues = DatabaseSession.query(Queue).all()
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

    async def test_lfg_with_too_many_friends(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        friend3 = factories.user.create()
        friend4 = factories.user.create()
        players = [mock_discord_object(x) for x in (user, friend1, friend2, friend3, friend4)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(
                cog.lfg,
                interaction,
                friends=f"<@{friend1.xid}><@{friend2.xid}><@{friend3.xid}><@{friend4.xid}>",
            )

        assert not DatabaseSession.query(Game).one_or_none()

    async def test_lfg_multiple_times(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        await run_command(cog.lfg, interaction)
        await run_command(cog.lfg, interaction)
        assert DatabaseSession.query(Game).count() == 1

    async def test_rematch(
        self,
        cog: LookingForGameCog,
        user: User,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        friend = factories.user.create()
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            service=GameService.GIRUDO.value,
            status=GameStatus.STARTED.value,
            started_at=datetime.now(tz=UTC),
        )
        message = MagicMock(spec=discord.Message)
        message.id = 123
        factories.post.create(
            guild=guild,
            channel=channel,
            game=game,
            message_xid=message.id,
        )
        factories.play.create(user_xid=user.xid, game_id=game.id)
        factories.play.create(user_xid=friend.xid, game_id=game.id)
        players = [mock_discord_object(x) for x in (user, friend)]

        with mock_operations(lfg_action, users=players):
            message = MagicMock(spec=discord.Message)
            message.id = 456
            lfg_action.safe_followup_channel.return_value = message

            await run_command(cog.rematch, interaction)

            lfg_action.safe_followup_channel.assert_called_once_with(
                interaction,
                content=None,
                embed=ANY,
                view=ANY,
                allowed_mentions=ANY,
            )

        DatabaseSession.expire_all()
        assert DatabaseSession.query(Game).count() == 2


@pytest.mark.asyncio
class TestCogLookingForGameJoinButton:
    async def test_join(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        settings: Settings,
    ) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_original_response",
                return_value=message,
            ),
        ):
            lfg_action.safe_update_embed_origin.return_value = message
            interaction.message = message
            view = GameView(bot=bot)

            await view.join.callback(interaction)

            mock_call = lfg_action.safe_update_embed_origin
            mock_call.assert_called_once()
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (f"{SPELLTABLE_PENDING_MSG}\n\n{guild.motd}\n\n{channel.motd}"),
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
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: SpellTable"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_join_when_no_original_response(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_original_response",
                return_value=None,
            ),
        ):
            lfg_action.safe_update_embed_origin.return_value = message
            interaction.message = message
            view = GameView(bot=bot)

            await view.join.callback(interaction)

            lfg_action.safe_update_embed_origin.assert_not_called()

    async def test_join_when_blocked(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        other_user = factories.user.create(xid=user.xid + 1, game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)

        with mock_operations(
            lfg_action,
            users=[
                mock_discord_object(user),
                mock_discord_object(other_user),
            ],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join.callback(interaction)

            lfg_action.safe_send_user.assert_called_once_with(
                interaction.user,
                "You can not join this game.",
            )

        assert DatabaseSession.query(Game).count() == 1

    async def test_join_when_started(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        # fully seat and start the game
        factories.user.create(game=game)
        factories.user.create(game=game)
        factories.user.create(game=game)
        factories.user.create(game=game)
        game.started_at = datetime.now(tz=UTC)  # type: ignore
        game.status = GameStatus.STARTED.value
        DatabaseSession.commit()

        # then try to join it
        with mock_operations(
            lfg_action,
            users=[mock_discord_object(user)],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join.callback(interaction)

            lfg_action.safe_send_user.assert_called_once_with(
                interaction.user,
                "Sorry, that game has already started.",
            )

        assert DatabaseSession.query(Game).count() == 1

    async def test_join_when_defer_fails(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_defer_interaction",
                return_value=False,
            ),
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join.callback(interaction)

            lfg_action.safe_update_embed_origin.assert_not_called()
