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
    from pytest_mock import MockerFixture

    from spellbot.settings import Settings
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db

CONVOKE_PENDING_MSG = (
    "_A [Convoke](https://www.convoke.games/) link will be created when all players have joined._"
)


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

    def test_game_player_count(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel, seats=4)
        factories.user.create(game=game)
        factories.user.create(game=game)
        assert game.player_count == 2

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
                GameService.COCKATRICE,
                "_Please use Cockatrice for this game._",
                id="cockatrice",
            ),
            pytest.param(
                GameService.TABLE_STREAM,
                (
                    "_A [Table Stream](https://table-stream.com/) link will "
                    "be created when all players have joined._"
                ),
                id="table-stream",
            ),
            pytest.param(
                GameService.CONVOKE,
                (
                    "_A [Convoke](https://www.convoke.games/) link will "
                    "be created when all players have joined._"
                ),
                id="convoke",
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
        expected_fields.append(
            {"inline": False, "name": "Support SpellBot", "value": ANY},
        )
        assert game.to_embed().to_dict() == {
            "color": settings.EMPTY_EMBED_COLOR,
            "description": description,
            "fields": expected_fields,
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: {service}"},
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
            "description": CONVOKE_PENDING_MSG,
            "fields": [
                {"inline": False, "name": "Players", "value": f"• <@{player.xid}> ({player.name})"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 3 more players to join...**",
            "type": "rich",
            "flags": 0,
        }

    def test_game_embed_pending_with_emoji(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)
        factories.user.create(game=game)

        convoke_emoji = MagicMock(spec=discord.Emoji)
        convoke_emoji.name = "convoke"
        emojis = [convoke_emoji]

        embed = game.to_embed(emojis=emojis)
        assert f"{convoke_emoji}" in embed.description
        assert "[Convoke](https://www.convoke.games/)" in embed.description

    def test_game_embed_pending_with_emoji_no_match(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)
        factories.user.create(game=game)

        # Emoji with a name that doesn't match the service
        other_emoji = MagicMock(spec=discord.Emoji)
        other_emoji.name = "some_other_emoji"
        emojis = [other_emoji]

        embed = game.to_embed(emojis=emojis)
        # Should not contain the emoji since it doesn't match
        assert f"{other_emoji}" not in embed.description
        assert "[Convoke](https://www.convoke.games/)" in embed.description

    def test_game_embed_pending_with_blind(self, settings: Settings, factories: Factories) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel, blind=True)
        factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.PENDING_EMBED_COLOR,
            "description": CONVOKE_PENDING_MSG,
            "fields": [
                {"inline": False, "name": "Players", "value": "**1 player name is hidden**"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
            "description": CONVOKE_PENDING_MSG,
            "fields": [
                {"inline": False, "name": "Players", "value": "**2 player names are hidden**"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
            "description": CONVOKE_PENDING_MSG,
            "fields": [
                {"inline": False, "name": "Players", "value": f"• <@{player.xid}> ({player.name})"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
            "description": CONVOKE_PENDING_MSG,
            "fields": [
                {"inline": False, "name": "⚠️ Additional Rules:", "value": "test rules"},
                {"inline": False, "name": "Players", "value": f"• <@{player.xid}> ({player.name})"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
                f"{CONVOKE_PENDING_MSG}\n\nplayer 1: {player.name}\n\ngame id: {game.id}"
            ),
            "fields": [
                {"inline": False, "name": "Players", "value": f"• <@{player.xid}> ({player.name})"},
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
            game_link="https://convoke.games/link",
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your Convoke game now!]({game.game_link})"
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Not any"},
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
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Not any"},
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
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: MTG Arena"},
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
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: MTG Arena"},
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "Sorry but SpellBot was unable to create a link for "
                "this game. Please go to [Convoke]"
                "(https://www.convoke.games/) to create one."
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Table Stream"},
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
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Table Stream"},
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
            game_link="https://convoke.games/link",
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your Convoke game now!]({game.game_link})"
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
            game_link="https://convoke.games/link",
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "# [Join your Convoke game now!]"
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
            game_link="https://convoke.games/link",
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your Convoke game now!]({game.game_link})"
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
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
            game_link="https://convoke.games/link",
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }
        assert game.to_embed(guild=dg, dm=True, suggested_vc=suggested_vc).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your Convoke game now!]({game.game_link})"
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
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }

        # Setting already_picked to True will change the wording in the embed just a bit:
        suggested_vc.already_picked = 555
        assert game.to_embed(guild=dg, dm=True, suggested_vc=suggested_vc).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                f"# [Join your Convoke game now!]({game.game_link})"
                "\n\n"
                f"## Your pod is already using a voice channel, join them now: "
                f"<#{suggested_vc.already_picked}>!\n"
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
                    "value": f"<#{suggested_vc.already_picked}>",
                },
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
            "flags": 0,
        }

    def test_game_embed_for_rematch(self, factories: Factories, settings: Settings) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link="https://convoke.games/link",
            guild=guild,
            channel=channel,
        )
        post = factories.post.create(guild=guild, channel=channel, game=game)
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed(dm=True, rematch=True).to_dict() == {
            "color": settings.STARTED_EMBED_COLOR,
            "description": (
                "This is a rematch of a previous game. "
                "Please continue using the same game lobby and voice channel.\n\n"
                "You can also [jump to the original game post]"
                f"(https://discordapp.com/channels/{guild.xid}/{channel.xid}/{post.message_xid})"
                f" in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": "\n".join(
                        [
                            f"• <@{player1.xid}> ({player1.name})",
                            f"• <@{player2.xid}> ({player2.name})",
                        ],
                    ),
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "flags": 0,
            "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Rematch Game!**",
            "type": "rich",
        }

    def test_bracket_title_when_no_bracket(self, factories: Factories) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(bracket=GameBracket.NONE.value, guild=guild, channel=channel)
        assert game.bracket_title == ""

    def test_embed_players_with_supporter_emoji(self, factories: Factories) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)
        player = factories.user.create(game=game)

        supporter_emoji = MagicMock(spec=discord.Emoji)
        supporter_emoji.name = "spellbot_supporter"
        emojis = [supporter_emoji]
        supporters = {player.xid}

        result = game.embed_players(emojis=emojis, supporters=supporters)
        assert f"{supporter_emoji}" in result
        assert f"<@{player.xid}>" in result

    def test_embed_players_with_owner_emoji(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)
        player = factories.user.create(game=game, xid=12345)

        mocker.patch("spellbot.models.game.settings.OWNER_XID", "12345")

        owner_emoji = MagicMock(spec=discord.Emoji)
        owner_emoji.name = "spellbot_creator"
        emojis = [owner_emoji]

        result = game.embed_players(emojis=emojis, supporters=set())
        assert f"{owner_emoji}" in result
        assert f"<@{player.xid}>" in result

    def test_embed_with_suggested_vc_no_channels(
        self,
        settings: Settings,
        factories: Factories,
    ) -> None:
        """Test when suggested_vc is provided but has no channels (both None)."""
        guild = factories.guild.create(motd=None, suggest_voice_category="lfg voice")
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31, tzinfo=UTC),
            game_link="https://convoke.games/link",
            guild=guild,
            channel=channel,
        )
        factories.post.create(guild=guild, channel=channel, game=game)
        factories.user.create(game=game)
        factories.user.create(game=game)

        dg = MagicMock(spec=discord.Guild)
        dg.id = guild.xid
        suggested_vc = VoiceChannelSuggestion()  # Both already_picked and random_empty are None

        embed = game.to_embed(guild=dg, dm=True, suggested_vc=suggested_vc)
        # Should not include voice channel suggestion text
        assert "voice channel" not in embed.description.lower()
