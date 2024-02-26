from __future__ import annotations

from typing import Callable
from unittest.mock import MagicMock, PropertyMock, patch

import discord
import pytest
from spellbot import SpellBot
from spellbot.actions import lfg_action
from spellbot.cogs import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat
from spellbot.models import Channel, Game, Play
from spellbot.settings import Settings
from spellbot.views import StartedGameSelect, StartedGameView

from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object, mock_operations


@pytest.fixture()
def cog(bot: SpellBot) -> LookingForGameCog:
    return LookingForGameCog(bot)


@pytest.mark.asyncio()
class TestCogLookingForGamePoints(InteractionMixin):
    async def test_points(
        self,
        cog: LookingForGameCog,
        settings: Settings,
        add_channel: Callable[..., Channel],
    ) -> None:
        channel = add_channel(
            default_seats=2,
            default_format=GameFormat.MODERN.value,
            xid=self.interaction.channel_id,
            show_points=True,
        )
        game = self.factories.game.create(
            guild=self.guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            message_xid=123,
        )
        user = self.factories.user.create(xid=self.interaction.user.id)
        other_user = self.factories.user.create(xid=self.interaction.user.id + 1, game=game)
        other_player = mock_discord_object(other_user)
        message = MagicMock(spec=discord.Message, id=game.message_xid)
        self.interaction.original_response.return_value = message

        with patch.object(
            StartedGameSelect,
            "values",
            new_callable=PropertyMock,
        ) as values:
            view = StartedGameView(bot=self.bot)
            select = view._children[0]
            values.return_value = ["5"]
            with mock_operations(lfg_action, users=[other_player]):
                lfg_action.safe_get_partial_message.return_value = message

                await self.run(cog.lfg)

                DatabaseSession.expire_all()
                game = DatabaseSession.query(Game).one()
                assert lfg_action.safe_update_embed.call_args_list[0].kwargs["embed"].to_dict() == {
                    "color": self.settings.STARTED_EMBED_COLOR,
                    "description": (
                        "Please check your Direct Messages for your SpellTable link.\n\n"
                        "When your game is over use the drop down to report your points.\n\n"
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
                    ],
                    "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                    "thumbnail": {"url": self.settings.THUMB_URL},
                    "title": "**Your game is ready!**",
                    "type": "rich",
                }

                await select.callback(self.interaction)

                found = DatabaseSession.query(Play).filter(Play.user_xid == user.xid).one()
                assert found.points == 5

                assert lfg_action.safe_update_embed.call_args_list[1].kwargs["embed"].to_dict() == {
                    "color": settings.STARTED_EMBED_COLOR,
                    "description": (
                        "Please check your Direct Messages for your SpellTable link.\n\n"
                        "When your game is over use the drop down to report your points.\n\n"
                        f"{self.guild.motd}\n\n{channel.motd}"
                    ),
                    "fields": [
                        {
                            "inline": False,
                            "name": "Players",
                            "value": (
                                f"• <@{self.interaction.user.id}> ({self.interaction.user.display_name}) - 5 points\n"
                                f"• <@{other_user.xid}> ({other_user.name})"
                            ),
                        },
                        {"inline": True, "name": "Format", "value": "Modern"},
                        {
                            "inline": True,
                            "name": "Started at",
                            "value": f"<t:{game.started_at_timestamp}>",
                        },
                    ],
                    "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                    "thumbnail": {"url": settings.THUMB_URL},
                    "title": "**Your game is ready!**",
                    "type": "rich",
                }

    async def test_points_when_message_not_found(
        self,
        cog: LookingForGameCog,
        settings: Settings,
        add_channel: Callable[..., Channel],
    ) -> None:
        channel = add_channel(
            default_seats=2,
            default_format=GameFormat.MODERN.value,
            xid=self.interaction.channel_id,
            show_points=True,
        )
        game = self.factories.game.create(
            guild=self.guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            message_xid=123,
        )
        user = self.factories.user.create(xid=self.interaction.user.id)
        other_user = self.factories.user.create(xid=self.interaction.user.id + 1, game=game)
        other_player = mock_discord_object(other_user)
        message = MagicMock(spec=discord.Message, id=game.message_xid)
        self.interaction.original_response.return_value = message

        with patch.object(
            StartedGameSelect,
            "values",
            new_callable=PropertyMock,
        ) as values:
            view = StartedGameView(bot=self.bot)
            select = view._children[0]
            values.return_value = ["5"]
            with mock_operations(lfg_action, users=[other_player]):
                lfg_action.safe_get_partial_message.return_value = message

                await self.run(cog.lfg)

                DatabaseSession.expire_all()
                game = DatabaseSession.query(Game).one()
                assert lfg_action.safe_update_embed.call_args_list[0].kwargs["embed"].to_dict() == {
                    "color": self.settings.STARTED_EMBED_COLOR,
                    "description": (
                        "Please check your Direct Messages for your SpellTable link.\n\n"
                        "When your game is over use the drop down to report your points.\n\n"
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
                    ],
                    "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                    "thumbnail": {"url": self.settings.THUMB_URL},
                    "title": "**Your game is ready!**",
                    "type": "rich",
                }

                message.id += 1  # make it so the message isn't findable in our DB
                lfg_action.safe_get_partial_message.return_value = message
                self.interaction.original_response.return_value = message
                lfg_action.safe_update_embed.reset_mock()

                await select.callback(self.interaction)

                found = DatabaseSession.query(Play).filter(Play.user_xid == user.xid).one()
                assert found.points is None
                lfg_action.safe_update_embed.assert_not_called()

    async def test_points_when_not_in_game(
        self,
        cog: LookingForGameCog,
        settings: Settings,
        add_channel: Callable[..., Channel],
    ) -> None:
        channel = add_channel(
            default_seats=2,
            default_format=GameFormat.MODERN.value,
            xid=self.interaction.channel_id,
            show_points=True,
        )
        game = self.factories.game.create(
            guild=self.guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            message_xid=123,
        )
        self.factories.user.create(xid=self.interaction.user.id)
        other_user = self.factories.user.create(xid=self.interaction.user.id + 1, game=game)
        other_player = mock_discord_object(other_user)
        message = MagicMock(spec=discord.Message, id=game.message_xid)
        self.interaction.original_response.return_value = message

        outside_user = self.factories.user.create(xid=self.interaction.user.id + 2)
        outside_player = mock_discord_object(outside_user)

        with patch.object(
            StartedGameSelect,
            "values",
            new_callable=PropertyMock,
        ) as values:
            view = StartedGameView(bot=self.bot)
            select = view._children[0]
            values.return_value = ["5"]
            with mock_operations(lfg_action, users=[other_player, outside_player]):
                lfg_action.safe_get_partial_message.return_value = message

                await self.run(cog.lfg)

                # change the interaction user to a user not in the game
                self.interaction.user = outside_player
                lfg_action.safe_send_user.reset_mock()
                await select.callback(self.interaction)

                lfg_action.safe_send_user.assert_called_once_with(
                    outside_player,
                    "You are not one of the players in this game.",
                )
