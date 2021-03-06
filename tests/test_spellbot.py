import asyncio
import inspect
import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Coroutine, List
from unittest.mock import MagicMock, Mock

import pytest
import pytz

import spellbot
from spellbot import (
    get_db_env,
    get_db_url,
    get_host,
    get_log_level,
    get_port,
    get_port_env,
    get_redis_url,
    ping,
)
from spellbot.constants import (
    CREATE_ENDPOINT,
    EMOJI_DROP_GAME,
    EMOJI_JOIN_GAME,
    THUMB_URL,
    VOICE_CATEGORY_PREFIX,
)
from spellbot.data import ChannelSettings, Event, Game, Server, User, UserServerSettings

from .constants import CLIENT_TOKEN, TEST_DATA_ROOT
from .mocks import AsyncMock
from .mocks.discord import MockAttachment, MockChannel, MockMessage, MockPayload
from .mocks.users import (
    ADAM,
    ADMIN,
    ADMIN_ROLE,
    AMY,
    BOT,
    BUDDY,
    DUDE,
    FRIEND,
    GUY,
    JACOB,
    JR,
    PUNK,
    SERVER_MEMBERS,
    TOM,
)
from .test_meta import SNAPSHOTS_USED

##############################
# Test Suite Utilities
##############################


def someone():
    """Returns some non-admin user"""
    return random.choice(list(filter(lambda member: member != ADMIN, SERVER_MEMBERS)))


def an_admin():
    """Returns a random non-admin user with the SpellBot Admin role"""
    cond = lambda member: member != ADMIN and ADMIN_ROLE in member.roles
    return random.choice(list(filter(cond, SERVER_MEMBERS)))


def not_an_admin():
    """Returns a random non-admin user without the SpellBot Admin role"""
    cond = lambda member: member != ADMIN and ADMIN_ROLE not in member.roles
    return random.choice(list(filter(cond, SERVER_MEMBERS)))


def is_discord_file(obj):
    """Returns true if the given object is a discord File object."""
    return (obj.__class__.__name__) == "File"


def user_has_game(client, user):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user and db_user.game is not None
    session.close()
    return rvalue


def game_json_for(client, user):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.game.to_json() if db_user and db_user.game else None
    session.close()
    return rvalue


def user_json_for(client, user):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.to_json() if db_user else None
    session.close()
    return rvalue


def game_embed_for(client, user, ready, message=None, dm=False):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.game.to_embed(dm) if db_user and db_user.game else None
    session.close()
    if ready:
        assert db_user.game.status != "pending"
    if message:
        assert db_user.game.message == message
    return rvalue.to_dict() if rvalue else None


def all_games(client):
    session = client.data.Session()
    games = session.query(Game).all()
    rvalue = [json.loads(str(game)) for game in games]
    session.close()
    return rvalue


def all_events(client):
    session = client.data.Session()
    events = session.query(Event).all()
    rvalue = [json.loads(str(event)) for event in events]
    session.close()
    return rvalue


def all_servers(client):
    session = client.data.Session()
    servers = session.query(Server).all()
    rvalue = [json.loads(str(server)) for server in servers]
    session.close()
    return rvalue


##############################
# Test Fixtures
##############################


@pytest.fixture(autouse=True, scope="session")
def set_random_seed():
    random.seed(0)


@pytest.fixture
def snap(snapshot):
    snapshot.snapshot_dir = Path("tests") / "snapshots"
    snap.counter = 0

    def match(obj):
        test = inspect.stack()[1].function
        snapshot_file = f"{test}_{snap.counter}.txt"
        snapshot.assert_match(str(obj), snapshot_file)
        snap.counter += 1
        SNAPSHOTS_USED.add(snapshot_file)

    return match


##############################
# Test Suite
##############################


