import inspect
import json
import random
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from os import chdir
from pathlib import Path
from subprocess import run
from unittest.mock import MagicMock, Mock
from warnings import warn

import pytest
import toml

import spellbot
from spellbot.assets import load_strings
from spellbot.data import Event, Game, User

##############################
# Discord.py Mocks
##############################


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class MockFile:
    def __init__(self, fp):
        self.fp = fp


class MockAttachment:
    def __init__(self, filename, data):
        self.filename = filename
        self.data = data

    async def read(self, *, use_cached=False):
        return self.data


class MockMember:
    def __init__(self, member_name, member_id, roles=[]):
        self.name = member_name
        self.id = member_id
        self.roles = roles
        self.avatar_url = "http://example.com/avatar.png"
        self.bot = False

        # sent is a spy for tracking calls to send(), it doesn't exist on the real object.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_sent_XXX` and `all_sent_XXX` to make our lives easier.
        self.sent = AsyncMock()

    async def send(self, content=None, *args, **kwargs):
        await self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )

    @property
    def last_sent_call(self):
        args, kwargs = self.sent.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_sent_response(self):
        return self.all_sent_responses[-1]

    @property
    def last_sent_embed(self):
        return self.last_sent_call["kwargs"]["embed"].to_dict()

    @property
    def all_sent_calls(self):
        sent_calls = []
        for sent_call in self.sent.call_args_list:
            args, kwargs = sent_call
            sent_calls.append({"args": args, "kwargs": kwargs})
        return sent_calls

    @property
    def all_sent_responses(self):
        return [sent_call["args"][0] for sent_call in self.all_sent_calls]

    @property
    def all_sent_embeds(self):
        return [
            sent_call["kwargs"]["embed"].to_dict()
            for sent_call in self.all_sent_calls
            if "embed" in sent_call["kwargs"]
        ]

    @property
    def all_sent_files(self):
        return [
            sent_call["kwargs"]["file"]
            for sent_call in self.all_sent_calls
            if "file" in sent_call["kwargs"]
        ]

    @property
    def all_sent_embeds_json(self):
        return json.dumps(self.all_sent_embeds, indent=4, sort_keys=True)

    def __repr__(self):
        return f"{self.name}#{self.id}"


class MockRole:
    def __init__(self, name):
        self.name = name


class MockGuild:
    def __init__(self, guild_id, name, members):
        self.id = guild_id
        self.name = name
        self.members = members


class MockChannel:
    def __init__(self, channel_id, channel_type):
        self.id = channel_id
        self.type = channel_type

        # sent is a spy for tracking calls to send(), it doesn't exist on the real object.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_sent_XXX` and `all_sent_XXX` to make our lives easier.
        self.sent = AsyncMock()

    async def send(self, content=None, *args, **kwargs):
        await self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )

    @property
    def last_sent_call(self):
        args, kwargs = self.sent.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_sent_response(self):
        return self.all_sent_responses[-1]

    @property
    def last_sent_embed(self):
        return self.last_sent_call["kwargs"]["embed"].to_dict()

    @property
    def all_sent_calls(self):
        sent_calls = []
        for sent_call in self.sent.call_args_list:
            args, kwargs = sent_call
            sent_calls.append({"args": args, "kwargs": kwargs})
        return sent_calls

    @property
    def all_sent_responses(self):
        return [sent_call["args"][0] for sent_call in self.all_sent_calls]

    @property
    def all_sent_embeds(self):
        return [
            sent_call["kwargs"]["embed"].to_dict()
            for sent_call in self.all_sent_calls
            if "embed" in sent_call["kwargs"]
        ]

    @property
    def all_sent_files(self):
        return [
            sent_call["kwargs"]["file"]
            for sent_call in self.all_sent_calls
            if "file" in sent_call["kwargs"]
        ]

    @property
    def all_sent_embeds_json(self):
        return json.dumps(self.all_sent_embeds, indent=4, sort_keys=True)

    @asynccontextmanager
    async def typing(self):
        yield


class MockTextChannel(MockChannel):
    def __init__(self, channel_id, channel_name, members):
        super().__init__(channel_id, "text")
        self.name = channel_name
        self.members = members
        self.guild = MockGuild(500, "Guild Name", members)


class MockDM(MockChannel):
    def __init__(self, channel_id):
        super().__init__(channel_id, "private")
        self.recipient = None  # can't be set until we know the author of a message


class MockMessage:
    def __init__(self, author, channel, content, mentions=None, attachments=None):
        self.author = author
        self.channel = channel
        self.content = content
        self.mentions = mentions or []
        self.attachments = attachments or []
        if isinstance(channel, MockDM):
            channel.recipient = author


class MockDiscordClient:
    def __init__(self, **kwargs):
        self.user = ADMIN

    def get_user(self, user_id):
        for user in ALL_USERS:
            if user.id == user_id:
                return user


##############################
# Test Suite Constants
##############################

CLIENT_TOKEN = "my-token"
CLIENT_AUTH = "my-auth"
CLIENT_USER = "ADMIN"
CLIENT_USER_ID = 82226367030108160

AUTHORIZED_CHANNEL = "good-channel"
UNAUTHORIZED_CHANNEL = "bad-channel"

TST_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = TST_ROOT / "fixtures"
REPO_ROOT = TST_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"

SRC_DIRS = [REPO_ROOT / "tests", SRC_ROOT / "spellbot", REPO_ROOT / "scripts"]

ADMIN_ROLE = MockRole("SpellBot Admin")
PLAYER_ROLE = MockRole("Player Player")

ADMIN = MockMember(CLIENT_USER, CLIENT_USER_ID, roles=[ADMIN_ROLE])
FRIEND = MockMember("friend", 82169952898900001, roles=[PLAYER_ROLE])
BUDDY = MockMember("buddy", 82942320688700002, roles=[ADMIN_ROLE, PLAYER_ROLE])
GUY = MockMember("guy", 82988021019800003)
DUDE = MockMember("dude", 82988761019800004, roles=[ADMIN_ROLE])

JR = MockMember("J.R.", 72988021019800005)
ADAM = MockMember("Adam", 62988021019800006)
AMY = MockMember("Amy", 52988021019800007)
JACOB = MockMember("Jacob", 42988021019800008)

