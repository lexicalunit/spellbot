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
import pytz
import toml

import spellbot
from spellbot.assets import load_strings
from spellbot.constants import THUMB_URL
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


MOCK_DISCORD_MESSAGE_ID_START = 5000


class MockDiscordMessage:
    def __init__(self):
        global MOCK_DISCORD_MESSAGE_ID_START
        self.id = MOCK_DISCORD_MESSAGE_ID_START
        MOCK_DISCORD_MESSAGE_ID_START += 1
        self.reactions = []

        # edited is a spy for tracking calls to edit(), it doesn't exist on the real obj.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_edited_XXX` and `all_edited_XXX` to make our lives easier.
        self.edited = AsyncMock()

    async def add_reaction(self, emoji):
        self.reactions.append(emoji)

    async def clear_reactions(self):
        self.reactions = []

    async def delete(self):
        pass

    async def remove_reaction(self, emoji, user):
        done = False
        update = []
        for reaction in self.reactions:
            if not done and reaction == emoji:
                done = True
                continue
            update.append(reaction)
        self.reactions = update

    async def edit(self, content=None, *args, **kwargs):
        await self.edited(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )

    @property
    def last_edited_call(self):
        args, kwargs = self.edited.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_edited_response(self):
        return self.all_edited_responses[-1]

    @property
    def last_edited_embed(self):
        return self.last_edited_call["kwargs"]["embed"].to_dict()

    @property
    def all_edited_calls(self):
        edited_calls = []
        for edited_call in self.edited.call_args_list:
            args, kwargs = edited_call
            edited_calls.append({"args": args, "kwargs": kwargs})
        return edited_calls

    @property
    def all_edited_responses(self):
        return [edited_call["args"][0] for edited_call in self.all_edited_calls]

    @property
    def all_edited_embeds(self):
        return [
            edited_call["kwargs"]["embed"].to_dict()
            for edited_call in self.all_edited_calls
            if "embed" in edited_call["kwargs"]
        ]


class MockPayload:
    def __init__(self, user_id, emoji, channel_id, message_id, guild_id, member=None):
        self.member = member
        self.user_id = user_id
        self.emoji = emoji
        self.channel_id = channel_id
        self.message_id = message_id
        self.guild_id = guild_id


def send_side_effect(*args, **kwargs):
    return MockDiscordMessage()


class MockMember:
    def __init__(self, member_name, member_id, roles=[], admin=False):
        self.name = member_name
        self.id = member_id
        self.roles = roles
        self.avatar_url = "http://example.com/avatar.png"
        self.bot = False
        self.admin = admin

        # sent is a spy for tracking calls to send(), it doesn't exist on the real object.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_sent_XXX` and `all_sent_XXX` to make our lives easier.
        self.sent = AsyncMock(side_effect=send_side_effect)
        self.last_sent_message = None

    async def send(self, content=None, *args, **kwargs):
        self.last_sent_message = await self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )
        return self.last_sent_message

    def permissions_in(self, channel):
        class Permissions:
            def __init__(self, administrator):
                self.administrator = administrator

        return Permissions(self.admin)

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
    """Don't create this directly, use the channel_maker fixture instead."""

    def __init__(self, channel_id, channel_type):
        self.id = channel_id
        self.type = channel_type

        # sent is a spy for tracking calls to send(), it doesn't exist on the real object.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_sent_XXX` and `all_sent_XXX` to make our lives easier.
        self.sent = AsyncMock(side_effect=send_side_effect)
        self.last_sent_message = None
        self.messages = []

    async def send(self, content=None, *args, **kwargs):
        self.last_sent_message = await self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )
        self.messages.append(self.last_sent_message)
        return self.last_sent_message

    async def fetch_message(self, message_id):
        for message in self.messages:
            if message.id == message_id:
                return message
        return None

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
    """Don't create this directly, use the channel_maker fixture instead."""

    def __init__(self, channel_id, channel_name, members):
        super().__init__(channel_id, "text")
        self.name = channel_name
        self.members = members
        self.guild = MockGuild(500, "Guild Name", members)


