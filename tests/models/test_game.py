from datetime import datetime

from spellbot.database import DatabaseSession
from spellbot.models.channel import Channel
from spellbot.models.game import Game, GameStatus
from spellbot.models.guild import Guild
from spellbot.models.play import Play
from spellbot.models.user import User


class TestModelGame:
    def test_game_to_dict(self):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(message_xid=301, seats=4, guild=guild, channel=channel)
        DatabaseSession.add_all([guild, channel, game])
        DatabaseSession.commit()

        assert game.to_dict() == {
            "id": game.id,
            "created_at": game.created_at,
            "updated_at": game.updated_at,
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
        }

    def test_game_show_links(self):
        guild1 = Guild(xid=101, name="guild-name")
        guild2 = Guild(xid=102, name="guild-name", show_links=True)
        channel1 = Channel(xid=201, name="channel-name", guild=guild1)
        channel2 = Channel(xid=202, name="channel-name", guild=guild2)
        game1 = Game(message_xid=301, seats=4, guild=guild1, channel=channel1)
        game2 = Game(message_xid=302, seats=4, guild=guild2, channel=channel2)
        DatabaseSession.add_all([guild1, guild2, channel1, channel2, game1, game2])
        DatabaseSession.commit()

        assert not game1.show_links()
        assert game1.show_links(True)
        assert game2.show_links()
        assert game2.show_links(True)

    def test_game_embed_empty(self, settings):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(message_xid=301, seats=4, guild=guild, channel=channel)
        DatabaseSession.add_all([guild, channel, game])
        DatabaseSession.commit()

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._"
            ),
            "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {
                "url": settings.THUMB_URL,
            },
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    def test_game_embed_pending(self, settings):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(message_xid=301, seats=4, guild=guild, channel=channel)
        player = User(xid=401, name="player", game=game)
        DatabaseSession.add_all([guild, channel, game, player])
        DatabaseSession.commit()

        assert game.to_embed().to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._"
            ),
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

    def test_game_embed_started_with_spelltable_link(self, settings):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(
            message_xid=301,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            spelltable_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        player1 = User(xid=401, name="player1", game=game)
        player2 = User(xid=402, name="player2", game=game)
        DatabaseSession.add_all([guild, channel, game, player1, player2])
        DatabaseSession.commit()

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
                f"(<{game.spelltable_link}>) (or [spectate this game]"
                f"({game.spelltable_link}?spectate=true))\n"
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

    def test_game_embed_started_with_points(self, settings):
        guild = Guild(xid=101, name="guild-name", show_points=True)
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(
            message_xid=301,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            guild=guild,
            channel=channel,
        )
        DatabaseSession.add_all([guild, channel, game])
        DatabaseSession.commit()

        player1 = User(xid=401, name="player1", game=game)
        player2 = User(xid=402, name="player2", game=game)
        play1 = Play(user_xid=player1.xid, game_id=game.id, points=5)
        play2 = Play(user_xid=player2.xid, game_id=game.id, points=1)
        DatabaseSession.add_all([player1, player2, play1, play2])
        DatabaseSession.commit()

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

    def test_game_embed_started_without_spelltable_link(self, settings):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(
            message_xid=301,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            guild=guild,
            channel=channel,
        )
        player1 = User(xid=401, name="player1", game=game)
        player2 = User(xid=402, name="player2", game=game)
        DatabaseSession.add_all([guild, channel, game, player1, player2])
        DatabaseSession.commit()

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

    def test_game_embed_started_with_voice_invite_link(self, settings):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(
            message_xid=301,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            spelltable_link="https://spelltable/link",
            voice_invite_link="https://voice/invite/link",
            voice_xid=501,
            guild=guild,
            channel=channel,
        )
        player1 = User(xid=401, name="player1", game=game)
        player2 = User(xid=402, name="player2", game=game)
        DatabaseSession.add_all([guild, channel, game, player1, player2])
        DatabaseSession.commit()

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
                f"(<{game.spelltable_link}>) (or [spectate this game]"
                f"({game.spelltable_link}?spectate=true))\n"
                "\n"
                f"[Join your voice chat now!]({game.voice_invite_link})  "
                "(invite will expire in 240 minutes)\n"
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

    def test_game_embed_started_with_motd(self, settings):
        guild = Guild(xid=101, name="guild-name", motd="this is a message of the day")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game = Game(
            message_xid=301,
            seats=2,
            status=GameStatus.STARTED.value,
            started_at=datetime(2021, 10, 31),
            spelltable_link="https://spelltable/link",
            guild=guild,
            channel=channel,
        )
        player1 = User(xid=401, name="player1", game=game)
        player2 = User(xid=402, name="player2", game=game)
        DatabaseSession.add_all([guild, channel, game, player1, player2])
        DatabaseSession.commit()

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
                f"(<{game.spelltable_link}>) (or [spectate this game]"
                f"({game.spelltable_link}?spectate=true))\n"
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