PUNK = MockMember("punk", 119678027792600009)  # for a memeber that's not in our channel
BOT = MockMember("robot", 82169567890900010)
BOT.bot = True

CHANNEL_MEMBERS = [FRIEND, BUDDY, GUY, DUDE, ADMIN, JR, ADAM, AMY, JACOB]
ALL_USERS = []  # users that are on the server, setup in client fixture

S_SPY = Mock(wraps=spellbot.s)

##############################
# Test Suite Utilities
##############################


def someone():
    """Returns some non-admin user"""
    return random.choice(list(filter(lambda member: member != ADMIN, CHANNEL_MEMBERS)))


def an_admin():
    """Returns a random non-admin user with the SpellBot Admin role"""
    cond = lambda member: member != ADMIN and ADMIN_ROLE in member.roles
    return random.choice(list(filter(cond, CHANNEL_MEMBERS)))


def not_an_admin():
    """Returns a random non-admin user without the SpellBot Admin role"""
    cond = lambda member: member != ADMIN and ADMIN_ROLE not in member.roles
    return random.choice(list(filter(cond, CHANNEL_MEMBERS)))


def is_discord_file(obj):
    """Returns true if the given object is a discord File object."""
    return (obj.__class__.__name__) == "File"


def text_channel():
    return MockTextChannel(1, AUTHORIZED_CHANNEL, members=CHANNEL_MEMBERS)


def private_channel():
    return MockDM(1)


def game_response_for(client, user, ready, message=None):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.game.to_str() if db_user and db_user.game else None
    if rvalue:
        if ready:
            if message:
                assert rvalue.startswith(message)
            else:
                assert rvalue.startswith("**Your SpellTable game is ready!**")
        else:
            assert rvalue.startswith("**You have been entered in a play queue")
    session.close()
    return rvalue


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


##############################
# Test Fixtures
##############################


@pytest.fixture
def patch_discord():
    orig = spellbot.SpellBot.__bases__
    spellbot.SpellBot.__bases__ = (MockDiscordClient,)
    yield
    spellbot.SpellBot.__bases__ = orig


@pytest.fixture(autouse=True, scope="session")
def set_random_seed():
    random.seed(0)


@pytest.fixture
def client(monkeypatch, mocker, patch_discord, tmp_path):
    # Define which users are on this Discord server.
    global ALL_USERS
    ALL_USERS = CHANNEL_MEMBERS + [PUNK, BOT]

    # Keep track of strings used in the test suite.
    monkeypatch.setattr(spellbot, "s", S_SPY)

    # Don't actually begin background tasks during tests.
    monkeypatch.setattr(spellbot.SpellBot, "_begin_background_tasks", MagicMock())

    # Fallback to using sqlite for tests, but use the environment variable if it's set.
    (tmp_path / "spellbot.db").touch()
    connection_string = f"sqlite:///{tmp_path}/spellbot.db"
    db_url = spellbot.get_db_url("TEST_SPELLBOT_DB_URL", connection_string)
    bot = spellbot.SpellBot(
        token=CLIENT_TOKEN, auth=CLIENT_AUTH, db_url=db_url, mock_games=True
    )

    # Each test should have a clean slate. If we're using sqlite this is ensured
    # automatically as each test will create its own new spellbot.db file. With other
    # databases we'll have to manually clean out any existing data before each
    # test as the previous tests could have left data behind.
    for table in bot.data.metadata.tables.keys():
        bot.data.conn.execute(f"DELETE FROM {table};")

    # Make sure that all users have their send calls reset between client tests.
    for user in ALL_USERS:
        user.sent = AsyncMock()

    yield bot

    # For sqlite closing the connection when we're done isn't necessary, but for other
    # databases our test suite can quickly exhaust their connection pools.
    bot.data.conn.close()


SNAPSHOTS_USED = set()


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


@pytest.fixture
def spoof_session(client):
    """
    The client creates a session when processing a command,
    we have to create one ourselves when not in a command context.
    """
    client.session = client.data.Session()


##############################
# Test Suites
##############################