class MockDM(MockChannel):
    """Don't create this directly, use the channel_maker fixture instead."""

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
        self.channels = []

    def get_user(self, user_id):
        for user in ALL_USERS:
            if user.id == user_id:
                return user

    async def fetch_user(self, user_id):
        return self.get_user(user_id)

    def get_channel(self, channel_id):
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        return None

    async def fetch_channel(self, channel_id):
        return self.get_channel(channel_id)


##############################
# Test Suite Constants
##############################

CLIENT_TOKEN = "my-token"
CLIENT_AUTH = "my-auth"
CLIENT_USER = "ADMIN"
CLIENT_USER_ID = 82226367030108160

TST_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = TST_ROOT / "fixtures"
REPO_ROOT = TST_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"

SRC_DIRS = [REPO_ROOT / "tests", SRC_ROOT / "spellbot", REPO_ROOT / "scripts"]

ADMIN_ROLE = MockRole("SpellBot Admin")
PLAYER_ROLE = MockRole("Player Player")

ADMIN = MockMember(CLIENT_USER, CLIENT_USER_ID, roles=[ADMIN_ROLE], admin=True)
FRIEND = MockMember("friend", 82169952898900001, roles=[PLAYER_ROLE])
BUDDY = MockMember("buddy", 82942320688700002, roles=[ADMIN_ROLE, PLAYER_ROLE])
GUY = MockMember("guy", 82988021019800003)
DUDE = MockMember("dude", 82988761019800004, roles=[ADMIN_ROLE])

JR = MockMember("J.R.", 72988021019800005)
ADAM = MockMember("Adam", 62988021019800006)
TOM = MockMember("Tom", 62988021019800016)
AMY = MockMember("Amy", 52988021019800007)
JACOB = MockMember("Jacob", 42988021019800008)

PUNK = MockMember("punk", 119678027792600009)  # for a memeber that's not in our channel
BOT = MockMember("robot", 82169567890900010)
BOT.bot = True
ADMIN.bot = True

SERVER_MEMBERS = [FRIEND, BUDDY, GUY, DUDE, ADMIN, JR, ADAM, TOM, AMY, JACOB]
ALL_USERS = []  # users that are on the server, setup in client fixture

S_SPY = Mock(wraps=spellbot.s)

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


def game_embed_for(client, user, ready, message=None):
    session = client.data.Session()
    db_user = session.query(User).filter(User.xid == user.id).first()
    rvalue = db_user.game.to_embed() if db_user and db_user.game else None
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
    ALL_USERS = SERVER_MEMBERS + [PUNK, BOT]

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
def session(client):
    """
    The client creates a session when processing a command,
    we have to create one ourselves when not in a command context.
    """
    return client.data.Session()


@pytest.fixture
def channel_maker(client):
    """Use this fixture to create channels so that we can hook them up to the client."""

    class MockChannelFactory:
        def __init__(self, next_channel_id):
            self.next_channel_id = next_channel_id

        def text(self, name="a-text-channel", members=SERVER_MEMBERS):
            channel = MockTextChannel(self.next_channel_id, name, members)
            client.channels.append(channel)  # not something you can do with a real client
            self.next_channel_id += 1
            return channel

        def dm(self):
            channel = MockDM(self.next_channel_id)
            self.next_channel_id += 1
            return channel

        def make(self, channel_type):
            if channel_type == "dm":
                return self.dm()
            return self.text()

    return MockChannelFactory(6500)


##############################
# Test Suites
##############################


