from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock

import discord
import pytest

from spellbot.enums import GameBracket, GameService
from spellbot.models import Game, GameStatus
from spellbot.operations import VoiceChannelSuggestion

if TYPE_CHECKING:
    from spellbot.settings import Settings
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


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
            "bracket": game.bracket,
            "service": game.service,
            "game_link": game.game_link,
            "jump_links": game.jump_links,
            "password": game.password,
            "rules": game.rules,
            "blind": game.blind,
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
                GameService.TABLE_STREAM,
                "_A Table Stream link will be created when all players have joined._",
                id="table-stream",
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
            updated_at=datetime(2021, 10, 31, tzinfo=UTC),
            service=service.value,
            bracket=GameBracket.BRACKET_2.value,
        )

        expected_fields = [
            {"inline": True, "name": "Format", "value": "Commander"},
            {"inline": True, "name": "Bracket", "value": "✦ 2: Core"},
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
            "flags": 0,
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
            "flags": 0,
        }

    def test_game_embed_pending_with_blind(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel, blind=True)
        factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.PENDING_EMBED_COLOR,
            "description": ("_A SpellTable link will be created when all players have joined._"),
            "fields": [
                {"inline": False, "name": "Players", "value": "**1 player name is hidden**"},
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
            "flags": 0,
        }

    def test_game_embed_pending_with_blind_multiple_players(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel, blind=True)
        factories.user.create(game=game)
        factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.PENDING_EMBED_COLOR,
            "description": ("_A SpellTable link will be created when all players have joined._"),
            "fields": [
                {"inline": False, "name": "Players", "value": "**2 player names are hidden**"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 2 more players to join...**",
            "type": "rich",
            "flags": 0,
        }

    def test_game_embed_pending_with_blind_dm(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel, blind=True)
        player = factories.user.create(game=game)

        assert game.to_embed(dm=True).to_dict() == {
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
            "flags": 0,
        }

    def test_game_embed_with_rules(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel, rules="test rules")
        player = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.PENDING_EMBED_COLOR,
            "description": ("_A SpellTable link will be created when all players have joined._"),
            "fields": [
                {"inline": False, "name": "⚠️ Additional Rules:", "value": "test rules"},
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
            "flags": 0,
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
            "flags": 0,
        }

    def test_game_embed_started_with_game_link(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link="https://spelltable/link",
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
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your SpellTable game now!]({game.game_link})"
                "\n\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
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
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link=None,
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
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Contact the other players in your game to organize this match."
                "\n\n"
                "You can also [jump to the original game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
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
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link=None,
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
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Please use MTG Arena to play this game."
                "\n\n"
                "You can also [jump to the original game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }

    def test_game_with_guild_notice(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd=None, notice="this is a notice")
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            guild=guild,
            channel=channel,
        )
        factories.user.create(game=game)
        factories.user.create(game=game)
        assert game.to_embed().to_dict()["description"] == (
            "this is a notice\n\nPlease check your Direct Messages for your game details."
        )

    def test_game_embed_started_without_game_link(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
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
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Sorry but SpellBot was unable to create a link for "
                "this game. Please go to [SpellTable]"
                "(https://spelltable.wizards.com/) to create one."
                "\n\n"
                "You can also [jump to the original game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }

    def test_game_embed_started_without_tablestream_link(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            guild=guild,
            channel=channel,
            service=GameService.TABLE_STREAM.value,
            password="fake",  # noqa: S106
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
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Service", "value": "Table Stream"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Sorry but SpellBot was unable to create a link for "
                "this game. Please go to [Table Stream]"
                "(https://table-stream.com/) to create one."
                "\n\n"
                "Password: `fake`"
                "\n\n"
                "You can also [jump to the original game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Service", "value": "Table Stream"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
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
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link="https://spelltable/link",
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
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your SpellTable game now!]({game.game_link})"
                "\n\n"
                f"## Join your voice chat now: <#{game.voice_xid}>"
                "\n\n"
                "You can also [jump to the original game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
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
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link="https://spelltable/link",
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
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "# [Join your SpellTable game now!]"
                f"({game.game_link})\n\n"
                f"## Join your voice chat now: <#{game.voice_xid}>\n\n"
                f"Or use this voice channel invite: {game.voice_invite_link}\n\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }

    def test_game_embed_started_with_motd(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd="this is a message of the day")
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Please check your Direct Messages for your game details.\n\n"
                "this is a message of the day"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your SpellTable game now!]({game.game_link})"
                "\n\n"
                "You can also [jump to the original game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) "
                f"in <#{channel.xid}>.\n\n"
                "this is a message of the day"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
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
            "flags": 0,
        }

    def test_game_embed_started_with_suggested_voice_channel(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None, suggest_voice_category="lfg voice")
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        dg = MagicMock(spec=discord.Guild)
        dt = MagicMock(spec=discord.CategoryChannel, guild=dg, name="voice-channels")
        dc = MagicMock(spec=discord.VoiceChannel, guild=dg, category=dt, members=[])
        dc.id = 501
        dg.categories = [dt]
        dg.voice_channels = [dc]
        suggested_vc = VoiceChannelSuggestion(random_empty=dc.id)

        assert game.to_embed(guild=dg, suggested_vc=suggested_vc).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": "Please check your Direct Messages for your game details.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {
                    "inline": False,
                    "name": "🔊 Suggested Voice Channel",
                    "value": f"<#{dc.id}>",
                },
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(guild=dg, dm=True, suggested_vc=suggested_vc).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your SpellTable game now!]({game.game_link})"
                "\n\n"
                f"## Please consider using this available voice channel: <#{dc.id}>.\n"
                "**˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙ॱ⋅.˳.⋅ॱ˙**"
                "\n\n"
                "You can also [jump to the original game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.posts[0].message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": (
                        f"• <@{player1.xid}> ({player1.name})\n• <@{player2.xid}> ({player2.name})"
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {
                    "inline": False,
                    "name": "🔊 Suggested Voice Channel",
                    "value": f"<#{dc.id}>",
                },
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