@pytest.mark.asyncio
class TestSpellBot:
    async def test_init(self, client):
        assert client.token == CLIENT_TOKEN

    async def test_on_ready(self, client):
        await client.on_ready()

    async def test_on_message_non_text(self, client):
        invalid_channel_type = "voice"
        channel = MockChannel(6, invalid_channel_type)
        await client.on_message(MockMessage(someone(), channel, "!help"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_from_admin(self, client, channel):
        await client.on_message(MockMessage(ADMIN, channel, "!help"))
        channel.sent.assert_not_called()

    async def test_on_message_in_unauthorized_channel(self, client):
        author = an_admin()
        channel = text_channel()
        admin_cmd = f"!spellbot channels {AUTHORIZED_CHANNEL}"
        await client.on_message(MockMessage(author, text_channel(), admin_cmd))

        bad_channel = MockTextChannel(5, UNAUTHORIZED_CHANNEL, members=CHANNEL_MEMBERS)
        await client.on_message(MockMessage(someone(), bad_channel, "!help"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_is_admin(self, client, channel):
        assert spellbot.is_admin(channel, not_an_admin()) == False
        assert spellbot.is_admin(channel, an_admin()) == True

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_no_request(self, client, channel):
        await client.on_message(MockMessage(someone(), channel, "!"))
        await client.on_message(MockMessage(someone(), channel, "!!"))
        await client.on_message(MockMessage(someone(), channel, "!!!"))
        await client.on_message(MockMessage(someone(), channel, "!   "))
        await client.on_message(MockMessage(someone(), channel, "!   !"))
        await client.on_message(MockMessage(someone(), channel, " !   !"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_ambiguous_request(self, client, channel):
        author = someone()
        msg = MockMessage(author, channel, "!s")
        if hasattr(channel, "recipient"):
            assert channel.recipient == author
        await client.on_message(msg)
        assert channel.last_sent_response == "Did you mean: !spellbot, !status?"

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_invalid_request(self, client, channel):
        await client.on_message(MockMessage(someone(), channel, "!xenomorph"))
        assert channel.last_sent_response == 'Sorry, there is no "xenomorph" command.'

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_from_a_bot(self, client, channel):
        author = BOT
        await client.on_message(MockMessage(author, channel, "!help"))
        assert len(channel.all_sent_calls) == 0

    @pytest.mark.parametrize(
        "channel,author", [(text_channel(), GUY), (private_channel(), FRIEND)]
    )
    async def test_on_message_help(self, client, channel, author, snap):
        await client.on_message(MockMessage(author, channel, "!help"))
        for response in author.all_sent_responses:
            snap(response)
        assert len(author.all_sent_calls) == 2

    async def test_on_message_play_dm(self, client):
        author = someone()
        await client.on_message(MockMessage(author, private_channel(), "!play"))
        assert author.last_sent_response == "That command only works in text channels."

    async def test_on_message_spellbot_dm(self, client):
        author = an_admin()
        channel = private_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert author.last_sent_response == "That command only works in text channels."

    async def test_on_message_spellbot_non_admin(self, client):
        author = not_an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert channel.last_sent_response == (
            "You do not have admin permissions for this bot."
        )

    async def test_on_message_spellbot_no_subcommand(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot"))
        assert channel.last_sent_response == (
            "Please provide a subcommand when using this command."
        )

    async def test_on_message_spellbot_bad_subcommand(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot foo"))
        assert channel.last_sent_response == 'The subcommand "foo" is not recognized.'

    async def test_on_message_spellbot_channels_none(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot channels"))
        assert channel.last_sent_response == "Please provide a list of channels."

    async def test_on_message_spellbot_channels(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels {AUTHORIZED_CHANNEL}")
        )
        assert channel.last_sent_response == (
            f"This bot is now authroized to respond only in: #{AUTHORIZED_CHANNEL}"
        )
        await client.on_message(
            MockMessage(author, channel, "!spellbot channels foo bar baz")
        )
        resp = "This bot is now authroized to respond only in: #foo, #bar, #baz"
        assert channel.last_sent_response == resp
        await client.on_message(MockMessage(author, channel, "!help"))  # bad channel now
        assert channel.last_sent_response == resp

    async def test_on_message_play_too_many_tags(self, client):
        channel = text_channel()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!play a b c d e f"))
        assert channel.last_sent_response == "Sorry, you can not use more than 5 tags."

    async def test_on_message_play(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)
        assert channel.last_sent_response == (
            "Right on, I'll send you a Direct Message with details."
        )

        await client.on_message(MockMessage(GUY, channel, "!play"))
        assert channel.last_sent_response == "You are already in the queue."

        await client.on_message(MockMessage(FRIEND, channel, "!play"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        await client.on_message(MockMessage(DUDE, channel, "!play"))
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)

        await client.on_message(MockMessage(GUY, channel, "!play"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

    async def test_on_message_play_then_leave_server(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(FRIEND, channel, "!play"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        # Simulate FRIEND leaving this Discord server
        global ALL_USERS
        ALL_USERS = [user for user in ALL_USERS if user != FRIEND]

        await client.on_message(MockMessage(BUDDY, channel, "!play"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        await client.on_message(MockMessage(DUDE, channel, "!play"))
        assert DUDE.last_sent_response == game_response_for(client, DUDE, False)

        await client.on_message(MockMessage(AMY, channel, "!play"))
        assert AMY.last_sent_response == game_response_for(client, AMY, True)

    async def test_on_message_play_cedh(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play cedh"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(GUY, channel, "!play cedh"))
        assert channel.last_sent_response == "You are already in the queue."

        await client.on_message(MockMessage(FRIEND, channel, "!play cedh"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play cedh"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        await client.on_message(MockMessage(AMY, channel, "!play"))
        assert AMY.last_sent_response == game_response_for(client, AMY, False)

        await client.on_message(MockMessage(DUDE, channel, "!play cedh"))
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)

        await client.on_message(MockMessage(GUY, channel, "!play cedh"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

    async def test_on_message_play_cedh_and_proxy(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play cedh proxy"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(GUY, channel, "!play cedh proxy"))
        assert channel.last_sent_response == "You are already in the queue."

        await client.on_message(MockMessage(FRIEND, channel, "!play cedh proxy"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play cedh proxy"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        await client.on_message(MockMessage(AMY, channel, "!play proxy"))
        assert AMY.last_sent_response == game_response_for(client, AMY, False)

        await client.on_message(MockMessage(DUDE, channel, "!play cedh proxy"))
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)

        await client.on_message(MockMessage(GUY, channel, "!play cedh proxy"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

    async def test_on_message_play_no_power_then_power(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play size:2"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(FRIEND, channel, "!play size:2 power:5"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_leave_not_queued(self, client, channel):
        author = someone()
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == "You were not in the queue."

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_leave(self, client, channel):
        author = someone()
        public_channel = text_channel()
        await client.on_message(MockMessage(author, public_channel, "!play"))
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == "You have been removed from the queue."

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_about(self, client, channel):
        await client.on_message(MockMessage(someone(), channel, "!about"))
        assert len(channel.all_sent_calls) == 1

        about = channel.last_sent_embed
        assert about["title"] == "SpellBot"
        assert about["url"] == "https://github.com/lexicalunit/spellbot"
        assert about["description"] == (
            "_A Discord bot for [SpellTable](https://www.spelltable.com/)._\n"
            "\n"
            "Use the command `!help` for usage details. Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[supporting me on Ko-fi!](https://ko-fi.com/Y8Y51VTHZ)"
        )
        assert about["footer"]["text"] == "MIT \u00a9 amy@lexicalunit et al"
        assert about["thumbnail"]["url"] == (
            "https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot.png"
        )

        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Package"] == "[PyPI](https://pypi.org/project/spellbot/)"
        assert fields["Author"] == "[@lexicalunit](https://github.com/lexicalunit)"

        version = spellbot.__version__
        assert fields["Version"] == (
            f"[{version}](https://pypi.org/project/spellbot/{version}/)"
        )

    async def test_on_message_play_too_many(self, client):
        author = someone()
        channel = text_channel()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        content = f"!play {mentions_str}"
        await client.on_message(MockMessage(author, channel, content, mentions=mentions))
        assert channel.last_sent_response == "Sorry, you mentioned too many people."

    async def test_on_message_play_mention_already(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play"))
        await client.on_message(
            MockMessage(DUDE, channel, f"!play @{GUY.name}", mentions=[GUY])
        )
        assert channel.last_sent_response == f"Sorry, {GUY} is already in the play queue."

    async def test_on_message_play_all(self, client):
        channel = text_channel()
        mentions = [GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        content = f"!play {mentions_str}"
        await client.on_message(MockMessage(FRIEND, channel, content, mentions=mentions))
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)

    async def test_on_message_play_then_leave_3(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(FRIEND, channel, "!play"))
        await client.on_message(MockMessage(BUDDY, channel, "!play"))
        await client.on_message(MockMessage(GUY, channel, "!play"))
        await client.on_message(MockMessage(FRIEND, channel, "!leave"))
        await client.on_message(MockMessage(BUDDY, channel, "!leave"))
        await client.on_message(MockMessage(GUY, channel, "!leave"))
        session = client.data.Session()
        assert len(session.query(Game).all()) == 0

    async def test_on_message_play_3_then_1(self, client):
        channel = text_channel()
        mentions = [GUY, BUDDY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        content = f"!play {mentions_str}"
        await client.on_message(MockMessage(FRIEND, channel, content, mentions=mentions))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)
        assert GUY.last_sent_response == game_response_for(client, GUY, False)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        await client.on_message(MockMessage(DUDE, channel, content))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)

    async def test_on_message_play_1_then_3(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(DUDE, channel, "!play"))
        assert DUDE.last_sent_response == game_response_for(client, DUDE, False)

        mentions = [GUY, BUDDY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        content = f"!play {mentions_str}"
        await client.on_message(MockMessage(FRIEND, channel, content, mentions=mentions))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)

    async def test_on_message_play_3_then_3_then_1_then_1(self, client, freezer):
        NOW = datetime.utcnow()
        freezer.move_to(NOW)
        channel = text_channel()
        mentions = [GUY, BUDDY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        content = f"!play {mentions_str}"
        await client.on_message(MockMessage(FRIEND, channel, content, mentions=mentions))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)
        assert GUY.last_sent_response == game_response_for(client, GUY, False)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        freezer.move_to(NOW + timedelta(minutes=5))
        mentions = [JR, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        content = f"!play {mentions_str}"
        await client.on_message(MockMessage(AMY, channel, content, mentions=mentions))
        assert AMY.last_sent_response == game_response_for(client, AMY, False)
        assert JR.last_sent_response == game_response_for(client, JR, False)
        assert ADAM.last_sent_response == game_response_for(client, ADAM, False)

        freezer.move_to(NOW + timedelta(minutes=10))
        await client.on_message(MockMessage(DUDE, channel, content))
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)

        freezer.move_to(NOW + timedelta(minutes=15))
        await client.on_message(MockMessage(JACOB, channel, content))
        assert AMY.last_sent_response == game_response_for(client, AMY, True)
        assert JR.last_sent_response == game_response_for(client, JR, True)
        assert ADAM.last_sent_response == game_response_for(client, ADAM, True)
        assert JACOB.last_sent_response == game_response_for(client, JACOB, True)

    async def test_on_message_play_size_1(self, client):
        author = someone()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!play size:1"))
        assert channel.last_sent_response == "Game size must be between 2 and 4."

    async def test_on_message_play_size_neg_1(self, client):
        author = someone()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!play size:-1"))
        assert channel.last_sent_response == "Game size must be between 2 and 4."

    async def test_on_message_play_size_5(self, client):
        author = someone()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!play size:5"))
        assert channel.last_sent_response == "Game size must be between 2 and 4."

    async def test_on_message_play_size_invalid(self, client):
        author = someone()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!play size:three"))
        assert channel.last_sent_response == "Game size must be between 2 and 4."

    async def test_on_message_play_size_2(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(FRIEND, channel, "!play size:2"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play size:2"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)

    async def test_on_message_play_size_2_multiple_games(self, client):
        channel = text_channel()

        # game 1
        await client.on_message(MockMessage(FRIEND, channel, "!play size:2"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)
        await client.on_message(MockMessage(BUDDY, channel, "!play size:2"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)

        session = client.data.Session()
        user = session.query(User).filter(User.xid == FRIEND.id).first()
        first_game_url = user.game.url

        # game 2
        await client.on_message(MockMessage(FRIEND, channel, "!play size:2"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)
        await client.on_message(MockMessage(BUDDY, channel, "!play size:2"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)

        session = client.data.Session()
        user = session.query(User).filter(User.xid == FRIEND.id).first()
        second_game_url = user.game.url

        assert first_game_url is not None
        assert second_game_url is not None
        assert first_game_url != second_game_url

    async def test_on_message_play_size_2_and_4(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play"))
        first_response = GUY.last_sent_response
        assert first_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(FRIEND, channel, "!play size:2"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play size:2"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)

        assert GUY.last_sent_response == first_response

    async def test_on_message_play_size_2_and_4_already(self, client):
        channel = text_channel()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!play"))
        assert author.last_sent_response == game_response_for(client, author, False)

        await client.on_message(MockMessage(author, channel, "!play size:2"))
        assert channel.last_sent_response == "You are already in the queue."

    async def test_on_message_play_then_expire(self, client, freezer):
        NOW = datetime.utcnow()
        freezer.move_to(NOW)
        channel = text_channel()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!play"))
        first_response = author.last_sent_response
        assert first_response == game_response_for(client, author, False)
        await client.cleanup_expired_games()
        assert author.last_sent_response == first_response
        freezer.move_to(NOW + timedelta(days=1))
        await client.cleanup_expired_games()
        assert author.last_sent_response == (
            "SpellBot has removed you from the queue due to server inactivity. "
            "Sorry, but unfortunately not enough players available at this time. "
            "Please try again when there are more players available."
        )

    async def test_on_message_play_then_expire_after_left_server(self, client, freezer):
        NOW = datetime.utcnow()
        freezer.move_to(NOW)
        channel = text_channel()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!play"))

        # Simulate author leaving this Discord server
        global ALL_USERS
        ALL_USERS = [user for user in ALL_USERS if user != author]

        freezer.move_to(NOW + timedelta(days=1))
        await client.cleanup_expired_games()
        assert len(author.all_sent_calls) == 1
        assert len(all_games(client)) == 0

    async def test_on_message_play_then_cleanup(self, client):
        channel = text_channel()
        assert len(all_games(client)) == 0

        await client.on_message(MockMessage(AMY, channel, "!play size:2"))
        await client.cleanup_started_games()
        assert len(all_games(client)) == 1

        await client.on_message(MockMessage(JR, channel, "!play size:2"))
        await client.cleanup_started_games()
        assert len(all_games(client)) == 0

    async def test_on_message_spellbot_prefix_none(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix"))
        assert channel.last_sent_response == "Please provide a prefix string."

    async def test_on_message_spellbot_prefix(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        assert channel.last_sent_response == (
            'This bot will now use "$" as its command prefix for this server.'
        )
        await client.on_message(MockMessage(author, channel, "$play"))
        assert author.last_sent_response == game_response_for(client, author, False)
        await client.on_message(MockMessage(author, channel, "$spellbot prefix $"))
        assert channel.last_sent_response == (
            'This bot will now use "$" as its command prefix for this server.'
        )
        await client.on_message(MockMessage(author, channel, "$spellbot prefix !"))
        assert channel.last_sent_response == (
            'This bot will now use "!" as its command prefix for this server.'
        )
        await client.on_message(MockMessage(author, channel, "!spellbot prefix )"))
        assert channel.last_sent_response == (
            'This bot will now use ")" as its command prefix for this server.'
        )

    async def test_on_message_status(self, client, freezer):
        channel = text_channel()
        await client.on_message(MockMessage(BUDDY, channel, "!status"))
        assert channel.last_sent_response == (
            "There is not enough information to calculate the current average"
            " queue wait time right now."
        )

        NOW = datetime.utcnow()
        freezer.move_to(NOW)
        await client.on_message(MockMessage(GUY, channel, "!play size:2"))

        freezer.move_to(NOW + timedelta(minutes=10))
        await client.on_message(MockMessage(BUDDY, channel, "!play size:2"))

        await client.on_message(MockMessage(BUDDY, channel, "!status"))
        assert channel.last_sent_response == (
            "The average queue wait time is currently 5 minutes."
        )

        await client.on_message(MockMessage(FRIEND, channel, "!play"))
        assert FRIEND.last_sent_response.split("\n")[0] == (
            "**You have been entered in a play queue for a 4 player game.**"
            " _The average wait time is 5 minutes._"
        )

    async def test_cleanup_expired_waits(self, client, freezer):
        channel = text_channel()
        NOW = datetime.utcnow()
        freezer.move_to(NOW)
        await client.on_message(MockMessage(GUY, channel, "!play size:2"))

        freezer.move_to(NOW + timedelta(seconds=10))
        await client.on_message(MockMessage(BUDDY, channel, "!play size:2"))

        await client.on_message(MockMessage(BUDDY, channel, "!status"))
        assert channel.last_sent_response == (
            "The average queue wait time is currently 5 seconds."
        )

        freezer.move_to(NOW + timedelta(minutes=35))
        await client.cleanup_expired_waits(30)

        await client.on_message(MockMessage(BUDDY, channel, "!status"))
        assert channel.last_sent_response == (
            "There is not enough information to calculate the current average "
            "queue wait time right now."
        )

    async def test_on_message_spellbot_scope_none(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot scope"))
        assert channel.last_sent_response == "Please provide a scope string."

    async def test_on_message_spellbot_scope_bad(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot scope world"))
        assert channel.last_sent_response == (
            'Sorry, scope should be either "server" or "channel".'
        )

    async def test_on_message_spellbot_scope(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot scope channel"))
        assert channel.last_sent_response == (
            "Matchmaking on this server is now set to: channel."
        )
        await client.on_message(MockMessage(author, channel, "!spellbot scope server"))
        assert channel.last_sent_response == (
            "Matchmaking on this server is now set to: server."
        )

    async def test_on_message_play_with_scope(self, client):
        channel_a = MockTextChannel(1, "channel_a", members=CHANNEL_MEMBERS)
        channel_b = MockTextChannel(2, "channel_b", members=CHANNEL_MEMBERS)
        admin = an_admin()
        await client.on_message(MockMessage(admin, channel_a, "!spellbot scope channel"))

        await client.on_message(MockMessage(GUY, channel_a, "!play size:2"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)
        await client.on_message(MockMessage(DUDE, channel_b, "!play size:2"))
        first_response = DUDE.last_sent_response
        assert first_response == game_response_for(client, DUDE, False)

        await client.on_message(MockMessage(BUDDY, channel_a, "!play size:2"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert DUDE.last_sent_response == first_response

    async def test_on_message_play_with_power_bad(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play power:42"))
        assert channel.last_sent_response == (
            "Sorry, power level should a number between 1 and 10."
        )

    async def test_on_message_play_with_power_level_high(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play power:5"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(FRIEND, channel, "!play power:7"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play power:9"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        await client.on_message(MockMessage(AMY, channel, "!play power:9"))
        assert AMY.last_sent_response == game_response_for(client, AMY, False)

        await client.on_message(MockMessage(DUDE, channel, "!play power:10"))
        assert DUDE.last_sent_response == game_response_for(client, DUDE, False)

        await client.on_message(MockMessage(JR, channel, "!play power:9"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert AMY.last_sent_response == game_response_for(client, AMY, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)
        assert JR.last_sent_response == game_response_for(client, JR, True)

    async def test_on_message_play_average_power(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play size:3 power:5"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(FRIEND, channel, "!play size:3 power:7"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play size:3 power:8"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, True)
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)

    async def test_on_message_play_with_power_level_low(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!play power:5"))
        assert GUY.last_sent_response == game_response_for(client, GUY, False)

        await client.on_message(MockMessage(FRIEND, channel, "!play power:7"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        await client.on_message(MockMessage(BUDDY, channel, "!play power:10"))
        assert BUDDY.last_sent_response == game_response_for(client, BUDDY, False)

        await client.on_message(MockMessage(AMY, channel, "!play power:9"))
        assert AMY.last_sent_response == game_response_for(client, AMY, False)

        await client.on_message(MockMessage(DUDE, channel, "!play power:4"))
        assert DUDE.last_sent_response == game_response_for(client, DUDE, False)

        await client.on_message(MockMessage(JR, channel, "!play power:6"))
        assert GUY.last_sent_response == game_response_for(client, GUY, True)
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, True)
        assert DUDE.last_sent_response == game_response_for(client, DUDE, True)
        assert JR.last_sent_response == game_response_for(client, JR, True)

    async def test_on_message_spellbot_expire_none(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot expire"))
        assert channel.last_sent_response == "Please provide a number of minutes."

    async def test_on_message_spellbot_expire_bad(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot expire world"))
        assert channel.last_sent_response == (
            "Sorry, game expiration time should be between 10 and 60 minutes."
        )

    async def test_on_message_spellbot_expire(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot expire 45"))
        assert channel.last_sent_response == "Game expiration time set to 45 minutes."

    async def test_on_message_play_then_custom_expire(self, client, freezer):
        NOW = datetime.utcnow()
        freezer.move_to(NOW)
        channel = text_channel()
        author = someone()
        await client.on_message(MockMessage(an_admin(), channel, "!spellbot expire 45"))
        await client.on_message(MockMessage(author, channel, "!play"))
        first_response = author.last_sent_response
        assert first_response == game_response_for(client, author, False)
        freezer.move_to(NOW + timedelta(minutes=30))
        await client.cleanup_expired_games()
        assert author.last_sent_response == first_response
        freezer.move_to(NOW + timedelta(minutes=50))
        await client.cleanup_expired_games()
        assert author.last_sent_response == (
            "SpellBot has removed you from the queue due to server inactivity. Sorry,"
            " but unfortunately not enough players available at this time. Please try"
            " again when there are more players available."
        )

    async def test_on_message_spellbot_config(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        await client.on_message(MockMessage(author, channel, "$spellbot expire 45"))
        await client.on_message(MockMessage(author, channel, "$spellbot scope channel"))
        await client.on_message(MockMessage(author, channel, "$spellbot config"))

        about = channel.last_sent_embed
        assert about["title"] == "SpellBot Server Config"
        assert about["footer"]["text"] == f"Config for Guild ID: {channel.guild.id}"
        assert about["thumbnail"]["url"] == (
            "https://raw.githubusercontent.com/lexicalunit/spellbot/master/spellbot.png"
        )
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Queue scope"] == "channel-specific"
        assert fields["Friendly queueing"] == "on"
        assert fields["Inactivity expiration time"] == "45 minutes"
        assert fields["Authorized channels"] == "all"

        channels_cmd = f"$spellbot channels {AUTHORIZED_CHANNEL} foo bar"
        await client.on_message(MockMessage(author, channel, channels_cmd))
        await client.on_message(MockMessage(author, channel, "$spellbot config"))
        about = channel.last_sent_embed
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Authorized channels"] == f"#{AUTHORIZED_CHANNEL}, #foo, #bar"

    async def test_on_message_game_with_power_bad(self, client):
        channel = text_channel()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str} power:42"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            "Sorry, power level should a number between 1 and 10."
        )

    async def test_on_message_game_with_too_many_mentions(self, client):
        channel = text_channel()
        mentions = [FRIEND, GUY, BUDDY, DUDE, AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            "Sorry, you mentioned too many people. I expected 4 players to be mentioned."
        )

    async def test_on_message_game_with_too_few_mentions(self, client):
        channel = text_channel()
        mentions = [FRIEND, GUY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            "Sorry, you mentioned too few people. I expected 4 players to be mentioned."
        )

    async def test_on_message_game_with_too_many_tags(self, client):
        channel = text_channel()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        tags = ["one", "two", "three", "four", "five", "six"]
        tags_str = " ".join(tags)
        cmd = f"!game {tags_str} {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        assert channel.last_sent_response == "Sorry, you can not use more than 5 tags."

    async def test_on_message_game_with_size_bad(self, client):
        channel = text_channel()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str} size:100"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        assert channel.last_sent_response == "Game size must be between 2 and 4."

    async def test_on_message_game_non_admin(self, client):
        channel = text_channel()
        author = not_an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            "You do not have admin permissions for this bot."
        )

    async def test_on_message_game_message_too_long(self, client):
        channel = text_channel()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "foo bar baz" * 100
        cmd = f"!game {mentions_str} -- {message}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            "Sorry, the optional game message must be shorter than 255 characters."
        )

    async def test_on_message_game(self, client):
        channel = text_channel()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> {game['url']}\n"
            f"> Players: <@{FRIEND.id}>, <@{BUDDY.id}>, <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_response_for(client, FRIEND, True)
        assert FRIEND.last_sent_response == player_response
        assert GUY.last_sent_response == player_response
        assert BUDDY.last_sent_response == player_response
        assert DUDE.last_sent_response == player_response

    async def test_on_message_game_with_message(self, client):
        channel = text_channel()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        message = "This is a message!"
        cmd = f"!game {mentions_str} -- {message}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> {game['url']}\n"
            f"> Players: <@{FRIEND.id}>, <@{BUDDY.id}>, <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_response_for(client, FRIEND, True, message=message)
        assert FRIEND.last_sent_response == player_response
        assert GUY.last_sent_response == player_response
        assert BUDDY.last_sent_response == player_response
        assert DUDE.last_sent_response == player_response

    async def test_on_message_game_with_auto_dequeue(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(FRIEND, channel, "!play"))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)
        assert channel.last_sent_response == (
            "Right on, I'll send you a Direct Message with details."
        )

        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> {game['url']}\n"
            f"> Players: <@{FRIEND.id}>, <@{BUDDY.id}>, <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_response_for(client, FRIEND, True)
        assert FRIEND.last_sent_response == player_response
        assert GUY.last_sent_response == player_response
        assert BUDDY.last_sent_response == player_response
        assert DUDE.last_sent_response == player_response

    async def test_on_message_game_multiple_times(self, client):
        channel = text_channel()

        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> {game['url']}\n"
            f"> Players: <@{FRIEND.id}>, <@{BUDDY.id}>, <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_response_for(client, FRIEND, True)
        assert FRIEND.last_sent_response == player_response
        assert GUY.last_sent_response == player_response
        assert BUDDY.last_sent_response == player_response
        assert DUDE.last_sent_response == player_response

        mentions = [AMY, JR, ADAM, FRIEND]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[1]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> {game['url']}\n"
            f"> Players: <@{AMY.id}>, <@{ADAM.id}>, <@{JR.id}>, <@{FRIEND.id}>"
        )
        player_response = game_response_for(client, FRIEND, True)
        assert FRIEND.last_sent_response == player_response
        assert AMY.last_sent_response == player_response
        assert JR.last_sent_response == player_response
        assert ADAM.last_sent_response == player_response

    async def test_ensure_server_exists(self, client, spoof_session):
        server = client.ensure_server_exists(5)
        client.session.commit()
        assert json.loads(str(server)) == {
            "guild_xid": 5,
            "prefix": "!",
            "scope": "server",
            "expire": 30,
            "friendly": True,
        }

    async def test_on_message_event_no_data(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(an_admin(), channel, "!event"))
        assert channel.last_sent_response == (
            "Sorry, you must include an attachment containing"
            " event data with this command."
        )

    async def test_on_message_event_no_params(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        message = MockMessage(an_admin(), channel, "!event", attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            "Please include the column names from the CSV file"
            " too identify the players' discord names."
        )

    async def test_on_message_event_invalid_player_count(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        message = MockMessage(an_admin(), channel, "!event a", attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == "Player count must be between 2 and 4."

    async def test_on_message_event_missing_player(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        warning = (
            "**Warning:** Event file is missing a player name on row 1."
            f' SpellBot will **NOT** create a game for the players: "{AMY.name}", "".'
        )
        assert warning in channel.all_sent_responses
        assert channel.last_sent_response == (
            "No games created for this event, please address any warnings and try again."
        )

    async def test_on_message_event_no_header(self, client):
        channel = text_channel()
        data = bytes(f"{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            "Sorry, the attached CSV file is missing a header."
        )

    async def test_on_message_event_no_header_v2(self, client):
        channel = text_channel()
        data = bytes("1,2,3\n4,5,6\n7,8,9", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            "Sorry, the attached CSV file is missing a header."
        )

    async def test_on_message_event_not_csv(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        txt_file = MockAttachment("event.txt", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[txt_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            "Sorry, the file is not a CSV file."
            ' Make sure the filename ends with ".csv" please.'
        )

    async def test_on_message_event_missing_discord_user(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{PUNK.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)

        warning = (
            '**Warning:** On row 1 the username "punk" is not on this server. '
            "SpellBot will **NOT** create a game for the players:"
            f' "{AMY.name}", "{PUNK.name}".'
        )
        assert warning in channel.all_sent_responses

    async def test_on_message_event_not_admin(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(not_an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            "You do not have admin permissions for this bot."
        )

    async def test_on_message_event_with_dequeue(self, client):
        channel = text_channel()

        await client.on_message(MockMessage(AMY, channel, "!play"))
        assert AMY.last_sent_response == game_response_for(client, AMY, False)

        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)

        events = all_events(client)
        assert len(events) == 1

        event = all_events(client)[0]
        assert channel.last_sent_response == (
            f"Event {event['id']} created! If everything looks good,"
            f" next run `!begin {event['id']}` to start the event."
        )

    async def test_on_message_event_message_too_long(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "foo bar baz" * 100
        comment = f"!event player1 player2 -- {opt}"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        assert channel.last_sent_response == (
            "Sorry, the optional game message must be shorter than 255 characters."
        )

    async def test_on_message_event(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        assert channel.last_sent_response == (
            f"Event {event['id']} created! If everything looks good,"
            f" next run `!begin {event['id']}` to start the event."
        )

    async def test_on_message_event_with_message(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "an message override"
        comment = f"!event player1 player2 -- {opt}"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        assert channel.last_sent_response == (
            f"Event {event['id']} created! If everything looks good,"
            f" next run `!begin {event['id']}` to start the event."
        )

    async def test_on_message_begin_not_admin(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Event {event_id} created! If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(
            MockMessage(not_an_admin(), channel, f"!begin {event_id}")
        )
        assert channel.last_sent_response == (
            "You do not have admin permissions for this bot."
        )

    async def test_on_message_begin_no_params(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(an_admin(), channel, "!begin"))
        assert channel.last_sent_response == "Please provide the event id."

    async def test_on_message_begin_bad_param(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(an_admin(), channel, "!begin sock"))
        assert channel.last_sent_response == (
            "Sorry, SpellBot can not find an event with that id."
        )

    async def test_on_message_begin_event_not_found(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Event {event_id} created! If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(
            MockMessage(an_admin(), channel, f"!begin {event_id + 1}")
        )
        assert channel.last_sent_response == (
            "Sorry, SpellBot can not find an event with that id."
        )

    async def test_on_message_begin_event(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Event {event_id} created! If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(an_admin(), channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> {game['url']}\n"
            f"> Players: {AMY.name}, {JR.name}"
        )
        player_response = game_response_for(client, AMY, True)
        assert AMY.last_sent_response == player_response
        assert JR.last_sent_response == player_response

    async def test_on_message_begin_event_with_message(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        opt = "this is an optional message"
        comment = f"!event player1 player2 -- {opt}"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Event {event_id} created! If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(an_admin(), channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> {game['url']}\n"
            f"> Players: {AMY.name}, {JR.name}"
        )
        player_response = game_response_for(client, AMY, True, message=opt)
        assert AMY.last_sent_response == player_response
        assert JR.last_sent_response == player_response

    async def test_on_message_begin_event_when_user_left(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Event {event_id} created! If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        # Simulate AMY leaving this Discord server
        global ALL_USERS
        ALL_USERS = [user for user in ALL_USERS if user != AMY]

        await client.on_message(MockMessage(an_admin(), channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            "**Warning:** A user left the server since this event was created."
            " SpellBot did **NOT** start the game for the players:"
            f" {AMY.name}, {JR.name}."
        )

    async def test_on_message_begin_event_already(self, client):
        channel = text_channel()
        data = bytes(f"player1,player2\n{AMY.name},{JR.name}", "utf-8")
        csv_file = MockAttachment("event.csv", data)
        comment = "!event player1 player2"
        message = MockMessage(an_admin(), channel, comment, attachments=[csv_file])
        await client.on_message(message)
        event = all_events(client)[0]
        event_id = event["id"]
        assert channel.last_sent_response == (
            f"Event {event_id} created! If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(an_admin(), channel, f"!begin {event_id}"))
        await client.on_message(MockMessage(an_admin(), channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            "Sorry, that event has already started and can not be started again."
        )

    async def test_on_message_spellbot_friendly_none(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot friendly"))
        assert channel.last_sent_response == 'Please indicate either "off" or "on".'

    async def test_on_message_spellbot_friendly_bad(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot friendly world"))
        assert channel.last_sent_response == (
            'Sorry, this setting should be either "off" or "on".'
        )

    async def test_on_message_spellbot_friendly(self, client):
        author = an_admin()
        channel = text_channel()
        await client.on_message(MockMessage(author, channel, "!spellbot friendly off"))
        assert channel.last_sent_response == (
            "Allow users to queue with their friends: off."
        )
        await client.on_message(MockMessage(author, channel, "!spellbot friendly on"))
        assert channel.last_sent_response == (
            "Allow users to queue with their friends: on."
        )

    async def test_on_message_play_all_non_friendly(self, client):
        channel = text_channel()
        await client.on_message(
            MockMessage(an_admin(), channel, "!spellbot friendly off")
        )

        mentions = [GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        content = f"!play {mentions_str}"
        await client.on_message(MockMessage(FRIEND, channel, content, mentions=mentions))
        assert FRIEND.last_sent_response == game_response_for(client, FRIEND, False)

        assert len(GUY.all_sent_calls) == 0
        assert len(BUDDY.all_sent_calls) == 0
        assert len(DUDE.all_sent_calls) == 0


def test_paginate():
    def subject(text):
        return [page for page in spellbot.paginate(text)]

    assert subject("") == [""]
    assert subject("four") == ["four"]

    with open(Path(FIXTURES_ROOT) / "ipsum_2011.txt") as f:
        text = f.read()
        pages = subject(text)
        assert len(pages) == 2
        assert all(len(page) <= 2000 for page in pages)
        assert pages == [text[0:1937], text[1937:]]

    with open(Path(FIXTURES_ROOT) / "aaa_2001.txt") as f:
        text = f.read()
        pages = subject(text)
        assert len(pages) == 2
        assert all(len(page) <= 2000 for page in pages)
        assert pages == [text[0:2000], text[2000:]]

    with open(Path(FIXTURES_ROOT) / "quotes.txt") as f:
        text = f.read()
        pages = subject(text)
        assert len(pages) == 2
        assert all(len(page) <= 2000 for page in pages)
        assert pages == [text[0:2000], f"> {text[2000:]}"]


class TestMigrations:
    def test_alembic(self, tmp_path):
        from spellbot.data import create_all, reverse_all
        from sqlalchemy import create_engine

        db_file = tmp_path / "spellbot.db"
        connection_url = f"sqlite:///{db_file}"
        engine = create_engine(connection_url)
        connection = engine.connect()
        create_all(connection, connection_url)
        reverse_all(connection, connection_url)


class TestCodebase:
    def test_flake8(self):
        """Checks that the Python codebase passes configured flake8 checks."""
        chdir(REPO_ROOT)
        cmd = ["flake8", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"flake8 issues:\n{proc.stdout.decode('utf-8')}"

    def test_black(self):
        """Checks that the Python codebase passes configured black checks."""
        chdir(REPO_ROOT)
        cmd = ["black", "-v", "--check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"black issues:\n{proc.stderr.decode('utf-8')}"

    def test_isort(self):
        """Checks that the Python codebase imports are correctly sorted."""
        chdir(REPO_ROOT)
        cmd = ["isort", "-df", "-rc", "-c", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"isort issues:\n{proc.stdout.decode('utf-8')}"

    def test_sort_strings(self):
        """Checks that the strings data is correctly sorted."""
        chdir(REPO_ROOT)
        cmd = ["python", "scripts/sort_strings.py", "--check"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, (
            f"sort strings issues:\n{proc.stdout.decode('utf-8')}\n\n"
            "Please run `poetry run scripts/sort_strings.py` to resolve this issue."
        )

    def test_snapshots_size(self):
        """Checks that none of the snapshots files are unreasonably small."""
        snapshots_dir = REPO_ROOT / "tests" / "snapshots"
        small_snapshots = []
        for f in snapshots_dir.glob("*.txt"):
            if f.stat().st_size <= 150:
                small_snapshots.append(f"- {f.name}")
        if small_snapshots:
            offenders = "\n".join(small_snapshots)
            assert False, (
                "Very small snapshot files are problematic.\n"
                "Offending snapshot files:\n"
                f"{offenders}\n"
                "Consider refacotring them to avoid using snapshots. Tests that use "
                "snapshots are harder to reason about when they fail. Whenever possible "
                "a test with inline data is much easier to reason about and refactor."
            )

    def test_readme_commands(self, client):
        """Checks that all commands are documented in our readme."""
        with open(REPO_ROOT / "README.md") as f:
            readme = f.read()

        documented = set(re.findall("^- `!([a-z]+)`: .*$", readme, re.MULTILINE))
        implemented = set(client.commands)

        assert sorted(documented) == sorted(implemented)

    def test_pyproject_dependencies(self):
        """Checks that pyproject.toml dependencies are sorted."""
        pyproject = toml.load("pyproject.toml")

        dev_deps = list(pyproject["tool"]["poetry"]["dev-dependencies"].keys())
        assert dev_deps == sorted(dev_deps)

        deps = list(pyproject["tool"]["poetry"]["dependencies"].keys())
        assert deps == sorted(deps)


# These tests will fail in isolation, you must run the full test suite for them to pass.
class TestMeta:
    # Tracks the usage of string keys over the entire test session.
    # It can fail for two reasons:
    #
    # 1. There's a key in strings.yaml that's not being used at all.
    # 2. There's a key in strings.yaml that isn't being used in the tests.
    #
    # For situation #1 the solution is to remove the key from the config.
    # As for #2, there should be a new test which utilizes this key.
    def test_strings(self):
        """Assues that there are no missing or unused strings data."""
        used_keys = set(s_call[0][0] for s_call in S_SPY.call_args_list)
        config_keys = set(load_strings().keys())
        if "did_you_mean" not in used_keys:
            warn('strings.yaml key "did_you_mean" is unused in test suite')
            used_keys.add("did_you_mean")
        assert config_keys - used_keys == set()

    # Tracks the usage of snapshot files over the entire test session.
    # When it fails it means you probably need to clear out any unused snapshot files.
    def test_snapshots(self):
        """Checks that all of the snapshots files are being used."""
        snapshots_dir = REPO_ROOT / "tests" / "snapshots"
        snapshot_files = set(f.name for f in snapshots_dir.glob("*.txt"))
        assert snapshot_files == SNAPSHOTS_USED