@pytest.mark.asyncio
class TestSpellBot:
    async def test_init(self, client, channel_maker):
        assert client.token == CLIENT_TOKEN

    async def test_on_ready(self, client, channel_maker):
        await client.on_ready()

    async def test_on_message_non_text(self, client, channel_maker):
        channel = MockChannel(6, "voice")
        await client.on_message(MockMessage(someone(), channel, "!help"))
        channel.sent.assert_not_called()

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_is_admin(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        assert spellbot.is_admin(channel, not_an_admin()) == False
        assert spellbot.is_admin(channel, an_admin()) == True

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

        # TODO: Coverage for all functionality of parse_opts could be here, but it is
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
        self, client, channel_maker, channel_type
    ):
        author = someone()
        channel = channel_maker.make(channel_type)
        msg = MockMessage(author, channel, "!l")
        if hasattr(channel, "recipient"):
            assert channel.recipient == author
        await client.on_message(msg)
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, that's not a command."
            " Did you mean to use one of these commands: !leave, !lfg?"
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_invalid_request(self, client, channel_maker, channel_type):
        dm = channel_maker.make(channel_type)
        author = someone()
        await client.on_message(MockMessage(author, dm, "!xeno"))
        assert dm.last_sent_response == (
            f'Sorry <@{author.id}>, there is no "xeno" command.'
        )

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_from_a_bot(self, client, channel_maker, channel_type):
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(BOT, channel, "!help"))
        assert len(channel.all_sent_calls) == 0

    @pytest.mark.parametrize("channel_type", ["dm", "text"])
    async def test_on_message_help(self, client, channel_maker, channel_type, snap):
        author = someone()
        channel = channel_maker.make(channel_type)
        await client.on_message(MockMessage(author, channel, "!help"))
        for response in author.all_sent_responses:
            snap(response)
        assert len(author.all_sent_calls) == 3

    async def test_on_message_spellbot_dm(self, client, channel_maker):
        author = an_admin()
        dm = channel_maker.dm()
        await client.on_message(MockMessage(author, dm, "!spellbot channels foo"))
        assert author.last_sent_response == (
            f"Hello <@{author.id}>! That command only works in text channels."
        )

    async def test_on_message_spellbot_non_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_spellbot_no_subcommand(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, please provide a subcommand when using this command."
        )

    async def test_on_message_spellbot_bad_subcommand(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot foo"))
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but the subcommand "foo" is not recognized.'
        )

    async def test_on_message_spellbot_channels_none(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot channels"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please provide a list of channels."
            " Like #bot-commands, for example."
        )

    async def test_on_message_spellbot_channels_all_bad(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!spellbot channels foo"))
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "foo" is not a valid channel. Try using # to'
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
            f'Sorry <@{author.id}>, but "foo" is not a valid channel. Try using # to'
            ' mention the channels you want or using "all" if you want me to operate'
            " in all channels."
        )
        assert channel.all_sent_responses[1] == (
            f"Ok <@{author.id}>, I will now operate within: <#{channel.id}>"
        )

    async def test_on_message_spellbot_channels_with_bad_ref(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels <#{channel.id + 1}>")
        )
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "<#{channel.id + 1}>" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

    async def test_on_message_spellbot_channels_with_invalid(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels #{channel.id}")
        )
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "#{channel.id}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )

        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

    async def test_on_message_spellbot_channels_no_mention(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels #{channel.name}")
        )
        assert channel.last_sent_response == (
            f'Sorry <@{author.id}>, but "#{channel.name}" is not a valid channel.'
            ' Try using # to mention the channels you want or using "all" if you'
            " want me to operate in all channels."
        )

        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

    async def test_on_message_spellbot_channels(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        foo = channel_maker.text("foo")
        bar = channel_maker.text("bar")
        baz = channel_maker.text("baz")
        await client.on_message(
            MockMessage(author, channel, f"!spellbot channels <#{channel.id}>")
        )
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, I will now operate within: <#{channel.id}>"
        )
        cmd = f"!spellbot channels <#{foo.id}> <#{bar.id}> <#{baz.id}>"
        await client.on_message(MockMessage(author, channel, cmd))
        resp = (
            f"Ok <@{author.id}>, I will now operate within:"
            f" <#{foo.id}>, <#{bar.id}>, <#{baz.id}>"
        )
        assert channel.last_sent_response == resp
        await client.on_message(MockMessage(author, channel, "!help"))  # bad channel now
        assert channel.last_sent_response == resp

        await client.on_message(MockMessage(author, foo, "!spellbot channels all"))
        assert foo.last_sent_response == (
            f"Ok <@{author.id}>, I will now operate within: all channels"
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
            "Use the command `!help` for usage details. Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            "[🔗 Add SpellBot to your Discord!](https://discordapp.com/api/oauth2"
            "/authorize?client_id=725510263251402832&permissions=92224&scope=bot)\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[supporting me on Ko-fi!](https://ko-fi.com/Y8Y51VTHZ)"
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
            f"Sorry <@{author.id}>, but please provide a prefix string."
        )

    async def test_on_message_spellbot_prefix(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use "$" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "$about"))
        assert channel.last_sent_embed["url"] == "http://spellbot.io/"
        await client.on_message(MockMessage(author, channel, "$spellbot prefix $"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use "$" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "$spellbot prefix !"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use "!" as my command prefix on this server.'
        )
        await client.on_message(MockMessage(author, channel, "!spellbot prefix )"))
        assert channel.last_sent_response == (
            f'Ok <@{author.id}>, I will now use ")" as my command prefix on this server.'
        )

    async def test_on_message_spellbot_expire_none(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but please provide a number of minutes."
        )

    async def test_on_message_spellbot_expire_bad(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire world"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but game expiration time"
            " should be between 10 and 60 minutes."
        )

    async def test_on_message_spellbot_expire(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot expire 45"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, game expiration time on this"
            " server has been set to 45 minutes."
        )

    async def test_on_message_spellbot_config(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot prefix $"))
        await client.on_message(MockMessage(author, channel, "$spellbot expire 45"))
        await client.on_message(MockMessage(author, channel, "$spellbot config"))

        about = channel.last_sent_embed
        assert about["title"] == "SpellBot Server Config"
        assert about["footer"]["text"] == f"Config for Guild ID: {channel.guild.id}"
        assert about["thumbnail"]["url"] == THUMB_URL
        fields = {f["name"]: f["value"] for f in about["fields"]}
        assert fields["Inactivity expiration time"] == "45 minutes"
        assert fields["Active channels"] == "all"

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
        mentions = [FRIEND, GUY, BUDDY, DUDE, AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, you mentioned too many people."
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
            f"Sorry <@{author.id}>, you mentioned too few people."
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
            f"Sorry <@{author.id}>, but you can not use more than 5 tags."
        )

    async def test_on_message_game_with_size_bad(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str} size:100"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_game_non_admin(self, client, channel_maker):
        channel = channel_maker.text()
        author = not_an_admin()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
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
            f"Sorry <@{author.id}>, but the optional game message"
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
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert game_json_for(client, GUY)["tags"] == []
        assert game_json_for(client, GUY)["message"] == None

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
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
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
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
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
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{AMY.id}>, <@{ADAM.id}>"
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
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
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
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
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
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{AMY.id}>, <@{ADAM.id}>,"
            f" <@{JR.id}>, <@{FRIEND.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert AMY.last_sent_embed == player_response
        assert JR.last_sent_embed == player_response
        assert ADAM.last_sent_embed == player_response

    async def test_ensure_server_exists(self, client, session):
        server = client.ensure_server_exists(session, 5)
        session.commit()
        assert json.loads(str(server)) == {
            "channels": [],
            "guild_xid": 5,
            "prefix": "!",
            "expire": 30,
        }

    async def test_on_message_event_no_data(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!event"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you must include an attachment containing"
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
            f"Sorry <@{author.id}>, please include the column names from the CSV file"
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
            f"Sorry <@{author.id}>, but the player count must be between 2 and 4."
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
            f"Hey <@{author.id}>, no games were created for this event."
            " Please address any warnings and try again."
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
            f"Sorry <@{author.id}>, but the attached CSV file is missing a header."
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
            f"Sorry <@{author.id}>, but the attached CSV file is missing a header."
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
            f"Sorry <@{author.id}>, but the file is not a CSV file."
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
            f"<@{author.id}>, you do not have admin permissions to run that command."
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
            f"Sorry <@{author.id}>, but the optional game message"
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
            f"Sorry <@{author.id}>, but you can not use more than 5 tags."
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
            f"**Error:** The user {AMY.name} appears in more than one paring in this"
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
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
            f"Ok <@{admin.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(not_admin, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            f"<@{not_admin.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_begin_no_params(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!begin"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, please provide the event ID with that command."
        )

    async def test_on_message_begin_bad_param(self, client, channel_maker):
        channel = channel_maker.text()
        author = an_admin()
        await client.on_message(MockMessage(author, channel, "!begin sock"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but I can't find an event with that ID."
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id + 1}"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but I can't find an event with that ID."
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
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
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        # Simulate AMY leaving this Discord server
        global ALL_USERS
        ALL_USERS = [user for user in ALL_USERS if user != AMY]

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
            f"Ok <@{author.id}>, I've created event {event_id}!"
            " This event will have 1 games. If everything looks good,"
            f" next run `!begin {event_id}` to start the event."
        )

        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        await client.on_message(MockMessage(author, channel, f"!begin {event_id}"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but that event has already started"
            " and can not be started again."
        )

    async def test_on_message_lfg_dm(self, client, channel_maker):
        channel = channel_maker.dm()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert author.last_sent_response == (
            f"Hello <@{author.id}>! That command only works in text channels."
        )

    async def test_on_message_lfg_size_too_much(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:10"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_too_many_mentions(self, client, channel_maker):
        channel = channel_maker.text()
        author = DUDE
        mentions = [FRIEND, GUY, BUDDY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you've mentioned too many players"
            " for that size game."
        )

    async def test_on_message_lfg_mention_already(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg"))

        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"Sorry <@{JR.id}>, but <@{AMY.id}> is already in another"
            " pending game and can't be invited."
        )

    async def test_on_message_lfg_size_too_little(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:1"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_size_not_number(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg size:x"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_lfg_too_many_tags(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg ~a ~b ~c ~d ~e ~f"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you can not use more than 5 tags."
        )

    async def test_on_message_lfg_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert channel.last_sent_response == (
            f"Hi <@{author.id}>! You're already waiting in a game."
            " If you want to, you can leave that game with `!leave` and then try again."
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
            emoji="➕",
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
                {"inline": True, "name": "Players", "value": f"<@{ADAM.id}>, <@{JR.id}>"}
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
            emoji="➕",
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
                {"inline": True, "name": "Players", "value": f"<@{ADAM.id}>, <@{JR.id}>"}
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

    async def test_on_message_lfg_with_invite(self, client, channel_maker):
        channel = channel_maker.text()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert len(channel.all_sent_calls) == 0
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )
        assert ADAM.last_sent_response == (
            f"Hello <@{ADAM.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )

    async def test_on_message_lfg_with_invite_all_confirmed(self, client, channel_maker):
        channel = channel_maker.text()
        dm = channel_maker.dm()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert len(channel.all_sent_calls) == 0
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )
        assert ADAM.last_sent_response == (
            f"Hello <@{ADAM.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )

        await client.on_message(MockMessage(AMY, dm, "yes"))
        assert AMY.last_sent_response == (
            f"Thanks <@{AMY.id}>, your invitation has been confirmed!"
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(AMY, dm, "yes"))
        assert AMY.last_sent_response == (
            f"Hi <@{AMY.id}>, just letting you know that your invitation"
            " was already confirmed."
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(ADAM, dm, "yes"))
        assert ADAM.last_sent_response == (
            f"Thanks <@{ADAM.id}>, your invitation has been confirmed!"
        )

        assert channel.last_sent_embed == game_embed_for(client, JR, False)
        assert channel.last_sent_embed == game_embed_for(client, AMY, False)
        assert channel.last_sent_embed == game_embed_for(client, ADAM, False)

    async def test_on_message_lfg_with_invite_some_confirmed(self, client, channel_maker):
        channel = channel_maker.text()
        dm = channel_maker.dm()
        mentions = [AMY, ADAM]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!lfg {mentions_str}"
        await client.on_message(MockMessage(JR, channel, cmd, mentions=mentions))
        assert len(channel.all_sent_calls) == 0
        assert AMY.last_sent_response == (
            f"Hello <@{AMY.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )
        assert ADAM.last_sent_response == (
            f"Hello <@{ADAM.id}>! You've been invited to a game by <@{JR.id}>."
            " To confirm or deny please respond with yes or no."
        )

        await client.on_message(MockMessage(AMY, dm, "yes"))
        assert AMY.last_sent_response == (
            f"Thanks <@{AMY.id}>, your invitation has been confirmed!"
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(DUDE, dm, "yes"))
        assert DUDE.last_sent_response == (
            f"Sorry <@{DUDE.id}>, but you do not currently have any pending invitations."
        )
        assert len(channel.all_sent_calls) == 0

        await client.on_message(MockMessage(ADAM, dm, "no"))
        assert ADAM.last_sent_response == f"Thank you for your response, <@{ADAM.id}>."

        assert channel.last_sent_embed == game_embed_for(client, JR, False)
        assert channel.last_sent_embed == game_embed_for(client, AMY, False)
        assert not user_has_game(client, ADAM)

    async def test_on_message_leave(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, author, False)
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Ok <@{author.id}>, you've been removed from the pending game"
            " that you were signed up for."
        )

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_message_leave_already(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!leave"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you we're not in any pending games."
        )

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
        assert game_embed_for(client, ADAM, False) == None

    async def test_on_raw_reaction_add_bad_channel(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id + 1,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == None

    async def test_on_raw_reaction_add_self(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADMIN.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADMIN,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADMIN, False) == None

    async def test_on_raw_reaction_add_bad_message(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id + 1,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == None

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
            emoji="➕",
            channel_id=channel_a.id,
            guild_id=channel_a.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert game_embed_for(client, ADAM, False) == None

    async def test_on_raw_reaction_add_plus_not_a_game(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!leave"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert message.reactions == []

    async def test_on_raw_reaction_add_plus_twice(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        await client.on_raw_reaction_add(payload)
        assert len(ADAM.all_sent_calls) == 0

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_already(self, client, channel_maker):
        channel = channel_maker.text()

        # first game
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)

        # second game
        await client.on_message(MockMessage(JR, channel, "!lfg ~modern"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert ADAM.last_sent_response == (
            f"Sorry <@{ADAM.id}>, I couldn't add you to that game"
            " because you're already signed up for another game."
            " You can use `!leave` to leave that game."
        )

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert "2 more players" in game_embed_for(client, ADAM, False)["title"]

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_complete(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        ready = game_embed_for(client, ADAM, True)
        assert GUY.last_sent_embed == ready
        assert ADAM.last_sent_embed == ready

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_after_disconnect(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg size:2"))
        message = channel.last_sent_message

        # Simulate GUY leaving this Discord server
        global ALL_USERS
        ALL_USERS = [user for user in ALL_USERS if user != GUY]

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert "1 more player" in game_embed_for(client, ADAM, False)["title"]

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_plus_then_minus(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message

        assert not user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, ADAM)

        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➖",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        assert not user_has_game(client, ADAM)

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_minus_to_empty_game(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message

        payload = MockPayload(
            user_id=GUY.id,
            message_id=message.id,
            emoji="➖",
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
                "description": "To join/leave this game, react with ➕/➖.",
                "footer": {"text": f"SpellBot Reference #SB{games[0].id}"},
                "thumbnail": {"url": THUMB_URL},
                "title": "**Waiting for 4 more players to join...**",
                "type": "rich",
            },
        ]

        # TODO: Actually test that the embed was edited correctly.

    async def test_on_raw_reaction_add_minus_when_not_in_game(
        self, client, channel_maker
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
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
            emoji="➖",
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
            emoji="➕",
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
            emoji="➖",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=AMY,
        )
        await client.on_raw_reaction_add(payload)
        assert user_has_game(client, AMY)

    async def test_game_cleanup_started(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Link: <{game['url']}>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert user_has_game(client, FRIEND)

        freezer.move_to(NOW + timedelta(days=3))
        await client.cleanup_started_games()

        assert not user_has_game(client, FRIEND)

    async def test_game_cleanup_expired(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, GUY, False)

        assert user_has_game(client, GUY)

        freezer.move_to(NOW + timedelta(days=3))
        await client.cleanup_expired_games()

        assert not user_has_game(client, GUY)
        assert GUY.last_sent_response == (
            f"My appologies <@{GUY.id}>,"
            " but I deleted your pending game due to server inactivity."
        )

        # TODO: Actually test that the embed was deleted correctly.

    async def test_game_cleanup_expired_after_left(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        assert channel.last_sent_embed == game_embed_for(client, GUY, False)

        assert user_has_game(client, GUY)

        # Simulate GUY leaving this Discord server
        global ALL_USERS
        ALL_USERS = [user for user in ALL_USERS if user != GUY]

        freezer.move_to(NOW + timedelta(days=3))
        await client.cleanup_expired_games()

        assert not user_has_game(client, GUY)
        assert len(GUY.all_sent_calls) == 0

        # TODO: Actually test that the embed was deleted correctly.

    async def test_on_message_export_non_admin(self, client, channel_maker):
        channel = channel_maker.text()
        author = GUY
        await client.on_message(MockMessage(author, channel, "!export"))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_export(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(JR, channel, "!lfg size:2 ~mtgo"))
        message = channel.last_sent_message
        payload = MockPayload(
            user_id=ADAM.id,
            message_id=message.id,
            emoji="➕",
            channel_id=channel.id,
            guild_id=channel.guild.id,
            member=ADAM,
        )
        await client.on_raw_reaction_add(payload)
        game = all_games(client)[0]
        created_at = game["created_at"]

        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))

        await client.on_message(MockMessage(an_admin(), channel, "!export"))
        attachment = channel.all_sent_files[0]
        assert attachment.fp.read() == (
            str.encode(
                "id,size,status,message,system,channel_xid,url,event_id,created_at,tags\n"
                f"{game['id']},2,started,,mtgo,#{channel.name},,,{created_at},\n"
            )
        )

    async def test_on_message_play(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(ADAM, channel, "!play ~modern"))
        assert len(all_games(client)) == 1

        await client.on_message(MockMessage(ADAM, channel, "!play ~modern"))
        assert len(all_games(client)) == 1

        await client.on_message(MockMessage(JR, channel, "!play ~modern ~chaos"))
        assert len(all_games(client)) == 2

        await client.on_message(MockMessage(AMY, channel, "!play ~modern"))
        assert len(all_games(client)) == 2

        assert game_embed_for(client, ADAM, False) == game_embed_for(client, AMY, False)

        await client.on_message(MockMessage(TOM, channel, "!play ~modern ~chaos"))
        assert len(all_games(client)) == 2
        assert game_embed_for(client, JR, False) == game_embed_for(client, TOM, False)

        await client.on_message(MockMessage(JACOB, channel, "!play"))
        assert len(all_games(client)) == 3

        await client.on_message(MockMessage(GUY, channel, "!play ~modern ~no-ban-list"))
        assert len(all_games(client)) == 4

    async def test_on_message_play_full(self, client, channel_maker):
        channel = channel_maker.text()

        await client.on_message(MockMessage(JR, channel, "!play size:2"))
        assert len(all_games(client)) == 1

        await client.on_message(MockMessage(TOM, channel, "!play size:2"))
        assert len(all_games(client)) == 1
        assert game_embed_for(client, JR, True) == game_embed_for(client, TOM, True)

    async def test_on_message_join_none_found(self, client, channel_maker):
        channel = channel_maker.text()
        author = someone()
        await client.on_message(MockMessage(author, channel, "!join"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but I didn't find any games for you to join."
        )

    async def test_on_message_join(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg"))
        await client.on_message(MockMessage(JACOB, channel, "!join"))
        assert game_embed_for(client, AMY, False) == game_embed_for(client, JACOB, False)

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
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

        await client.on_message(MockMessage(author, channel, "!leave"))
        await client.on_message(MockMessage(author, channel, "!lfg ~emperor"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but the game size must be between 2 and 4."
        )

    async def test_on_message_join_up_with_someone(self, client, channel_maker):
        channel = channel_maker.text()
        await client.on_message(MockMessage(AMY, channel, "!lfg ~modern"))

        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!join {mentions_str}"
        await client.on_message(MockMessage(JACOB, channel, cmd, mentions=mentions))
        assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)

    async def test_on_message_spellbot_help(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!spellbot help"))
        assert len(channel.all_sent_calls) == 1
        assert len(author.all_sent_calls) >= 1

    async def test_on_message_queue_no_mentions(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        await client.on_message(MockMessage(author, channel, "!queue"))
        assert channel.last_sent_response == (
            f"Sorry <@{author.id}>, but you need to mention at least one player."
        )

    async def test_on_message_queue_dm(self, client, channel_maker):
        author = an_admin()
        dm = channel_maker.dm()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str}"
        await client.on_message(MockMessage(author, dm, cmd, mentions=mentions))
        assert author.last_sent_response == (
            f"Hello <@{author.id}>! That command only works in text channels."
        )

    async def test_on_message_queue_non_admin(self, client, channel_maker):
        author = not_an_admin()
        channel = channel_maker.text()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str}"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"<@{author.id}>, you do not have admin permissions to run that command."
        )

    async def test_on_message_queue_admin(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.all_sent_responses[0] == f"I added <@{AMY.id}> to a queue."
        game = all_games(client)[0]
        game_id = game["id"]
        assert channel.all_sent_embeds[0] == {
            "color": 5914365,
            "description": "To join/leave this game, react with ➕/➖.",
            "fields": [{"inline": True, "name": "Players", "value": f"<@{AMY.id}>"}],
            "footer": {"text": f"SpellBot Reference #SB{game_id}"},
            "thumbnail": {"url": THUMB_URL},
            "title": "**Waiting for 1 more player to join...**",
            "type": "rich",
        }

    async def test_on_message_queue_twice(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()
        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))
        assert channel.last_sent_response == (
            f"The player <@{AMY.id}> was already in a game. I have removed them from"
            " that game. If you want to enter them into a queue, please run that"
            " command again to add them."
        )
        assert len(all_games(client)) == 1
        assert game_json_for(client, AMY) == None

    async def test_on_message_queue_till_ready(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()

        mentions = [AMY]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))

        mentions = [JR]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))

        assert game_embed_for(client, AMY, True) == game_embed_for(client, JR, True)

    async def test_on_message_queue_till_ready_all(self, client, channel_maker):
        author = an_admin()
        channel = channel_maker.text()

        mentions = [AMY, JR]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!queue {mentions_str} size:2"
        await client.on_message(MockMessage(author, channel, cmd, mentions=mentions))

        assert game_embed_for(client, AMY, True) == game_embed_for(client, JR, True)


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
        from sqlalchemy import create_engine

        from spellbot.data import create_all, reverse_all

        db_file = tmp_path / "spellbot.db"
        connection_url = f"sqlite:///{db_file}"
        engine = create_engine(connection_url)
        connection = engine.connect()
        create_all(connection, connection_url)
        reverse_all(connection, connection_url)


class TestCodebase:
    def test_mypy(self):
        """Checks that the Python codebase passes mypy static analysis checks."""
        chdir(REPO_ROOT)
        cmd = ["mypy", *SRC_DIRS, "--warn-unused-configs"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"mypy issues:\n{proc.stdout.decode('utf-8')}"

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
        cmd = ["black", "--check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"black issues:\n{proc.stderr.decode('utf-8')}"

    def test_isort(self):
        """Checks that the Python codebase imports are correctly sorted."""
        chdir(REPO_ROOT)
        cmd = ["isort", "--df", "-w90", "-c", *SRC_DIRS]
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

    def test_readme_commands(self, client, channel_maker):
        """Checks that all commands are documented in our readme."""
        with open(REPO_ROOT / "README.md") as f:
            readme = f.read()

        documented = set(re.findall("^- `!([a-z]+)`: .*$", readme, re.MULTILINE))
        implemented = set(client._commands.values())

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
