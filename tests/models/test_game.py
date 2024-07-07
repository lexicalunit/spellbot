from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest
import pytest_asyncio
import pytz
from spellbot.database import DatabaseSession
from spellbot.enums import GameService
from spellbot.models import Game, GameStatus, Play

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from spellbot.settings import Settings

    from tests.fixtures import Factories


@pytest_asyncio.fixture(autouse=True)
async def use_consistent_date(freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("2021-03-01")


class TestModelGame:
    def test_game_to_dict(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel)

        assert game.to_dict() == {
            "id": game.id,
            "created_at": game.created_at,
            "updated_at": game.updated_at,
            "deleted_at": game.deleted_at,
            "started_at": game.started_at,
            "guild_xid": game.guild_xid,
            "channel_xid": game.channel_xid,
            "posts": game.posts,
            "voice_xid": game.voice_xid,
            "voice_invite_link": game.voice_invite_link,
            "seats": game.seats,
            "status": game.status,
            "format": game.format,
            "service": game.service,
            "spelltable_link": game.spelltable_link,
            "jump_links": game.jump_links,
            "spectate_link": game.spectate_link,
            "confirmed": game.confirmed,
            "requires_confirmation": game.requires_confirmation,
        }

    def test_game_show_links(self, factories: Factories) -> None:
        guild1 = factories.guild.create()
        guild2 = factories.guild.create(show_links=True)
        channel1 = factories.channel.create(guild=guild1)
        channel2 = factories.channel.create(guild=guild2)
        game1 = factories.game.create(guild=guild1, channel=channel1)
        game2 = factories.game.create(guild=guild2, channel=channel2)

        assert not game1.show_links()
        assert game1.show_links(True)
        assert game2.show_links()
        assert game2.show_links(True)

    @pytest.mark.parametrize(
        ("service", "description"),
        [
            pytest.param(
                GameService.SPELLTABLE,
                "_A SpellTable link will be created when all players have joined._",
                id="spelltable",
            ),
            pytest.param(
                GameService.COCKATRICE,
                "_Please use Cockatrice for this game._",
                id="cockatrice",
            ),
            pytest.param(
                GameService.NOT_ANY,
                "_Please contact the players in your game to organize this game._",
                id="not_any",
            ),
        ],
    )
    def test_game_embed_empty(
        self,
        settings: Settings,
        factories: Factories,
        service: GameService,
        description: str,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            updated_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            service=service.value,
        )

        expected_fields = [
            {"inline": True, "name": "Format", "value": "Commander"},
            {"inline": True, "name": "Updated at", "value": "<t:1635638400>"},
        ]
        if service != GameService.SPELLTABLE:
            expected_fields.append(
                {"inline": False, "name": "Service", "value": str(service)},
            )
        expected_fields.append(
            {"inline": False, "name": "Support SpellBot", "value": ANY},
        )
        assert game.to_embed().to_dict() == {
            "color": settings.EMPTY_EMBED_COLOR,
            "description": description,
            "fields": expected_fields,
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    def test_game_embed_pending(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)
        player = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.PENDING_EMBED_COLOR,
            "description": ("_A SpellTable link will be created when all players have joined._"),
            "fields": [
                {"inline": False, "name": "Players", "value": f"• <@{player.xid}> ({player.name})"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 3 more players to join...**",
            "type": "rich",
        }

    def test_game_embed_placeholders(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd="player 1: ${player_name_1}")
        channel = factories.channel.create(guild=guild, motd="game id: ${game_id}")
        game = factories.game.create(guild=guild, channel=channel)
        player = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.PENDING_EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._\n\n"
                f"player 1: {player.name}\n\n"
                f"game id: {game.id}"
            ),
            "fields": [
                {"inline": False, "name": "Players", "value": f"• <@{player.xid}> ({player.name})"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 3 more players to join...**",
            "type": "rich",
        }

    def test_game_embed_started_with_spelltable_link(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            spelltable_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": "Please check your Direct Messages for your game details.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "[Join your SpellTable game now!]"
                f"({game.spelltable_link}) (or [spectate this game]"
                f"({game.spectate_link}))\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_no_service(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            spelltable_link=None,
            guild=guild,
            channel=channel,
            service=GameService.NOT_ANY.value,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": "Please check your Direct Messages for your game details.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Service", "value": "Not any"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Contact the other players in your game to organize this match.\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Service", "value": "Not any"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_arena(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            spelltable_link=None,
            guild=guild,
            channel=channel,
            service=GameService.MTG_ARENA.value,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": "Please check your Direct Messages for your game details.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Service", "value": "MTG Arena"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Please use MTG Arena to play this game.\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Service", "value": "MTG Arena"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_with_guild_notice(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd=None, notice="this is a notice")
        channel = factories.channel.create(guild=guild, show_points=True, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            guild=guild,
            channel=channel,
        )
        factories.user.create(game=game)
        factories.user.create(game=game)
        assert game.to_embed().to_dict()["description"] == (
            "this is a notice\n\n"
            "Please check your Direct Messages for your game details.\n\n"
            "When your game is over use the drop down to report your points."
        )

    def test_game_embed_started_with_points(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, show_points=True, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            guild=guild,
            channel=channel,
        )
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)
        DatabaseSession.query(Play).filter(
            Play.game_id == game.id,
            Play.user_xid == player1.xid,
        ).update(
            {
                Play.points: 5,  # type: ignore
            },
        )
        DatabaseSession.query(Play).filter(
            Play.game_id == game.id,
            Play.user_xid == player2.xid,
        ).update(
            {
                Play.points: 1,  # type: ignore
            },
        )

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Please check your Direct Messages for your game details.\n"
                "\n"
                "When your game is over use the drop down to report your points."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n**ﾠ⮑ 5 points**\n"
                        f"• <@{player2.xid}> ({player2.name})\n**ﾠ⮑ 1 point**"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_without_spelltable_link(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": "Please check your Direct Messages for your game details.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Sorry but SpellBot was unable to create a SpellTable link for "
                "this game. Please go to [SpellTable]"
                "(https://spelltable.wizards.com/) to create one.\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_voice_channel(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            spelltable_link="https://spelltable/link",
            voice_xid=501,
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": "Please check your Direct Messages for your game details.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "[Join your SpellTable game now!]"
                f"({game.spelltable_link}) (or [spectate this game]"
                f"({game.spectate_link}))\n"
                "\n"
                f"Join your voice chat now: <#{game.voice_xid}>\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_voice_channel_and_link(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            spelltable_link="https://spelltable/link",
            voice_xid=501,
            voice_invite_link="https://voice/invite",
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": "Please check your Direct Messages for your game details.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "[Join your SpellTable game now!]"
                f"({game.spelltable_link}) (or [spectate this game]"
                f"({game.spectate_link}))\n"
                "\n"
                f"Join your voice chat now: <#{game.voice_xid}>\n"
                f"Or use this voice channel invite: {game.voice_invite_link}\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_motd(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd="this is a message of the day")
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            spelltable_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Please check your Direct Messages for your game details.\n"
                "\n"
                "this is a message of the day"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "[Join your SpellTable game now!]"
                f"({game.spelltable_link}) (or [spectate this game]"
                f"({game.spectate_link}))\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>.\n"
                "\n"
                "this is a message of the day"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n"
                        f"• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_win_loss(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(
            guild=guild,
            show_points=True,
            require_confirmation=True,
            motd=None,
        )
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=pytz.utc),
            guild=guild,
            channel=channel,
            requires_confirmation=True,
        )
        player1 = factories.user.create(game=game, xid=1)
        player2 = factories.user.create(game=game, xid=2)
        player3 = factories.user.create(game=game, xid=3)
        DatabaseSession.query(Play).filter(
            Play.game_id == game.id,
            Play.user_xid == player1.xid,
        ).update({Play.points: 3})  # type: ignore
        DatabaseSession.query(Play).filter(
            Play.game_id == game.id,
            Play.user_xid == player2.xid,
        ).update({Play.points: 1})  # type: ignore
        DatabaseSession.query(Play).filter(
            Play.game_id == game.id,
            Play.user_xid == player3.xid,
        ).update({Play.points: 0})  # type: ignore

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Please check your Direct Messages for your game details.\n"
                "\n"
                "When your game is over use the drop down to report your points."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n**ﾠ⮑ ❌ WIN**\n"
                        f"• <@{player2.xid}> ({player2.name})\n**ﾠ⮑ ❌ TIE**\n"
                        f"• <@{player3.xid}> ({player3.name})\n**ﾠ⮑ ❌ LOSS**"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