@pytest.mark.asyncio
class TestSpellBot:
    async def test_init_default(self, patch_discord, mock_background_tasks, tmp_path):
        (tmp_path / "spellbot.db").touch()
        connection_string = f"sqlite:///{tmp_path}/spellbot.db"
        db_url = spellbot.get_db_url("TEST_SPELLBOT_DB_URL", connection_string)

        bot = spellbot.SpellBot(db_url=db_url, mock_games=True)

        assert bot.loop

    async def test_init_with_loop(self, patch_discord, mock_background_tasks, tmp_path):
        (tmp_path / "spellbot.db").touch()
        connection_string = f"sqlite:///{tmp_path}/spellbot.db"
        db_url = spellbot.get_db_url("TEST_SPELLBOT_DB_URL", connection_string)
        loop = asyncio.get_event_loop()

        bot = spellbot.SpellBot(loop=loop, db_url=db_url, mock_games=True)

        assert bot.loop == loop

    async def test_init(self, client, channel_maker):
        assert client.token == CLIENT_TOKEN

    async def test_on_ready(self, client, channel_maker):
        await client.on_ready()

    async def test_paginate(self):
        def subject(text):
            return [page for page in spellbot.paginate(text)]

        assert subject("") == [""]
        assert subject("four") == ["four"]

        with open(Path(TEST_DATA_ROOT) / "ipsum_2011.txt") as f:
            text = f.read()
            pages = subject(text)
            assert len(pages) == 2
            assert all(len(page) <= 2000 for page in pages)
            assert pages == [text[0:1937], text[1937:]]

        with open(Path(TEST_DATA_ROOT) / "aaa_2001.txt") as f:
            text = f.read()
            pages = subject(text)
            assert len(pages) == 2
            assert all(len(page) <= 2000 for page in pages)
            assert pages == [text[0:2000], text[2000:]]

        with open(Path(TEST_DATA_ROOT) / "quotes.txt") as f:
            text = f.read()
            pages = subject(text)
            assert len(pages) == 2
            assert all(len(page) <= 2000 for page in pages)
            assert pages == [text[0:2000], f"> {text[2000:]}"]

    async def test_on_message_non_text(self, client, channel_maker):
        channel = MockChannel(6, "voice")
        await client.on_message(MockMessage(someone(), channel, "!spellbot help"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_is_admin(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        assert not spellbot.is_admin(channel, not_an_admin())
        assert spellbot.is_admin(channel, an_admin())

    async def test_parse_opts(self):
        assert spellbot.parse_opts(["a", "B", "c"]) == {
            "message": None,
            "params": ["a", "B", "c"],
            "size": 4,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "~B", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": 4,
            "tags": ["b"],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:5", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": 5,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:fancy", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": None,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:", "5", "c"]) == {
            "message": None,
            "params": ["a", "c"],
            "size": 5,
            "tags": [],
            "system": "spelltable",
        }

        assert spellbot.parse_opts(["a", "size:", "fancy", "c"]) == {
            "message": None,
            "params": ["a", "fancy", "c"],
            "size": None,
            "tags": [],
            "system": "spelltable",
        }

        # NOTE: Coverage for all functionality of parse_opts could be here, but it is
        #       actually covered in other places in these tests so, shrug...

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_no_request(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(someone(), channel, "!"))
        await client.on_message(MockMessage(someone(), channel, "!!"))
        await client.on_message(MockMessage(someone(), channel, "!!!"))
        await client.on_message(MockMessage(someone(), channel, "!   "))
        await client.on_message(MockMessage(someone(), channel, "!   !"))
        await client.on_message(MockMessage(someone(), channel, " !   !"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_ambiguous_request(
        self, client, channel_maker, channel_type, monkeypatch
    ):
        deferred_coroutines: List[Coroutine] = []

        def mock_call_later(interval, _, coroutine):
            deferred_coroutines.append(coroutine)

        monkeypatch.setattr(client.loop, "call_later", mock_call_later)

        author = someone()
        channel = channel_maker.make(channel_type)
        msg = MockMessage(author, channel, "!l")
        if hasattr(channel, "recipient"):
            assert channel.recipient == author
        await client.on_message(msg)
        post = channel.last_sent_message
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, that's not a command."
            " Did you mean to use one of these commands: !leave, !lfg?"
        )

        for coroutine in deferred_coroutines:
            await coroutine
        post.delete.assert_called_once()

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_invalid_request(
        self, client, channel_maker, channel_type, monkeypatch
    ):
        deferred_coroutines: List[Coroutine] = []

        def mock_call_later(interval, _, coroutine):
            deferred_coroutines.append(coroutine)

        monkeypatch.setattr(client.loop, "call_later", mock_call_later)

        dm = channel_maker.make(channel_type)
        author = someone()
        await client.on_message(MockMessage(author, dm, "!xeno"))
        post = dm.last_sent_message
        assert dm.last_sent_response == (
            f'Sorry {author.mention}, there is no "xeno" command.'
            ' Try "!spellbot help" for usage help.'
        )

        for coroutine in deferred_coroutines:
            await coroutine
        post.delete.assert_called_once()

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_from_a_bot(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(BOT, channel, "!spellbot help"))
        assert len(channel.all_sent_calls) == 0

    async def test_on_message_spellbot_help(self, client, channel_maker, snap):
        author = not_an_admin()
        channel = channel_maker.text()
        msg = MockMessage(author, channel, "!spellbot help")
        await client.on_message(msg)
        assert "✅" in msg.reactions
        for response in author.all_sent_responses:
            snap(response)
        assert len(author.all_sent_calls) == 3

    async def test_on_message_help(self, client, channel_maker):
        author = someone()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!help"))
        assert len(channel.all_sent_calls) == 0

    async def test_on_message_help_includes_confirmation_in_text_channel(
        self, client, channel_maker
    ):
        author = someone()
        channel = channel_maker.make("text")
        msg = MockMessage(author, channel, "!spellbot help")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_help_does_not_include_confirmation_in_dm(
        self, client, channel_maker
    ):
        author = someone()
        channel = channel_maker.make("dm")
        msg = MockMessage(author, channel, "!spellbot help")
        await client.on_message(msg)
        assert "✅" not in msg.reactions

    async def test_on_message_spellbot_dm(self, client, channel_maker):
        author = an_admin()
        dm = channel_maker.dm()
        await client.on_message(MockMessage(author, dm, "!spellbot channels foo"))
        assert author.last_sent_response == (
            f"Hello {author.mention}! That command only works in text channels."
        )

    async def test_on_message_spellbot_non_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert channel.last_sent_response == (
            f"{author.mention}, you do not have admin permissions to run that command."
        )

    async def test_on_message_spellbot_no_subcommand(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, "
            "please provide a subcommand when using this command."
        )

    async def test_on_message_spellbot_bad_subcommand(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot foo"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but the subcommand "foo" is not recognized.'
        )

    async def test_on_message_spellbot_channels_none(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot channels"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a list of channels."
            " Like #bot-commands, for example."
        )

    async def test_on_message_spellbot_channels_all_bad(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "foo" is not a valid channel. Try using # to'
            ' mention the channels you want or using "all" if you want me to operate'
            " in all channels."
        )

    async def test_on_message_spellbot_channels_one_bad_one_good(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        author = an_admin()
        cmd = f"!spellbot channels foo <#{channel.id}>"
        await client.on_message(MockMessage(author, channel, cmd))
        assert len(channel.all_sent_responses) == 2
        assert channel.all_sent_responses[0] == (
            f'Sorry {author.mention}, but "foo" is not a valid channel. Try using # to'
            ' mention the channels you want or using "all" if you want me to operate'
            " in all channels."
        )
        assert channel.all_sent_responses[1] == (
            f"Ok {author.mention}, I will now operate within: <#{channel.id}>"
        )

    async def test_on_message_spellbot_channels_with_bad_ref(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels <#{channel.id + 1}>")
        )
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "<#{channel.id + 1}>" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )
        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_spellbot_channels_with_invalid(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels #{channel.id}")
        )
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "#{channel.id}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )

        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_spellbot_channels_no_mention(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels #{channel.name}")
        )
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "#{channel.name}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )

        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_spellbot_channels(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        foo = channel_maker.text("foo")
        bar = channel_maker.text("bar")
        baz = channel_maker.text("baz")
        await client.on_message(
            MockMessage(admin, channel, f"!spellbot channels <#{channel.id}>")
        )
        assert channel.last_sent_response == (
            f"Ok {admin.mention}, I will now operate within: <#{channel.id}>"
        )
        cmd = f"!spellbot channels <#{foo.id}> <#{bar.id}> <#{baz.id}>"
        await client.on_message(MockMessage(admin, channel, cmd))
        resp = (
            f"Ok {admin.mention}, I will now operate within:"
            f" <#{foo.id}>, <#{bar.id}>, <#{baz.id}>"
        )
        assert channel.last_sent_response == resp
        await client.on_message(
            MockMessage(author, channel, "!spellbot help")
        )  # bad channel now
        assert len(author.all_sent_calls) == 0

        await client.on_message(MockMessage(admin, foo, "!spellbot channels all"))
        assert foo.last_sent_response == (
            f"Ok {admin.mention}, I will now operate within: all channels"
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_about(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(someone(), channel, "!about"))
        assert len(channel.all_sent_calls) == 1

        about = channel.last_sent_embed
        assert about["title"] == "SpellBot"
        assert about["url"] == "http://spellbot.io/"
        assert about["description"] == (
            "_The Discord bot for [SpellTable](https://www.spelltable.com/)._\n"
            "\n"
            "Use the command `!spellbot help` for usage details. "
            "Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            "[🔗 Add SpellBot to your Discord!](https://discordapp.com/api/oauth2"
            "/authorize?client_id=725510263251402832&permissions=93265&scope=bot)\n"
            "\n"
            "[👍 Give SpellBot a vote on top.gg!]"
            "(https://top.gg/bot/725510263251402832/vote)\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[becoming a patron!](https://www.patreon.com/lexicalunit)"
        )
        assert about["thumbnail"]["url"] == THUMB_URL

        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Author"] == "[@lexicalunit](https://github.com/lexicalunit)"

        version = spellbot.__version__
        assert fields["Version"] == (
            f"[{version}](https://pypi.org/project/spellbot/{version}/)"
        )

    async def test_on_message_spellbot_prefix_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a prefix string."
        )

    async def test_on_message_spellbot_prefix(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        assert channel.last_sent_response == (
            f"Ok {author.mention},"
            ' I will now use "$" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "$about"))
        assert channel.last_sent_embed["url"] == "http://spellbot.io/"
        await client.on_message(MockMessage(author, channel, "$spellbot prefix $"))
        assert channel.last_sent_response == (
            f"Ok {author.mention},"
            ' I will now use "$" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "$spellbot prefix !"))
        assert channel.last_sent_response == (
            f"Ok {author.mention},"
            ' I will now use "!" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "!spellbot prefix )"))
        assert channel.last_sent_response == (
            f"Ok {author.mention},"
            ' I will now use ")" as my command prefix on this server.'
        )

    async def test_on_message_spellbot_expire_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a number of minutes."
        )

    async def test_on_message_spellbot_expire_bad(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire world"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but game expiration time"
            " should be between 10 and 60 minutes."
        )

    async def test_on_message_spellbot_expire(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire 45"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, game expiration time on this"
            " server has been set to 45 minutes."
        )

    async def test_on_message_spellbot_config(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        await client.on_message(MockMessage(author, channel, "$spellbot expire 45"))
        await client.on_message(MockMessage(author, channel, "$spellbot smotd Hello!"))
        await client.on_message(MockMessage(author, channel, "$spellbot config"))

        about = channel.last_sent_embed
        assert about["title"] == "SpellBot Server Config"
        assert about["footer"]["text"] == f"Config for Guild ID: {channel.guild.id}"
        assert about["thumbnail"]["url"] == THUMB_URL
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields == {
            "Active channels": "All",
            "Auto verify channels": "All",
            "Command prefix": "$",
            "Inactivity expiration time": "45 minutes",
            "Links privacy": "Public",
            "MOTD privacy": "Both",
            "Power": "On",
            "Server MOTD": "Hello!",
            "Spectator links": "Off",
            "Tags": "On",
            "Voice channels": "Off",
            "Admin created voice category prefix": VOICE_CATEGORY_PREFIX,
        }

        foo = channel_maker.text("foo")
        bar = channel_maker.text("bar")
        channels_cmd = f"$spellbot channels <#{channel.id}> <#{foo.id}> <#{bar.id}>"
        await client.on_message(MockMessage(author, channel, channels_cmd))
        await client.on_message(MockMessage(author, channel, "$spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Active channels"] == f"<#{channel.id}>, <#{foo.id}>, <#{bar.id}>"

    async def test_on_message_game_with_too_many_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, TOM, BUDDY, DUDE, AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, you mentioned too many people."
            " I expected 4 players to be mentioned."
        )

    async def test_on_message_game_with_too_few_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, you mentioned too few people."
            " I expected 4 players to be mentioned."
        )

    async def test_on_message_game_with_too_many_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        tags = ["one", "two", "three", "four", "five", "six"]
        tags_str = " ".join([f"~{tag}" for tag in tags])
        cmd = f"!game {mentions_str} {tags_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but you can not use more than 5 tags."
        )

    async def test_on_message_game_with_size_bad(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str} size:100"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the game size must be between 2 and 4."
        )

    async def test_on_message_game_non_admin(self, client, channel_maker):
        channel = channel_maker.text()
        author = not_an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"{author.mention}, you do not have admin permissions to run that command."
        )

    async def test_on_message_game_message_too_long(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "foo bar baz" * 100
        cmd = f"!game {mentions_str} msg: {message}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the optional game message"
            " must be shorter than 255 characters."
        )

    async def test_on_message_game(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {FRIEND.mention}, {BUDDY.mention},"
            f" {GUY.mention}, {DUDE.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == []
        assert game_json_for(client, GUY)["message"] is None

    async def test_on_message_game_with_voice(self, client, channel_maker):
        channel = channel_maker.text()
        admin = an_admin()

        await client.on_message(MockMessage(admin, channel, "!spellbot voice on"))
        assert channel.last_sent_response == (
            f"Ok {admin.mention}, I've turned on automatic voice channel creation."
        )

        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Voice: <{game['voice_channel_invite']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {FRIEND.mention}, {BUDDY.mention},"
            f" {GUY.mention}, {DUDE.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == []
        assert game_json_for(client, GUY)["message"] is None

    async def test_on_message_game_with_message(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} msg: {message}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {FRIEND.mention}, {BUDDY.mention},"
            f" {GUY.mention}, {DUDE.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True, message=message)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == []
        assert game_json_for(client, GUY)["message"] == message

    async def test_on_message_game_with_message_and_tags(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} msg: {message} ~a ~b ~c"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {FRIEND.mention}, {BUDDY.mention},"
            f" {GUY.mention}, {DUDE.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True, message=message)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, GUY)["message"] == message

        mentions = [ADAM, AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} size: 2 msg: {message} ~a ~b ~c"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[1]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {AMY.mention}, {ADAM.mention}"
        )
        player_response = game_embed_for(client, ADAM, True, message=message)
        assert ADAM.last_sent_embed == player_response
        assert AMY.last_sent_embed == player_response

        assert game_json_for(client, ADAM)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, ADAM)["message"] == message

    async def test_on_message_game_with_tags_and_message(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} ~a ~b ~c msg:{message}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {FRIEND.mention}, {BUDDY.mention},"
            f" {GUY.mention}, {DUDE.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True, message=message)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, GUY)["message"] == message

    async def test_on_message_game_multiple_times(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {FRIEND.mention}, {BUDDY.mention},"
            f" {GUY.mention}, {DUDE.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        mentions = [AMY, JR, ADAM, FRIEND]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[1]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {AMY.mention}, {ADAM.mention},"
            f" {JR.mention}, {FRIEND.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert AMY.last_sent_embed == player_response
        assert JR.last_sent_embed == player_response
        assert ADAM.last_sent_embed == player_response

    async def test_ensure_server_exists(self, client):
        session = client.data.Session()
        server = client.ensure_server_exists(session, 5)
        session.commit()
        assert json.loads(str(server)) == {
            "channels": [],
            "guild_xid": 5,
            "prefix": "!",
            "show_spectate_link": False,
            "expire": 30,
            "teams": [],
        }

    async def test_on_message_event_no_data(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!event"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but you must include an attachment containing"
            " event data with this command."
        )

    async def test_on_message_event_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        message = MockMessage(author, channel, "!event", attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, please include the column names from the CSV file"
            " too identify the players' discord names."
        )

    async def test_on_message_event_invalid_player_count(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        message = MockMessage(author, channel, "!event a", attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the player count must be between 2 and 4."
        )

    async def test_on_message_event_missing_player(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        warning = (
            "**Warning:** Event file is missing a player name on row 1."
            f' SpellBot will **NOT** create a game for the players: "{AMY.name}", "".'
        )
        assert warning in channel.all_sent_responses
        assert channel.last_sent_response == (
            f"Hey {author.mention}, no games were created for this event."
            " Please address any warnings and try again."
        )

    async def test_on_message_event_not_utf(self, client, channel_maker, monkeypatch):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])

        mock_decode_data = Mock()
        mock_decode_data.side_effect = UnicodeDecodeError("utf-8", b"f1", 0, 1, "reason")
        monkeypatch.setattr(client, "decode_data", mock_decode_data)

        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, "
            "but that file isn't UTF-8 encoded and I can't read it."
        )

    async def test_on_message_event_no_header(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the attached CSV file is missing a header."
        )

    async def test_on_message_event_no_header_v2(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes("1,2,3\n4,5,6\n7,8,9", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the attached CSV file is missing a header."
        )

    async def test_on_message_event_not_csv(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        txt_file = MockAttachment("event.txt", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[txt_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the file is not a CSV file."
            ' Make sure the filename ends with ".csv" please.'
        )

    async def test_on_message_event_missing_discord_user(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{PUNK.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)

        warning = (
            '**Warning:** On row 1 the username "punk" is not on this server. '
            "SpellBot will **NOT** create a game for the players:"
            f' "{AMY.name}", "{PUNK.name}".'
        )
        assert warning in channel.all_sent_responses

    async def test_on_message_event_not_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"{author.mention}, you do not have admin permissions to run that command."
        )

    async def test_on_message_event_message_too_long(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "foo bar baz" * 100
        comment = f"!event player1 player2 msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the optional game message"
            " must be shorter than 255 characters."
        )

    async def test_on_message_event_with_too_many_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name}#1234,@{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        tags = ["one", "two", "three", "four", "five", "six"]
        tags_str = " ".join([f"~{tag}" for tag in tags])
        comment = f"!event player1 player2 {tags_str}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but you can not use more than 5 tags."
        )

    async def test_on_message_event_duplicate_user(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(
            "player1,player2\n"
            f"{AMY.name}#1234,@{JR.name}\n"
            f"{ADAM.name},{AMY.name}\n",
            "utf-8",
        )
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            f"**Error:** The user {AMY.name} appears in more than one pairing in this"
            " event file! I first noticed this duplicate on row 2 which contains the"
            f' players: "{ADAM.name}", "{AMY.name}". Please resolve this issue and try'
            " again."
        )

    async def test_on_message_event(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(
            "player1,player2\n"
            f"{AMY.name}#1234,@{JR.name}\n"
            f"{ADAM.name},{GUY.name}\n",
            "utf-8",
        )
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 2 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

    async def test_on_message_event_with_message(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

    async def test_on_message_event_with_message_and_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 msg: {opt} ~a ~b ~c"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )
        assert game_json_for(client, AMY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, AMY)["message"] == "an message override"
        assert game_json_for(client, AMY) == game_json_for(client, JR)

    async def test_on_message_event_with_tags_and_message(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 ~a ~b ~c msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )
        assert game_json_for(client, AMY)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, AMY)["message"] == "an message override"
        assert game_json_for(client, AMY) == game_json_for(client, JR)

        data = bytes(f"player1,player2\n{ADAM.name},{GUY.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 ~a ~b ~c msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[1]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )
        assert game_json_for(client, ADAM)["tags"] == ["a", "b", "c"]
        assert game_json_for(client, ADAM)["message"] == "an message override"
        assert game_json_for(client, ADAM) == game_json_for(client, GUY)

    async def test_on_message_begin_not_admin(self, client, channel_maker):
        channel = channel_maker.text()
        admin = an_admin()
        not_admin = not_an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(admin, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {admin.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(not_admin, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            f"{not_admin.mention}, you do not have admin permissions to run that command."
        )

    async def test_on_message_begin_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!begin"))
        assert channel.last_sent_response == (
            f"{author.mention}, please provide the event ID with that command."
        )

    async def test_on_message_begin_bad_param(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!begin sock"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but I can't find an event with that ID."
        )

    async def test_on_message_begin_event_not_found(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id + 1}"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but I can't find an event with that ID."
        )

    async def test_on_message_begin_event(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {AMY.name}, {JR.name}"
        )
        player_response = game_embed_for(client, AMY, True)
        assert AMY.last_sent_embed == player_response
        assert JR.last_sent_embed == player_response

    async def test_on_message_begin_event_with_message(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "this is an optional message"
        comment = f"!event player1 player2 msg: {opt}"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {AMY.name}, {JR.name}"
        )
        player_response = game_embed_for(client, AMY, True, message=opt)
        assert AMY.last_sent_embed == player_response
        assert JR.last_sent_embed == player_response

    async def test_on_message_begin_event_when_user_left(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        client.mock_disconnect_user(AMY)

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            "**Warning:** A user left the server since this event was created."
            " SpellBot did **NOT** start the game for the players:"
            f" {AMY.name}, {JR.name}."
        )

    async def test_on_message_begin_event_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but that event has already started"
            " and can not be started again."
        )

    async def test_on_message_lfg_dm(self, client, channel_maker):
        channel = channel_maker.dm()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert author.last_sent_response == (
            f"Hello {author.mention}! That command only works in text channels."
        )

    async def test_on_message_lfg_size_too_much(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:10"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_too_many_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        author = DUDE
        mentions = [FRIEND, GUY, BUDDY, AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but you've mentioned too many players"
            " for that size game."
        )

    async def test_on_message_lfg_multiple_mentions_valid(self, client, channel_maker):
        channel = channel_maker.text()

        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert game_embed_for(client, AMY, False) == game_embed_for(client, ADAM, False)
        assert game_embed_for(client, AMY, False) == game_embed_for(client, JR, False)

    async def test_on_message_lfg_multiple_mentions_complete(self, client, channel_maker):
        channel = channel_maker.text()

        mentions = [AMY, ADAM, JACOB]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert game_embed_for(client, AMY, True) == game_embed_for(client, ADAM, True)
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JR, True)
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)

    async def test_on_message_lfg_size_too_little(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:1"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_size_not_number(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:x"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_too_many_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg ~a ~b ~c ~d ~e ~f"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but you can not use more than 5 tags."
        )

    async def test_on_message_lfg_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        post = channel.last_sent_message
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert channel.last_sent_embed["description"] == (
            "[Jump to the game post](https://discordapp.com/channels/"
            f"{channel.guild.id}/{channel.id}/{post.id}) to see it!"
        )

    async def test_on_message_lfg(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, author, False)

    async def test_on_message_lfg_mtgo(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(JR, channel, "!lfg size:2 ~mtgo"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        game = game_json_for(client, ADAM)
        assert game["system"] == "mtgo"
        assert game["tags"] == []
        assert game_embed_for(client, ADAM, True) == {
            "color": 5914365,
            "description": "Please exchange MTGO contact information and head over there"
            " to play!",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"{ADAM.mention}, {JR.mention}",
                }
            ],
            "footer": {"text": f"SpellBot Reference #SB{game['id']}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    async def test_on_message_lfg_arena(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(JR, channel, "!lfg size:2 ~arena"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        game = game_json_for(client, ADAM)
        assert game["system"] == "arena"
        assert game["tags"] == []
        assert game_embed_for(client, ADAM, True) == {
            "color": 5914365,
            "description": "Please exchange Arena contact information and head over there"
            " to play!",
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"{ADAM.mention}, {JR.mention}",
                }
            ],
            "footer": {"text": f"SpellBot Reference #SB{game['id']}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    async def test_on_message_lfg_with_size(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:2"))
        assert "1 more player" in channel.last_sent_embed["title"]

    async def test_on_message_lfg_with_size_with_space(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size: 2"))
        assert "1 more player" in channel.last_sent_embed["title"]

    async def test_on_message_lfg_with_tags(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(ADAM, channel, "!lfg ~modern ~no-ban-list"))
        assert {
            "inline": True,
            "name": "Tags",
            "value": "modern, no-ban-list",
        } in channel.last_sent_embed["fields"]

        await client.on_message(MockMessage(JR, channel, "!lfg ~modern"))
        assert {
            "inline": True,
            "name": "Tags",
            "value": "modern",
        } in channel.last_sent_embed["fields"]

    async def test_on_message_leave(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        message = channel.last_sent_message
        assert channel.last_sent_embed == game_embed_for(client, author, False)
        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

        assert message.last_edited_embed["title"] == (
            "**Waiting for 4 more players to join...**"
        )

    async def test_on_message_leave_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_raw_reaction_add_irrelevant(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="👍",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) is None

    async def test_on_raw_reaction_add_bad_channel(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id + 1,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) is None

    async def test_on_raw_reaction_add_self(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADMIN.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADMIN,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADMIN, False) is None

    async def test_on_raw_reaction_add_bad_message(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id + 1,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) is None

    async def test_on_raw_reaction_add_plus_unauth_channel(self, client, channel_maker):
        channel_a = channel_maker.text("a")
        channel_b = channel_maker.text("b")

        await client.on_message(MockMessage(GUY, channel_a, "!lfg"))
        message = channel_a.last_sent_message

        lock_up = MockMessage(
            an_admin(), channel_a, f"!spellbot channels <#{channel_b.id}>"
        )
        await client.on_message(lock_up)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel_a.id,
            guild_id=channel_a.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) is None

    async def test_on_raw_reaction_add_plus_not_a_game(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == game_embed_for(client, GUY, False)

    async def test_on_raw_reaction_add_plus_twice(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        await client.on_raw_reaction_add(payload)
        assert len(ADAM.all_sent_calls) == 0

        assert message.last_edited_embed["title"] == (
            "**Waiting for 2 more players to join...**"
        )

    async def test_on_raw_reaction_add_plus_already(self, client, channel_maker):
        channel = channel_maker.text()

        # first game
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message1 = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message1.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        embed1 = channel.last_sent_embed
        await client.on_raw_reaction_add(payload)

        # second game
        await client.on_message(MockMessage(JR, channel, "!lfg ~modern"))
        message2 = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message2.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert len(all_games(client)) == 2
        assert game_embed_for(client, ADAM, True) != game_embed_for(client, GUY, False)

        assert message1.last_edited_embed == embed1  # unchanged
        assert message2.last_edited_embed["title"] == "**Your game is ready!**"

    async def test_on_raw_reaction_add_plus(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert "2 more players" in game_embed_for(client, ADAM, False)["title"]

        assert message.last_edited_embed["title"] == (
            "**Waiting for 2 more players to join...**"
        )

    async def test_on_raw_reaction_add_plus_complete(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        ready = game_embed_for(client, ADAM, True)
        assert GUY.last_sent_embed == ready
        assert ADAM.last_sent_embed == ready

        assert message.last_edited_embed["title"] == "**Your game is ready!**"

    async def test_on_raw_reaction_add_plus_after_disconnect(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        message = channel.last_sent_message

        client.mock_disconnect_user(GUY)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert "1 more player" in game_embed_for(client, ADAM, False)["title"]

        session = client.data.Session()
        game = session.query(Game).all()[0]
        session.close()
        assert message.last_edited_embed == {
            "color": 5914365,
            "description": (
                f"To **join this game**, react with {EMOJI_JOIN_GAME}\n"
                f"If you need to drop, react with {EMOJI_DROP_GAME}\n"
                "\n"
                "_A SpellTable link will be created when all players have joined._\n"
                "\n"
                "Looking for more players to join you? Just run `!lfg` "
                "again.\n"
            ),
            "fields": [{"inline": False, "name": "Players", "value": ADAM.mention}],
            "footer": {"text": f"SpellBot Reference #SB{game.id}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Waiting for 1 more player to join...**",
            "type": "rich",
        }

    async def test_on_raw_reaction_add_plus_then_minus(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message

        assert not user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_DROP_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert not user_has_game(client, ADAM)

        session = client.data.Session()
        game = session.query(Game).all()[0]
        session.close()
        assert message.last_edited_embed == {
            "color": 5914365,
            "description": (
                f"To **join this game**, react with {EMOJI_JOIN_GAME}\n"
                f"If you need to drop, react with {EMOJI_DROP_GAME}\n"
                "\n"
                "_A SpellTable link will be created when all players have joined._\n"
                "\n"
                "Looking for more players to join you? Just run `!lfg` "
                "again.\n"
            ),
            "fields": [{"inline": False, "name": "Players", "value": GUY.mention}],
            "footer": {"text": f"SpellBot Reference #SB{game.id}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Waiting for 3 more players to join...**",
            "type": "rich",
        }

    async def test_on_raw_reaction_minus_to_empty_game(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message

        payload = MockPayload(
            user_id=GUY.id,
            message_id=message.id,
            emoji=EMOJI_DROP_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=GUY,
        )
        await client.on_raw_reaction_add(payload)
        assert not user_has_game(client, GUY)

        session = client.data.Session()
        games = session.query(Game).all()
        rvalue = [game.to_embed().to_dict() for game in games]
        session.close()
        assert rvalue == [
            {
                "color": 5914365,
                "description": (
                    f"To **join this game**, react with {EMOJI_JOIN_GAME}\n"
                    f"If you need to drop, react with {EMOJI_DROP_GAME}\n"
                    "\n"
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    "Looking for more players to join you? Just run `!lfg` "
                    "again.\n"
                ),
                "footer": {"text": f"SpellBot Reference #SB{games[0].id}"},
                "thumbnail": {"url": THUMB_URL},
                "title": "**Waiting for 4 more players to join...**",
                "type": "rich",
            },
        ]
        assert message.last_edited_embed == {
            "color": 5914365,
            "description": (
                f"To **join this game**, react with {EMOJI_JOIN_GAME}\n"
                f"If you need to drop, react with {EMOJI_DROP_GAME}\n"
                "\n"
                "_A SpellTable link will be created when all players have joined._\n"
                "\n"
                "Looking for more players to join you? Just run `!lfg` "
                "again.\n"
            ),
            "footer": {"text": f"SpellBot Reference #SB{games[0].id}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    async def test_on_raw_reaction_add_minus_when_not_in_game(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, GUY)
        assert user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=AMY.id,
            message_id=message.id,
            emoji=EMOJI_DROP_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        assert not user_has_game(client, AMY)

    async def test_on_raw_reaction_add_minus_when_not_in_that_game(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        assert user_has_game(client, AMY)

        await client.on_message(MockMessage(GUY, channel, "!lfg ~chaos"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, GUY)
        assert user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=AMY.id,
            message_id=message.id,
            emoji=EMOJI_DROP_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, AMY)

    async def test_on_message_export_non_admin(self, client, channel_maker):
        channel = channel_maker.text()
        author = GUY
        await client.on_message(MockMessage(author, channel, "!export"))
        assert channel.last_sent_response == (
            f"{author.mention}, you do not have admin permissions to run that command."
        )

    async def test_on_message_export(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(JR, channel, "!lfg size:2 ~mtgo"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)

        # game_two is pending, so it shouldn't show up in the csv export
        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))

        admin_author = an_admin()
        data = bytes(f"player1,player2\n{GUY.name},{FRIEND.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(admin_author, channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]

        await client.on_message(MockMessage(admin_author, channel, f"!begin {event_id}"))
        await client.on_message(MockMessage(an_admin(), channel, "!export"))

        attachment = channel.all_sent_files[0]
        data = attachment.fp.read().decode()

        expected = ["id,size,status,system,channel,url,event_id,created_at,tags,message"]
        for game in all_games(client):
            if game["status"] == "pending":
                continue
            expected.append(
                ",".join(
                    [
                        str(game["id"]) if game["id"] else "",
                        str(game["size"]) if game["size"] else "",
                        str(game["status"]) if game["status"] else "",
                        str(game["system"]) if game["system"] else "",
                        f"#{channel.name}" if game["channel_xid"] else "",
                        str(game["url"]) if game["url"] else "",
                        str(game["event_id"]) if game["event_id"] else "",
                        str(game["created_at"]) if game["created_at"] else "",
                        str(game["tags"]) if game["tags"] else "",
                        str(game["message"]) if game["message"] else "",
                    ]
                )
            )
        for line in expected:
            assert line in data
        assert len(data.split("\n")) == 4

    async def test_on_message_lfg_with_functional_tag(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg ~modern"))
        assert "1 more player" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~oathbreaker"))
        assert "3 more players" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~edh size: 3"))
        assert "2 more players" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg size:3 ~cedh"))
        assert "2 more players" in channel.last_sent_embed["title"]

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~king"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the game size must be between 2 and 4."
        )

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~emperor"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the game size must be between 2 and 4."
        )

    async def test_session_contextmanager(self, client, caplog):
        exception_thrown = False
        try:
            async with client.session() as session:
                session.execute("delete from nothing;")
                assert False
        except Exception:
            exception_thrown = True

        assert exception_thrown
        assert "database error" in caplog.text

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_unhandled_exception(
        self, client, caplog, monkeypatch, channel_maker, channel_type
    ):
        channel = channel_maker.make(channel_type)

        @spellbot.command(allow_dm=True)
        def mock_cmd(prefix, params, message):
            raise RuntimeError("boom")

        monkeypatch.setattr(client, "spellbot", mock_cmd)
        with pytest.raises(RuntimeError):
            await client.on_message(MockMessage(someone(), channel, "!spellbot help"))
        assert "unhandled exception" in caplog.text

    async def test_on_message_spellbot_links_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot links"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a links privacy setting."
        )

    async def test_on_message_spellbot_links_invalid(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot links foo"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but foo is not a valid setting."
            ' I was expecting either "private" or "public".'
        )

    async def test_on_message_spellbot_links(self, client, channel_maker):
        channel = channel_maker.text()

        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot links private"))
        assert channel.last_sent_response == (
            f"Right on, {author.mention}. From now on SpellTable links will be private."
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        assert "http://" in game_embed_for(client, AMY, True, dm=True)["description"]
        assert "http://" not in game_embed_for(client, AMY, True, dm=False)["description"]

    async def test_on_message_spellbot_power_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot power"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_power_invalid(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot power bottom"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_power(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(JACOB, channel, "!power 1"))
        await client.on_message(MockMessage(AMY, channel, "!power 10"))

        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot power off"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've turned the power command off."
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)

        await client.on_message(MockMessage(AMY, channel, "!power 1"))

        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot power on"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've turned the power command on."
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        assert game_embed_for(client, AMY, False) != game_embed_for(client, JACOB, False)

    async def test_on_message_spellbot_voice_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot voice"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_voice_invalid(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot voice loud"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_voice(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot voice off"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've turned off automatic voice channel creation."
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)
        assert game_json_for(client, AMY)["voice_channel_xid"] is None

        await client.on_message(MockMessage(author, channel, "!spellbot voice on"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've turned on automatic voice channel creation."
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        amy_embed = game_embed_for(client, AMY, True)
        assert amy_embed == game_embed_for(client, JACOB, True)
        assert game_json_for(client, AMY)["voice_channel_xid"] == 1
        assert "Join your voice chat now" in amy_embed["description"]

    async def test_on_message_spellbot_voice_private(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot voice on"))
        await client.on_message(MockMessage(author, channel, "!spellbot links private"))

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        amy_embed = game_embed_for(client, AMY, True)
        assert amy_embed == game_embed_for(client, JACOB, True)
        assert game_json_for(client, AMY)["voice_channel_xid"] == 1
        assert "Join your voice chat now" not in amy_embed["description"]

    async def test_game_creation_when_voice_channel_create_error(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()
        author = an_admin()
        mock_op = AsyncMock(return_value=None)
        monkeypatch.setattr(spellbot, "safe_create_voice_channel", mock_op)
        await client.on_message(MockMessage(author, channel, "!spellbot voice on"))

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))

        mock_op.assert_called()
        amy_embed = game_embed_for(client, AMY, True)
        assert amy_embed == game_embed_for(client, JACOB, True)
        assert game_json_for(client, AMY)["voice_channel_xid"] is None
        assert "Join your voice chat now" not in amy_embed["description"]

    async def test_game_creation_when_voice_invite_create_error(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()
        author = an_admin()
        mock_op = AsyncMock(return_value=None)
        monkeypatch.setattr(spellbot, "safe_create_invite", mock_op)
        await client.on_message(MockMessage(author, channel, "!spellbot voice on"))

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))

        mock_op.assert_called()
        amy_embed = game_embed_for(client, AMY, True)
        assert amy_embed == game_embed_for(client, JACOB, True)
        assert game_json_for(client, AMY)["voice_channel_xid"] == 1
        assert "Join your voice chat now" not in amy_embed["description"]

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_no_params(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_bad_param(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power bottom"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_no_space(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        msg = MockMessage(author, channel, "!power5")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_neg_param(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power -5"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_unlimited(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power unlimited"))
        assert channel.last_sent_response == (
            f"⚡ Sorry {author.mention}, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_high_param(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power 9000"))
        assert channel.last_sent_response == (
            f"💥 Sorry {author.mention}, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_eleven(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power 11"))
        assert channel.last_sent_response == (
            f"🤘 Sorry {author.mention}, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power_42(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!power 42"))
        assert channel.last_sent_response == (
            f"🤖 Sorry {author.mention}, please provide a number between"
            ' 1 to 10 or "none" to unset.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_power(self, client, channel_maker, channel_type):
        author = someone()
        channel = channel_maker.make(channel_type)
        msg = MockMessage(author, channel, "!power 5")
        await client.on_message(msg)
        assert "✅" in msg.reactions
        assert user_json_for(client, author)["power"] == 5
        await client.on_message(MockMessage(author, channel, "!power off"))
        assert "✅" in msg.reactions
        assert user_json_for(client, author)["power"] is None

    async def test_on_message_lfg_with_power_similar(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 5"))
        await client.on_message(MockMessage(JR, channel, "!power 4"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) == game_embed_for(client, JR, False)

        games = all_games(client)
        assert len(games) == 1
        game = games[0]
        assert game_embed_for(client, AMY, False) == {
            "color": 5914365,
            "description": (
                f"To **join this game**, react with {EMOJI_JOIN_GAME}\n"
                f"If you need to drop, react with {EMOJI_DROP_GAME}\n"
                "\n"
                "_A SpellTable link will be created when all players have joined._\n"
                "\n"
                "Looking for more players to join you? Just run `!lfg` "
                "again.\n"
            ),
            "fields": [
                {"inline": True, "name": "Average Power Level", "value": "4.5"},
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"{AMY.mention} (Power: 5), {JR.mention} (Power: 4)",
                },
            ],
            "footer": {"text": f"SpellBot Reference #SB{game['id']}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Waiting for 2 more players to join...**",
            "type": "rich",
        }

    async def test_on_message_lfg_with_power_disjoint(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 5"))
        await client.on_message(MockMessage(JR, channel, "!power 10"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) != game_embed_for(client, JR, False)
        assert len(all_games(client)) == 2

    async def test_on_message_lfg_with_power_6_vs_7(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 6"))
        await client.on_message(MockMessage(JR, channel, "!power 7"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) != game_embed_for(client, JR, False)
        assert len(all_games(client)) == 2

    async def test_on_message_lfg_with_power_7_vs_6(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 7"))
        await client.on_message(MockMessage(JR, channel, "!power 6"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) != game_embed_for(client, JR, False)
        assert len(all_games(client)) == 2

    async def test_on_message_lfg_with_power_vs_none(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!power 5"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        assert game_embed_for(client, AMY, False) != game_embed_for(client, JR, False)
        assert len(all_games(client)) == 2

    async def test_on_message_report_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report"))
        assert channel.last_sent_response == (
            f"{author.mention}, please provide the SpellBot game reference ID"
            " or SpellTable ID followed by your report."
        )

    async def test_on_message_report_one_param(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report 1"))
        assert channel.last_sent_response == (
            f"{author.mention}, please provide the SpellBot game reference ID"
            " or SpellTable ID followed by your report."
        )

    async def test_on_message_report_no_game(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report 1 sup"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, I couldn't find a game with that ID."
        )

    async def test_on_message_report_bad_id(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!report 1=1 sup"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, I couldn't find a game with that ID."
        )

    async def test_on_message_report_too_long(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        msg = "foo " * 100
        await client.on_message(MockMessage(author, channel, f"!report 1 {msg}"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, that report was too long."
            " Please limit your report to less than 255 characters."
        )

    async def test_on_message_report_not_started(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        game = all_games(client)[0]
        game_id = game["id"]
        await client.on_message(MockMessage(author, channel, f"!report {game_id} foo"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but that game hasn't even started yet."
        )

    async def test_on_message_report_by_id(self, client, channel_maker, monkeypatch):
        # this test isn't interested in verifying the report is correct
        monkeypatch.setattr(
            client, "_verify_command_fest_report", AsyncMock(return_value=True)
        )

        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))

        game = all_games(client)[0]
        game_id = game["id"]
        await client.on_message(MockMessage(AMY, channel, f"!report {game_id} sup"))
        assert channel.last_sent_response == f"Thanks for the report, {AMY.mention}!"
        await client.on_message(MockMessage(ADAM, channel, f"!report sb{game_id} word"))
        assert channel.last_sent_response == f"Thanks for the report, {ADAM.mention}!"
        await client.on_message(MockMessage(GUY, channel, f"!report SB{game_id} what"))
        assert channel.last_sent_response == f"Thanks for the report, {GUY.mention}!"
        await client.on_message(MockMessage(GUY, channel, f"!report #SB{game_id} what"))
        assert channel.last_sent_response == f"Thanks for the report, {GUY.mention}!"

    async def test_on_message_report_by_url(self, client, channel_maker, monkeypatch):
        # this test isn't interested in verifying the report is correct
        monkeypatch.setattr(
            client, "_verify_command_fest_report", AsyncMock(return_value=True)
        )

        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))

        game = all_games(client)[0]
        game_url = game["url"]
        game_id = game_url[game_url.rfind("/") + 1 :]
        await client.on_message(MockMessage(AMY, channel, f"!report {game_id} sup"))
        assert channel.last_sent_response == f"Thanks for the report, {AMY.mention}!"
        await client.on_message(MockMessage(ADAM, channel, f"!report a{game_id}z sup"))
        assert channel.last_sent_response == (
            f"Sorry {ADAM.mention}, I couldn't find a game with that ID."
        )

    async def test_on_message_report_cfb_incomplete(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))

        game = all_games(client)[0]
        game_url = game["url"]
        game_id = game_url[game_url.rfind("/") + 1 :]

        cmd = f"!report {game_id} @{AMY.name} 10"
        await client.on_message(MockMessage(AMY, channel, cmd, mentions=[AMY]))

        cmd = f"!report {game_id} @{ADAM.name} 20"
        await client.on_message(MockMessage(ADAM, channel, cmd, mentions=[ADAM]))

        async with client.session() as session:
            amy_user = session.query(User).filter(User.xid == AMY.id).one_or_none()
            assert amy_user.points(channel.guild.id) == 10

            adam_user = session.query(User).filter(User.xid == ADAM.id).one_or_none()
            assert adam_user.points(channel.guild.id) == 20

    async def test_on_message_report_cfb_wrong_points(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))

        game = all_games(client)[0]
        game_url = game["url"]
        game_id = game_url[game_url.rfind("/") + 1 :]
        cmd = f"!report {game_id} @{AMY.name} foot @{ADAM.name} leg"
        await client.on_message(MockMessage(AMY, channel, cmd, mentions=[AMY, ADAM]))
        assert channel.last_sent_response == (
            f"Sorry {AMY.mention}, to report points please use: `!report GameID"
            " @player1 Points @player2 Points @player3 Points @player4 Points`."
        )

    async def test_on_message_report_cfb_wrong_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))

        game = all_games(client)[0]
        game_url = game["url"]
        game_id = game_url[game_url.rfind("/") + 1 :]
        cmd = f"!report {game_id} @{AMY.name} foot @{ADAM.name} leg"
        await client.on_message(MockMessage(AMY, channel, cmd))
        assert channel.last_sent_response == (
            f"Sorry {AMY.mention}, to report points please use: `!report GameID"
            " @player1 Points @player2 Points @player3 Points @player4 Points`."
        )

    async def test_on_message_report_cfb(self, client, channel_maker):
        channel = channel_maker.text()
        admin = an_admin()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(admin, channel, cmd, mentions=mentions))

        await client.on_message(MockMessage(admin, channel, "!spellbot teams dogs cats"))
        await client.on_message(MockMessage(AMY, channel, "!team dogs"))
        await client.on_message(MockMessage(AMY, channel, "!team dogs"))
        await client.on_message(MockMessage(ADAM, channel, "!team dogs"))
        await client.on_message(MockMessage(GUY, channel, "!team cats"))

        game = all_games(client)[-1]
        game_url = game["url"]
        game_id = game_url[game_url.rfind("/") + 1 :]
        cmd = f"!report {game_id} @{AMY.name} 10 @{ADAM.name} 20"
        await client.on_message(MockMessage(AMY, channel, cmd, mentions=[AMY, ADAM]))
        assert channel.last_sent_response == f"Thanks for the report, {AMY.mention}!"

        async with client.session() as session:
            amy_user = session.query(User).filter(User.xid == AMY.id).one_or_none()
            assert amy_user.points(channel.guild.id) == 10

            adam_user = session.query(User).filter(User.xid == ADAM.id).one_or_none()
            assert adam_user.points(channel.guild.id) == 20

            guy_user = session.query(User).filter(User.xid == GUY.id).one_or_none()
            assert guy_user.points(channel.guild.id) == 0

        mentions = [AMY, GUY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game ~modern {mentions_str}"
        await client.on_message(MockMessage(admin, channel, cmd, mentions=mentions))

        game = all_games(client)[-1]
        game_url = game["url"]
        game_id = game_url[game_url.rfind("/") + 1 :]
        cmd = f"!report {game_id} @{AMY.name} 5 @{GUY.name} 5"
        await client.on_message(MockMessage(AMY, channel, cmd, mentions=[AMY, GUY]))
        assert channel.last_sent_response == f"Thanks for the report, {AMY.mention}!"

        cmd = f"!report {game_id} @{AMY.name} 7 @{GUY.name} 5"
        await client.on_message(MockMessage(AMY, channel, cmd, mentions=[AMY, GUY]))
        assert channel.last_sent_response == f"Thanks for the report, {AMY.mention}!"

        async with client.session() as session:
            amy_user = session.query(User).filter(User.xid == AMY.id).one_or_none()
            assert amy_user.points(channel.guild.id) == 17

            adam_user = session.query(User).filter(User.xid == ADAM.id).one_or_none()
            assert adam_user.points(channel.guild.id) == 20

            guy_user = session.query(User).filter(User.xid == GUY.id).one_or_none()
            assert guy_user.points(channel.guild.id) == 5

        await client.on_message(MockMessage(AMY, channel, "!points"))
        assert channel.last_sent_response == f"You've got 17 points, {AMY.mention}."

        await client.on_message(MockMessage(ADAM, channel, "!points"))
        assert channel.last_sent_response == f"You've got 20 points, {ADAM.mention}."

        await client.on_message(MockMessage(GUY, channel, "!points"))
        assert channel.last_sent_response == f"You've got 5 points, {GUY.mention}."

        await client.on_message(MockMessage(admin, channel, "!points"))
        assert "Team **dogs** has 37 points!" in channel.all_sent_responses
        assert "Team **cats** has 5 points!" in channel.all_sent_responses

    async def test_on_message_spellbot_teams_not_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot teams one two"))
        assert channel.last_sent_response == (
            f"{author.mention}, you do not have admin permissions to run that command."
        )

    async def test_on_message_spellbot_teams_no_params(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot teams"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a list of team names"
            " or `none` to erase teams."
        )

    async def test_on_message_spellbot_teams_too_few(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot teams cats"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please give at least two team names"
            " or `none` to erase teams."
        )

    async def test_on_message_spellbot_teams_dupes(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        cmd = "!spellbot teams cats cats dogs dogs cats"
        msg = MockMessage(author, channel, cmd)
        await client.on_message(msg)
        assert "✅" in msg.reactions
        assert set(all_servers(client)[0]["teams"]) == {"dogs", "cats"}

    async def test_on_message_spellbot_teams(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()

        await client.on_message(MockMessage(author, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert "Teams" not in fields

        msg = MockMessage(author, channel, "!spellbot teams cats dogs")
        await client.on_message(msg)
        assert "✅" in msg.reactions
        assert set(all_servers(client)[0]["teams"]) == {"dogs", "cats"}

        msg = MockMessage(author, channel, "!spellbot teams ants cows")
        await client.on_message(msg)
        assert "✅" in msg.reactions
        assert set(all_servers(client)[0]["teams"]) == {"ants", "cows"}

        await client.on_message(MockMessage(author, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Teams"] == "ants, cows"

        msg = MockMessage(author, channel, "!spellbot teams none")
        await client.on_message(msg)
        assert "✅" in msg.reactions
        assert set(all_servers(client)[0]["teams"]) == set()

    async def test_on_message_team_none(self, client, channel_maker):
        author = someone()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!team cats"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but there aren't any teams on this server."
        )

    async def test_on_message_team_not_set(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        await client.on_message(MockMessage(author, channel, "!team"))
        assert channel.last_sent_response == (
            f"Hey {author.mention}, "
            "you are not currently a part of a team on this server."
        )

    async def test_on_message_team_yours(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        msg = MockMessage(author, channel, "!team cAtS")
        await client.on_message(msg)
        assert "✅" in msg.reactions

        await client.on_message(MockMessage(author, channel, "!team"))
        assert channel.last_sent_response == (
            f"Hey {author.mention}, you are on the cats team."
        )

    async def test_on_message_team_not_found(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        await client.on_message(MockMessage(author, channel, "!team frogs"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but the teams available on this server are:"
            " cats, dogs."
        )

    async def test_on_message_team_gone(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams a b c d e"))
        await client.on_message(MockMessage(author, channel, "!team e"))

        async with client.session() as session:
            session.execute("delete from teams where name = 'e';")
            session.commit()

        await client.on_message(MockMessage(author, channel, "!team"))
        resp = channel.last_sent_response

        if resp == (
            f"Sorry {author.mention}, but the teams on this server have changed"
            " and your team no longer exists. Please choose a new team."
        ):
            pass  # sqlite
        elif resp == (
            f"Hey {author.mention}, "
            "you are not currently a part of a team on this server."
        ):
            # databases where cascade works

            # Since this string won't get exercised,
            # we have to call it or else the meta test will fail.
            from .test_meta import S_SPY

            S_SPY("team_gone", reply="")
        else:
            assert False

    async def test_on_message_team(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot teams cats dogs"))
        msg = MockMessage(author, channel, "!team dogs")
        await client.on_message(msg)
        assert "✅" in msg.reactions
        msg = MockMessage(author, channel, "!team cats")
        await client.on_message(msg)
        assert "✅" in msg.reactions
        msg = MockMessage(author, channel, "!team dogs")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_spellbot_tags_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot tags"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_tags_invalid(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot tags bottom"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot tags off"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've turned the ability to use tags off."
        )

        await client.on_message(MockMessage(AMY, channel, "!lfg ~modern ~fun"))

        game = game_json_for(client, AMY)
        assert game["size"] == 2
        assert game["tags"] == []

    # There was an issue with SpellBot where, since commands are handled async,
    # multiple commands could be processed interleaved at the same time. This problem
    # was mitigated by the fact that the work that was being done by these commands is
    # written in such a way as to be idempotent. Still, this means that additional
    # unnecessary work was being done by the bot. And code had to be written in such a
    # way to ensure the idempotentcy constraint is not violated. This constraint was then
    # violated by the `setup_voice()` method which creates a new voice channel. When two
    # users both did a `!lfg` command at the same time, triggering a game to be created,
    # the voice channel was created twice for this game. The fix was to make sure that
    # the bot doesn't create the channel if it already exists, which it can check before
    # trying to create the channel. This is not an ideal solution and I can't actually
    # get the bot to fail in this way in testing. Below was my attempt to see this
    # issue occur in tests, but something about it is wrong and I'm not sure how to
    # properly recreate this issue in this test suite at this time.
    #
    # NOTE: For now this particular issue with game creation has been resolved by using
    #       an async lock per channel for the critical paths that can create games. This
    #       note and test has been left in the codebase to document this problem. The
    #       danger still exists that future code/refactoring could introduce concurrency
    #       issues like this again. We must be vigilant against them.
    @pytest.mark.skip(reason="this test doesn't properly test the simultaneity problem")
    async def test_simultaneous_signup(self, client, channel_maker, monkeypatch):
        from functools import partial

        async def mock_setup_voice(times, session, game):
            if game.voice_channel_xid:
                return

            times()
            await asyncio.sleep(1)
            game.voice_channel_xid = 1

        times = Mock()
        monkeypatch.setattr(client, "setup_voice", partial(mock_setup_voice, times))

        channel = channel_maker.text()
        await client.on_message(MockMessage(an_admin(), channel, "!spellbot voice on"))
        await client.on_message(MockMessage(AMY, channel, "!lfg size:3"))

        await asyncio.gather(
            client.on_message(MockMessage(ADAM, channel, "!lfg size:3")),
            client.on_message(MockMessage(JR, channel, "!lfg size:3")),
        )

        times.assert_called_once()
        assert game_embed_for(client, AMY, True) == game_embed_for(client, ADAM, True)
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JR, True)

    async def test_game_is_expired(self, client, channel_maker, freezer):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg"))

        async with client.session() as session:
            for game in session.query(Game).all():
                assert not game.is_expired()

        freezer.move_to(NOW + timedelta(days=3))

        async with client.session() as session:
            for game in session.query(Game).all():
                assert game.is_expired()

    async def test_game_to_embed_with_average_wait_time(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))

        session = client.data.Session()
        game = session.query(Game).one_or_none()

        assert {
            "inline": True,
            "name": "Average Queue Time",
            "value": "10 minutes",
        } in game.to_embed(wait=10).to_dict()["fields"]

        assert {
            "inline": True,
            "name": "Average Queue Time",
            "value": "10 minutes and 30 seconds",
        } in game.to_embed(wait=10.5).to_dict()["fields"]

        assert {
            "inline": True,
            "name": "Average Queue Time",
            "value": "1 hour and 1 minute",
        } in game.to_embed(wait=61).to_dict()["fields"]

    async def test_create_spelltable_url(self, client, requests_mock):
        client.mock_games = False  # re-enable use of SpellTable API for this test
        mock_url = "http://example.com/game/id"
        requests_mock.post(CREATE_ENDPOINT, json={"gameUrl": mock_url})
        assert client.create_spelltable_url() == mock_url

    async def test_create_spelltable_url_missing_key(self, client, requests_mock):
        client.mock_games = False  # re-enable use of SpellTable API for this test
        requests_mock.post(CREATE_ENDPOINT, json={"bogus": None})
        assert client.create_spelltable_url() is None

    async def test_create_spelltable_url_not_json(self, client, requests_mock):
        client.mock_games = False  # re-enable use of SpellTable API for this test
        requests_mock.post(CREATE_ENDPOINT, json="oops!")
        assert client.create_spelltable_url() is None

    async def test_on_message_spellbot_smotd(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()
        await client.on_message(
            MockMessage(admin, channel, "!spellbot smotd Hello to      you! Hi!")
        )
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. "
            "The server message of the day is now: Hello to you! Hi!"
        )

        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))

        assert "Hello to you! Hi!" in game_embed_for(client, GUY, True)["description"]

    async def test_on_message_spellbot_smotd_none(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()

        await client.on_message(MockMessage(admin, channel, "!spellbot smotd something"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. The server message of the day is now: something"
        )
        await client.on_message(MockMessage(admin, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Server MOTD"] == "something"

        await client.on_message(MockMessage(admin, channel, "!spellbot smotd"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. The server message of the day is now: "
        )
        await client.on_message(MockMessage(admin, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Server MOTD"] == "None"

    async def test_on_message_spellbot_smotd_too_long(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()
        motd = "foo" * 100
        await client.on_message(MockMessage(admin, channel, f"!spellbot smotd {motd}"))
        assert channel.last_sent_response == (
            f"Sorry {admin.mention}, but that message is too long."
        )

    async def test_on_message_spellbot_cmotd(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()
        await client.on_message(
            MockMessage(admin, channel, "!spellbot cmotd Hello to      you! Hi!")
        )
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. "
            "The message of the day for this channel is now: Hello to you! Hi!"
        )

        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))

        assert "Hello to you! Hi!" in game_embed_for(client, GUY, True)["description"]

    async def test_on_message_spellbot_cmotd_none(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()

        await client.on_message(MockMessage(admin, channel, "!spellbot cmotd something"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}."
            " The message of the day for this channel is now: something"
        )

        await client.on_message(MockMessage(admin, channel, "!spellbot cmotd"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. The message of the day for this channel is now: "
        )

    async def test_on_message_spellbot_cmotd_too_long(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()
        motd = "foo" * 100
        await client.on_message(MockMessage(admin, channel, f"!spellbot cmotd {motd}"))
        assert channel.last_sent_response == (
            f"Sorry {admin.mention}, but that message is too long."
        )

    async def test_on_message_spellbot_smotd_and_cmotd(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()
        await client.on_message(
            MockMessage(admin, channel, "!spellbot cmotd Channel MOTD")
        )
        await client.on_message(
            MockMessage(admin, channel, "!spellbot smotd Server MOTD")
        )
        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))
        assert "Channel MOTD" in game_embed_for(client, GUY, True)["description"]
        assert "Server MOTD" in game_embed_for(client, GUY, True)["description"]

    async def test_on_message_spellbot_motd_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot motd"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a MOTD privacy setting."
        )

    async def test_on_message_spellbot_motd_invalid(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot motd foo"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but foo is not a valid setting."
            ' I was expecting "private", "public", or "both".'
        )

    async def test_on_message_spellbot_motd_private(self, client, channel_maker):
        channel = channel_maker.text()

        admin = an_admin()
        await client.on_message(MockMessage(admin, channel, "!spellbot smotd foobar"))
        await client.on_message(MockMessage(admin, channel, "!spellbot motd private"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. "
            "This server's MOTD privacy setting is now: private."
        )

        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        assert "foobar" in game_embed_for(client, AMY, False, dm=True)["description"]
        assert "foobar" not in game_embed_for(client, AMY, False, dm=False)["description"]

    async def test_on_message_spellbot_motd_public(self, client, channel_maker):
        channel = channel_maker.text()

        admin = an_admin()
        await client.on_message(MockMessage(admin, channel, "!spellbot smotd foobar"))
        await client.on_message(MockMessage(admin, channel, "!spellbot motd public"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. "
            "This server's MOTD privacy setting is now: public."
        )

        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        assert "foobar" not in game_embed_for(client, AMY, False, dm=True)["description"]
        assert "foobar" in game_embed_for(client, AMY, False, dm=False)["description"]

    async def test_on_message_spellbot_size_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot size"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a number of players."
        )

    async def test_on_message_spellbot_size_bad(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot size 6"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, "
            "but default game size should be between 2 and 4 players."
        )

        await client.on_message(MockMessage(author, channel, "!spellbot size cute"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, "
            "but default game size should be between 2 and 4 players."
        )

    async def test_on_message_spellbot_size(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot size 3"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, "
            "the default game size for this channel has been set to 3 players."
        )

        await client.on_message(MockMessage(someone(), channel, "!lfg"))
        async with client.session() as session:
            game = session.query(Game).one_or_none()
            assert game.size == 3

    async def test_spelltable_link_creation_failure(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()

        mock_create_spelltable_url = Mock(return_value=None)
        monkeypatch.setattr(client, "create_spelltable_url", mock_create_spelltable_url)

        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))
        assert game_embed_for(client, AMY, True)["description"] == (
            "Sorry but SpellBot was unable to create a SpellTable link"
            " for this game. Please go to"
            " [spelltable.com](https://www.spelltable.com/) to create one.\n"
        )

    async def test_on_message_spellbot_stats_non_admin(self, client, channel_maker):
        channel = channel_maker.text()
        author = GUY
        await client.on_message(MockMessage(author, channel, "!spellbot stats"))
        assert channel.last_sent_response == (
            f"{author.mention}, you do not have admin permissions to run that command."
        )

    async def test_on_message_spellbot_stats(self, client, channel_maker, freezer):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel1 = channel_maker.text()
        await client.on_message(MockMessage(JR, channel1, "!lfg size:2"))
        await client.on_message(MockMessage(ADAM, channel1, "!lfg size:2"))

        channel2 = channel_maker.text()
        await client.on_message(MockMessage(JR, channel2, "!lfg size:2"))
        await client.on_message(MockMessage(ADAM, channel2, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel2, "!lfg size:2"))
        await client.on_message(MockMessage(ADAM, channel2, "!lfg size:2"))

        channel3 = channel_maker.text()
        await client.on_message(MockMessage(JR, channel3, "!lfg size:2"))
        await client.on_message(MockMessage(ADAM, channel3, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel3, "!lfg size:2"))
        await client.on_message(MockMessage(ADAM, channel3, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel3, "!lfg size:2"))
        await client.on_message(MockMessage(ADAM, channel3, "!lfg size:2"))

        await client.on_message(MockMessage(an_admin(), channel1, "!spellbot stats"))

        attachment = channel1.all_sent_files[0]
        data = attachment.fp.read().decode()

        assert data == (
            "date,channel,games\n"
            "1982-04-24,<#6500>,1\n"
            "1982-04-24,<#6501>,2\n"
            "1982-04-24,<#6502>,3\n"
        )

    async def test_get_db_env(self):
        assert get_db_env("fallback") == "fallback"

        os.environ["SPELLBOT_DB_ENV"] = "value"
        assert get_db_env("fallback") == "value"

    async def test_get_db_url(self):
        assert get_db_url("MOCK_DB_ENV", "fallback") == "fallback"

        os.environ["MOCK_DB_ENV"] = "value"
        assert get_db_url("MOCK_DB_ENV", "fallback") == "value"

    async def test_get_port_env(self):
        assert get_port_env("fallback") == "fallback"

        os.environ["SPELLBOT_PORT_ENV"] = "value"
        assert get_port_env("fallback") == "value"

    async def test_get_port(self):
        assert get_port("MOCK_PORT_ENV", 42) == 42

        os.environ["MOCK_PORT_ENV"] = "9000"
        assert get_port("MOCK_PORT_ENV", 42) == 9000

    async def test_get_host(self):
        assert get_host("fallback") == "fallback"

        os.environ["SPELLBOT_HOST"] = "value"
        assert get_host("fallback") == "value"

    async def test_get_log_level(self):
        assert get_log_level("fallback") == "fallback"

        os.environ["SPELLBOT_LOG_LEVEL"] = "value"
        assert get_log_level("fallback") == "value"

    async def test_get_redis_url(self):
        assert get_redis_url() == None

        os.environ["REDISCLOUD_URL"] = "value"
        assert get_redis_url() == "value"

    async def test_ping(self):
        request = MagicMock()
        response = await ping(request)
        assert response.status == 200
        assert response.text == "ok"

    async def test_try_to_update_game_for_unknown_channel(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))
        mock_safe_fetch_channel = AsyncMock()
        monkeypatch.setattr(spellbot, "safe_fetch_channel", mock_safe_fetch_channel)
        async with client.session() as session:
            game = session.query(Game).all()[0]
            game.channel_xid = None
            session.commit()

            await client.try_to_update_game(game)

        mock_safe_fetch_channel.assert_not_called()

    async def test_try_to_update_game_for_unknown_message(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))
        mock_safe_fetch_channel = AsyncMock()
        monkeypatch.setattr(spellbot, "safe_fetch_channel", mock_safe_fetch_channel)
        async with client.session() as session:
            game = session.query(Game).all()[0]
            game.message_xid = None
            session.commit()

            await client.try_to_update_game(game)

        mock_safe_fetch_channel.assert_not_called()

    async def test_try_to_update_game_when_channel_not_found(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))
        mock_safe_fetch_channel = AsyncMock(return_value=None)
        monkeypatch.setattr(spellbot, "safe_fetch_channel", mock_safe_fetch_channel)
        mock_safe_fetch_message = AsyncMock()
        monkeypatch.setattr(spellbot, "safe_fetch_message", mock_safe_fetch_message)
        async with client.session() as session:
            game = session.query(Game).all()[0]

            await client.try_to_update_game(game)

        mock_safe_fetch_message.assert_not_called()

    async def test_try_to_update_game_when_message_not_found(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))
        await client.on_message(MockMessage(JR, channel, "!lfg size:2"))
        async with client.session() as session:
            game = session.query(Game).all()[0]
            mock_to_embed = Mock()
            monkeypatch.setattr(game, "to_embed", mock_to_embed)
            mock_safe_fetch_channel = AsyncMock(return_value=True)
            monkeypatch.setattr(spellbot, "safe_fetch_channel", mock_safe_fetch_channel)
            mock_safe_fetch_message = AsyncMock(return_value=None)
            monkeypatch.setattr(spellbot, "safe_fetch_message", mock_safe_fetch_message)

            await client.try_to_update_game(game)

            mock_to_embed.assert_not_called()

    async def test_on_message_spellbot_toggle_verify(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()

        # At first things work just like normal.
        await client.on_message(MockMessage(someone(), channel, "!points"))
        assert channel.last_sent_response.startswith("You've got 0 points")

        # Then we turn on verification for this channel.
        await client.on_message(MockMessage(admin, channel, "!spellbot toggle-verify"))
        assert channel.last_sent_response == (
            f"Ok {admin.mention}, verification is now on for this channel."
        )
        async with client.session() as session:
            settings = session.query(ChannelSettings).all()[0]
            assert settings.require_verification

        # Even after verification is required, things still work normally
        # because ALL channels are considered auto-verification channels.
        await client.on_message(MockMessage(AMY, channel, "!points"))
        assert channel.last_sent_response.startswith("You've got 0 points")
        async with client.session() as session:
            user_settings = session.query(UserServerSettings).all()[0]
            assert user_settings.verified

        # Now let's set an auto-verification channel specifically.
        another_channel = channel_maker.text()
        cmd = f"!spellbot auto-verify <#{another_channel.id}>"
        await client.on_message(MockMessage(admin, another_channel, cmd))

        # Now try again with AMY since she's already been verified.
        await client.on_message(MockMessage(AMY, channel, "!points"))
        assert channel.last_sent_response.startswith("You've got 0 points")

        # But when we try with another users, they should be unverified.
        await client.on_message(MockMessage(ADAM, channel, "!team cat"))
        # Check that SpellBot didn't respond to the !team cat command in the channel.
        assert channel.last_sent_response.startswith("You've got 0 points")
        # Instead, it should have messaged ADAM to tell him that he's not verified.
        assert ADAM.last_sent_response == (
            f"Hello <@{ADAM.id}>. You are not verified to use SpellBot in "
            f"{channel.name}. Please speak to a server moderator or administrator to "
            "get verified."
        )

        await client.on_message(MockMessage(admin, channel, "!spellbot toggle-verify"))
        assert channel.last_sent_response == (
            f"Ok {admin.mention}, verification is now off for this channel."
        )
        async with client.session() as session:
            settings = session.query(ChannelSettings).all()[0]
            assert not settings.require_verification

        # Now we should respond to ADAM's message.
        await client.on_message(MockMessage(ADAM, channel, "!team cat"))
        assert channel.last_sent_response.startswith("Sorry")

    async def test_on_message_verify_non_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!verify"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_unverify_non_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!unverify"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_verify_none(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!verify"))
        assert len(channel.all_sent_calls) == 0

    async def test_on_message_verify_and_unverify(self, client, channel_maker):
        admin = an_admin()

        # First set up a random auto-verification channel to
        # prevent "All" channels from being auto-verification channels.
        another_channel = channel_maker.text()
        cmd = f"!spellbot auto-verify <#{another_channel.id}>"
        await client.on_message(MockMessage(admin, another_channel, cmd))

        channel = channel_maker.text()
        await client.on_message(MockMessage(admin, channel, "!spellbot toggle-verify"))

        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!verify {mentions_str}"
        await client.on_message(MockMessage(admin, channel, cmd, mentions=mentions))

        await client.on_message(MockMessage(AMY, channel, "!points"))
        assert channel.last_sent_response.startswith("You've got 0 points")

        cmd = f"!unverify {mentions_str}"
        await client.on_message(MockMessage(admin, channel, cmd, mentions=mentions))

        await client.on_message(MockMessage(AMY, channel, "!points"))
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>. You are not verified to use SpellBot in "
            f"{channel.name}. Please speak to a server moderator or administrator to "
            "get verified."
        )

    async def test_on_message_verify_and_unverify_reacts(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()

        # create a game post
        await client.on_message(MockMessage(JR, channel, "!lfg"))
        game_post = channel.last_sent_message

        # then turn of verification
        await client.on_message(MockMessage(admin, channel, "!spellbot toggle-verify"))

        # then have an unverified user try to react join
        payload = MockPayload(
            user_id=AMY.id,
            message_id=game_post.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        await client.on_raw_reaction_add(payload)

        # unverified user should get a notification about being unverified
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>. You are not verified to use SpellBot in "
            f"{channel.name}. Please speak to a server moderator or administrator to "
            "get verified."
        )

        # only JR should have a game
        assert user_has_game(client, JR)
        assert not user_has_game(client, AMY)

        # now verify AMY
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!verify {mentions_str}"
        await client.on_message(MockMessage(admin, channel, cmd, mentions=mentions))

        # and try again
        payload = MockPayload(
            user_id=AMY.id,
            message_id=game_post.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        await client.on_raw_reaction_add(payload)

        # both should have a game
        assert user_has_game(client, JR)
        assert user_has_game(client, AMY)

    async def test_on_react_to_non_game(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(JR, channel, "!lfg"))
        message = channel.last_sent_message

        async with client.session() as session:
            session.execute("delete from games;")
            session.commit()

        payload = MockPayload(
            user_id=AMY.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        await client.on_raw_reaction_add(payload)

        assert not user_has_game(client, JR)
        assert not user_has_game(client, AMY)

    async def test_on_message_spellbot_verify_message(self, client, channel_maker):
        admin = an_admin()

        # First set up a random auto-verification channel to
        # prevent "All" channels from being auto-verification channels.
        another_channel = channel_maker.text()
        cmd = f"!spellbot auto-verify <#{another_channel.id}>"
        await client.on_message(MockMessage(admin, another_channel, cmd))

        channel = channel_maker.text()
        await client.on_message(
            MockMessage(admin, channel, "!spellbot verify-message What the heck?")
        )
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. "
            "The verification message for this channel is now: What the heck?"
        )

        await client.on_message(MockMessage(admin, channel, "!spellbot toggle-verify"))
        await client.on_message(MockMessage(AMY, channel, "!points"))
        assert AMY.last_sent_response == "What the heck?"

    async def test_on_message_spellbot_verify_message_none(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()

        await client.on_message(
            MockMessage(admin, channel, "!spellbot verify-message something")
        )
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}."
            " The verification message for this channel is now: something"
        )

        await client.on_message(MockMessage(admin, channel, "!spellbot verify-message"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}."
            " The verification message for this channel is now: "
        )

    async def test_on_message_spellbot_verify_message_too_long(
        self, client, channel_maker
    ):
        admin = an_admin()
        channel = channel_maker.text()
        msg = "foo" * 100
        await client.on_message(
            MockMessage(admin, channel, f"!spellbot verify-message {msg}")
        )
        assert channel.last_sent_response == (
            f"Sorry {admin.mention}, but that message is too long."
        )

    async def test_on_message_spellbot_power_7_break(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(BUDDY, channel, "!power 5"))
        await client.on_message(MockMessage(BUDDY, channel, "!lfg"))

        await client.on_message(MockMessage(AMY, channel, "!power 6"))
        await client.on_message(MockMessage(JACOB, channel, "!power 6"))

        mentions = [JACOB]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(AMY, channel, cmd, mentions=mentions))

        await client.on_message(MockMessage(GUY, channel, "!power 7"))
        await client.on_message(MockMessage(GUY, channel, "!lfg"))

        assert game_embed_for(client, AMY, False) == game_embed_for(client, JACOB, False)
        assert game_embed_for(client, AMY, False) == game_embed_for(client, BUDDY, False)
        assert game_embed_for(client, AMY, False) != game_embed_for(client, GUY, False)

        async with client.session() as session:
            assert len(session.query(Game).all()) == 2

    async def test_on_message_spellbot_spectate_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot spectate"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_spectate_invalid(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot spectate it"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but please provide an "on" or "off" setting.'
        )

    async def test_on_message_spellbot_spectate(self, client, channel_maker):
        channel = channel_maker.text()

        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot spectate off"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've turned the show spectator link setting off."
        )
        await client.on_message(MockMessage(author, channel, "!spellbot spectate on"))
        assert channel.last_sent_response == (
            f"Ok {author.mention}, I've turned the show spectator link setting on."
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
        await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)
        assert "spectate on the game" in game_embed_for(client, AMY, True)["description"]

    async def test_on_message_spellbot_auto_verify_none(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot auto-verify"))
        assert channel.last_sent_response == (
            f"Sorry {author.mention}, but please provide a list of channels."
            " Like #bot-commands, for example."
        )

    async def test_on_message_spellbot_auto_verify_all_bad(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot auto-verify foo"))
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "foo" is not a valid channel. Try using # to'
            ' mention the channels you want or using "all" if you want me to auto verify'
            " in all channels."
        )

    async def test_on_message_spellbot_auto_verify_one_bad_one_good(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        author = an_admin()
        cmd = f"!spellbot auto-verify foo <#{channel.id}>"
        await client.on_message(MockMessage(author, channel, cmd))
        assert len(channel.all_sent_responses) == 2
        assert channel.all_sent_responses[0] == (
            f'Sorry {author.mention}, but "foo" is not a valid channel. Try using # to'
            ' mention the channels you want or using "all" if you want me to auto verify'
            " in all channels."
        )
        assert channel.all_sent_responses[1] == (
            f"Ok {author.mention}, I will now auto verify users within: <#{channel.id}>"
        )

    async def test_on_message_spellbot_auto_verify_with_bad_ref(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot auto-verify <#{channel.id + 1}>")
        )
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "<#{channel.id + 1}>" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to auto verify in all channels."
        )
        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_spellbot_auto_verify_with_invalid(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot auto-verify #{channel.id}")
        )
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "#{channel.id}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to auto verify in all channels."
        )

        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_spellbot_auto_verify_no_mention(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot auto-verify #{channel.name}")
        )
        assert channel.last_sent_response == (
            f'Sorry {author.mention}, but "#{channel.name}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to auto verify in all channels."
        )

        msg = MockMessage(author, channel, "!leave")
        await client.on_message(msg)
        assert "✅" in msg.reactions

    async def test_on_message_spellbot_auto_verify(self, client, channel_maker):
        admin = an_admin()
        author = not_an_admin()
        channel = channel_maker.text()
        foo = channel_maker.text("foo")
        bar = channel_maker.text("bar")
        baz = channel_maker.text("baz")
        await client.on_message(
            MockMessage(admin, channel, f"!spellbot auto-verify <#{channel.id}>")
        )
        assert channel.last_sent_response == (
            f"Ok {admin.mention}, I will now auto verify users within: <#{channel.id}>"
        )
        cmd = f"!spellbot auto-verify <#{foo.id}> <#{bar.id}> <#{baz.id}>"
        await client.on_message(MockMessage(admin, channel, cmd))
        resp = (
            f"Ok {admin.mention}, I will now auto verify users within:"
            f" <#{foo.id}>, <#{bar.id}>, <#{baz.id}>"
        )
        assert channel.last_sent_response == resp

        await client.on_message(MockMessage(admin, channel, "!spellbot toggle-verify"))

        await client.on_message(MockMessage(author, channel, "!points"))
        assert author.last_sent_response == (
            f"Hello <@{author.id}>. You are not verified to use SpellBot in "
            f"{channel.name}. Please speak to a server moderator or administrator to "
            "get verified."
        )

        await client.on_message(MockMessage(author, foo, "whatever"))

        await client.on_message(MockMessage(author, channel, "!points"))
        assert channel.last_sent_response == f"You've got 0 points, <@{author.id}>."

        await client.on_message(MockMessage(admin, foo, "!spellbot auto-verify all"))
        assert foo.last_sent_response == (
            f"Ok {admin.mention}, I will now auto verify users within: all channels"
        )

    async def test_on_message_block_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        msg = MockMessage(AMY, channel, "!block")
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Sorry <@{AMY.id}>, please say who you want to block with that command."
        )

    async def test_on_message_block_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd, mentions=mentions)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Sorry <@{AMY.id}>, please do not mention users, "
            "just copy their name without an @."
        )

    async def test_on_message_block(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have blocked the following users for you: @{JACOB.name}"
        )

    async def test_on_message_block_twice(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have blocked the following users for you: @{JACOB.name}"
        )

        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have blocked the following users for you: @{JACOB.name}"
        )

    async def test_on_message_block_self(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Sorry <@{AMY.id}>, please say who you want to block with that command."
        )

    async def test_on_message_block_multiple(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB, ADAM]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have blocked the following users for you:"
            f" @{JACOB.name}, @{ADAM.name}"
        )

    async def test_on_message_unblock_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        msg = MockMessage(AMY, channel, "!unblock")

        await client.on_message(msg)

        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Sorry <@{AMY.id}>, " "please say who you want to unblock with that command."
        )

    async def test_on_message_unblock_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!unblock {mentions_str}"
        msg = MockMessage(AMY, channel, cmd, mentions=mentions)

        await client.on_message(msg)

        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Sorry <@{AMY.id}>, please do not mention users, "
            "just copy their name without an @."
        )

    async def test_on_message_unblock(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!unblock {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)

        await client.on_message(msg)

        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have unblocked the following users for you: @{JACOB.name}"
        )

    async def test_on_message_unblock_multiple(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB, ADAM]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!unblock {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)

        await client.on_message(msg)

        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have unblocked the following users for you: "
            f"@{JACOB.name}, @{ADAM.name}"
        )

    async def test_on_message_block_lfg_blocked(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have blocked the following users for you: @{JACOB.name}"
        )

        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JACOB, channel, "!lfg"))

        assert game_embed_for(client, AMY, False) != game_embed_for(client, JACOB, False)

    async def test_on_message_block_lfg_blocked_by(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have blocked the following users for you: @{JACOB.name}"
        )

        await client.on_message(MockMessage(JACOB, channel, "!lfg"))
        await client.on_message(MockMessage(AMY, channel, "!lfg"))

        assert game_embed_for(client, AMY, False) != game_embed_for(client, JACOB, False)

    async def test_on_message_block_reaction(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [JACOB]
        mentions_str = " ".join([f"{user.name}" for user in mentions])
        cmd = f"!block {mentions_str}"
        msg = MockMessage(AMY, channel, cmd)
        await client.on_message(msg)
        assert msg.delete.call_count == 1
        assert AMY.last_sent_response == (
            f"Ok <@{AMY.id}>, I have blocked the following users for you: @{JACOB.name}"
        )

        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=JACOB.id,
            message_id=message.id,
            emoji=EMOJI_JOIN_GAME,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=JACOB,
        )
        await client.on_raw_reaction_add(payload)

        assert game_embed_for(client, AMY, False) != game_embed_for(client, JACOB, False)
        assert game_embed_for(client, JACOB, False) is None

    async def test_on_message_spellbot_voice_category(
        self, client, channel_maker, monkeypatch
    ):
        admin = an_admin()
        channel = channel_maker.text()
        await client.on_message(
            MockMessage(admin, channel, "!spellbot voice-category This   is a test")
        )
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. The voice channels that the game command creates"
            " will be put into a category named: This is a test"
        )

        await client.on_message(MockMessage(admin, channel, "!spellbot voice on"))
        assert channel.last_sent_response == (
            f"Ok {admin.mention}, I've turned on automatic voice channel creation."
        )

        # setup a check that the bot attempts to create the category channel
        mock_op = AsyncMock(return_value=None)
        monkeypatch.setattr(spellbot, "safe_create_category_channel", mock_op)

        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Voice: <{game['voice_channel_invite']}>\n"
            f"> Spectate: <{game['url']}?spectate>\n"
            f"> Players notified by DM: {FRIEND.mention}, {BUDDY.mention},"
            f" {GUY.mention}, {DUDE.mention}"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == []
        assert game_json_for(client, GUY)["message"] is None

        mock_op.assert_called_once_with(client, channel.guild.id, "This is a test")

    async def test_on_message_spellbot_voice_category_none(self, client, channel_maker):
        admin = an_admin()
        channel = channel_maker.text()

        await client.on_message(
            MockMessage(admin, channel, "!spellbot voice-category something")
        )
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. The voice channels that the game command"
            " creates will be put into a category named: something"
        )
        await client.on_message(MockMessage(admin, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Admin created voice category prefix"] == "something"

        await client.on_message(MockMessage(admin, channel, "!spellbot voice-category"))
        assert channel.last_sent_response == (
            f"Right on, {admin.mention}. The voice channels that the game command"
            f" creates will be put into a category named: {VOICE_CATEGORY_PREFIX}"
        )
        await client.on_message(MockMessage(admin, channel, "!spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Admin created voice category prefix"] == VOICE_CATEGORY_PREFIX

    async def test_on_message_spellbot_voice_category_too_long(
        self, client, channel_maker
    ):
        admin = an_admin()
        channel = channel_maker.text()
        cat = "f" * 50
        await client.on_message(
            MockMessage(admin, channel, f"!spellbot voice-category {cat}")
        )
        assert channel.last_sent_response == (
            f"Sorry {admin.mention}, but that category name is too long."
        )
