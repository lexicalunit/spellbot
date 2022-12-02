from __future__ import annotations

from datetime import datetime

from spellbot.models import GameStatus
from spellbot.settings import Settings

from tests.fixtures import Factories


class TestModelGame:
    def test_game_to_dict(self, factories: Factories):
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)

        assert game.to_dict() == {
            "id": game.id,
            "created_at": game.created_at,
            "updated_at": game.updated_at,
            "deleted_at": game.deleted_at,
            "started_at": game.started_at,
            "guild_xid": game.guild_xid,
            "channel_xid": game.channel_xid,
            "message_xid": game.message_xid,
            "voice_xid": game.voice_xid,
            "seats": game.seats,
            "status": game.status,
            "format": game.format,
            "spelltable_link": game.spelltable_link,
            "voice_invite_link": game.voice_invite_link,
            "jump_link": game.jump_link,
            "spectate_link": game.spectate_link,
        }

    def test_game_show_links(self, factories: Factories):
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

    def test_game_embed_empty(self, settings: Settings, factories: Factories):
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": ("_A SpellTable link will be created when all players have joined._"),
            "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    def test_game_embed_pending(self, settings: Settings, factories: Factories):
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)
        player = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": ("_A SpellTable link will be created when all players have joined._"),
            "fields": [
                {"inline": False, "name": "Players", "value": f"<@{player.xid}>"},
                {"inline": True, "name": "Format", "value": "Commander"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 3 more players to join...**",
            "type": "rich",
        }

    def test_game_embed_pending_with_power_level(
        self,
        settings: Settings,
        factories: Factories,
    ):
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(guild=guild, channel=channel)
        player = factories.user.create(game=game)
        config = factories.config.create(
            guild_xid=guild.xid,
            user_xid=player.xid,
            power_level=10,
        )

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": ("_A SpellTable link will be created when all players have joined._"),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player.xid}> (power level: {config.power_level})",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
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
    ):
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            spelltable_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": "Please check your Direct Messages for your SpellTable link.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "[Join your SpellTable game now!]"
                f"({game.spelltable_link}) (or [spectate this game]"
                f"({game.spectate_link}))\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_points(
        self,
        settings: Settings,
        factories: Factories,
    ):
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, show_points=True, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            guild=guild,
            channel=channel,
        )
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)
        factories.play.create(user_xid=player1.xid, game_id=game.id, points=5)
        factories.play.create(user_xid=player2.xid, game_id=game.id, points=1)

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "Please check your Direct Messages for your SpellTable link.\n"
                "\n"
                "When your game is over use the drop down to report your points."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}> (5 points), <@{player2.xid}> (1 point)",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
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
    ):
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            guild=guild,
            channel=channel,
        )
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": "Please check your Direct Messages for your SpellTable link.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "Sorry but SpellBot was unable to create a SpellTable link for "
                "this game. Please go to [SpellTable]"
                "(https://spelltable.wizards.com/) to create one.\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_voice_invite_link(
        self,
        settings: Settings,
        factories: Factories,
    ):
        guild = factories.guild.create(motd=None)
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            spelltable_link="https://spelltable/link",
            voice_invite_link="https://voice/invite/link",
            voice_xid=501,
            guild=guild,
            channel=channel,
        )
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": "Please check your Direct Messages for your SpellTable link.",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "[Join your SpellTable game now!]"
                f"({game.spelltable_link}) (or [spectate this game]"
                f"({game.spectate_link}))\n"
                "\n"
                f"[Join your voice chat now!]({game.voice_invite_link})"
                " (invite will expire in 240 minutes)\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.message_xid}) in <#{channel.xid}>."
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
                {
                    "inline": True,
                    "name": "Voice Channel",
                    "value": f"<#{game.voice_xid}>",
                },
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    def test_game_embed_started_with_motd(self, settings: Settings, factories: Factories):
        guild = factories.guild.create(motd="this is a message of the day")
        channel = factories.channel.create(guild=guild, motd=None)
        game = factories.game.create(
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            spelltable_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        player1 = factories.user.create(game=game)
        player2 = factories.user.create(game=game)

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "Please check your Direct Messages for your SpellTable link.\n"
                "\n"
                "this is a message of the day"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
        assert game.to_embed(dm=True).to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "[Join your SpellTable game now!]"
                f"({game.spelltable_link}) (or [spectate this game]"
                f"({game.spectate_link}))\n"
                "\n"
                "You can also [jump to the original game post]"
                "(https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{game.message_xid}) in <#{channel.xid}>.\n"
                "\n"
                "this is a message of the day"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{player1.xid}>, <@{player2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Started at", "value": "<t:1635638400>"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }
