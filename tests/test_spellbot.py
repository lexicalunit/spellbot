import inspect
import json
import random
import re
from contextlib import asynccontextmanager
from datetime import datetime
from os import chdir
from os.path import dirname, realpath
from pathlib import Path
from subprocess import run
from unittest.mock import MagicMock, Mock

import pytest
import pytz
import toml
from discord import Embed

import spellbot
from spellbot.assets import load_strings

##############################
# Discord.py Mocks
##############################


class MockFile:
    def __init__(self, fp):
        self.fp = fp


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
        self.sent = MagicMock()

    async def send(self, content=None, *args, **kwargs):
        self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )

    @property
    def last_sent_call(self):
        args, kwargs = self.sent.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_sent_response(self):
        return self.last_sent_call["args"][0]

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
    def __init__(self, channel_id, members):
        self.members = members
        self.id = channel_id


class MockChannel:
    def __init__(self, channel_id, channel_type):
        self.id = channel_id
        self.type = channel_type

        # sent is a spy for tracking calls to send(), it doesn't exist on the real object.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_sent_XXX` and `all_sent_XXX` to make our lives easier.
        self.sent = MagicMock()

    async def send(self, content=None, *args, **kwargs):
        self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )

    @property
    def last_sent_call(self):
        args, kwargs = self.sent.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_sent_response(self):
        return self.last_sent_call["args"][0]

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
        self.guild = MockGuild(channel_id, members)


class MockDM(MockChannel):
    def __init__(self, channel_id):
        super().__init__(channel_id, "private")
        self.recipient = None  # can't be set until we know the author of a message


class MockMessage:
    def __init__(self, author, channel, content):
        self.author = author
        self.channel = channel
        self.content = content
        if isinstance(channel, MockDM):
            channel.recipient = author


class MockDiscordClient:
    def __init__(self, **kwargs):
        self.user = ADMIN


##############################
# Test Suite Constants
##############################

CLIENT_TOKEN = "my-token"
CLIENT_AUTH = "my-auth"
CLIENT_USER = "ADMIN"
CLIENT_USER_ID = 82226367030108160

AUTHORIZED_CHANNEL = "good channel"
UNAUTHORIZED_CHANNEL = "bad channel"

NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
LAST_SUNDAY = datetime(year=1982, month=4, day=18, tzinfo=pytz.utc)

TST_ROOT = dirname(realpath(__file__))
FIXTURES_ROOT = Path(TST_ROOT) / "fixtures"
REPO_ROOT = Path(TST_ROOT).parent
SRC_ROOT = REPO_ROOT / "src"

SRC_DIRS = [REPO_ROOT / "tests", SRC_ROOT / "spellbot", REPO_ROOT / "scripts"]

ADMIN_ROLE = MockRole("SpellBot Admin")
PLAYER_ROLE = MockRole("Player Player")

ADMIN = MockMember(CLIENT_USER, CLIENT_USER_ID, roles=[ADMIN_ROLE])
FRIEND = MockMember("friend", 82169952898912256, roles=[PLAYER_ROLE])
BUDDY = MockMember("buddy", 82942320688758784, roles=[ADMIN_ROLE, PLAYER_ROLE])
GUY = MockMember("guy", 82988021019836416)
DUDE = MockMember("dude", 82988761019835305, roles=[ADMIN_ROLE])
PUNK = MockMember("punk", 119678027792646146)  # for a memeber that's not in our channel
BOT = MockMember("robot", 82169567890912256)
BOT.bot = True

CHANNEL_MEMBERS = [FRIEND, BUDDY, GUY, DUDE, ADMIN]
ALL_USERS = CHANNEL_MEMBERS + [PUNK, BOT]

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
def client(monkeypatch, mocker, freezer, patch_discord, tmp_path):
    monkeypatch.setattr(spellbot, "s", S_SPY)

    # Unless changed in the test itself, all tests will assume the same datetime.
    freezer.move_to(NOW)

    # Fallback to using sqlite for tests, but use the environment variable if it's set.
    db_url = spellbot.get_db_url(
        "TEST_SPELLBOT_DB_URL", f"sqlite:///{tmp_path}/spellbot.db"
    )
    bot = spellbot.SpellBot(token=CLIENT_TOKEN, auth=CLIENT_AUTH, db_url=db_url)

    # Don't actually create games on SpellTable in test suite!
    create_game_mock = mocker.Mock(return_value="http://example.com/game")
    monkeypatch.setattr(bot, "create_game", create_game_mock)

    # Each test should have a clean slate. If we're using sqlite this is ensured
    # automatically as each test will create its own new spellbot.db file. With other
    # databases we'll have to manually clean out any existing data before each
    # test as the previous tests could have left data behind.
    for table in bot.data.metadata.tables.keys():
        bot.data.conn.execute(f"DELETE FROM {table};")

    # Make sure that all users have their send calls reset between client tests.
    for user in ALL_USERS:
        user.sent = MagicMock()

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
        channel = MockTextChannel(5, UNAUTHORIZED_CHANNEL, members=CHANNEL_MEMBERS)
        await client.on_message(MockMessage(someone(), channel, "!help"))
        channel.sent.assert_not_called()

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
        msg = MockMessage(author, channel, "!h")
        if hasattr(channel, "recipient"):
            assert channel.recipient == author
        await client.on_message(msg)
        assert channel.last_sent_response == ("Did you mean: !hello, !help?")

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_invalid_request(self, client, channel):
        await client.on_message(MockMessage(someone(), channel, "!xenomorph"))
        assert channel.last_sent_response == 'Sorry, there is no "xenomorph" command.'

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_on_message_from_a_bot(self, client, channel):
        author = BOT
        await client.on_message(MockMessage(author, channel, "!help"))
        assert len(channel.all_sent_calls) == 0

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_process_long_response_with_file(self, client, channel, monkeypatch):
        file = MockFile("file")

        @spellbot.command()
        async def mock_help(channel, author, params):
            return "What? " * 1000, file

        monkeypatch.setattr(client, "help", mock_help)
        await client.on_message(MockMessage(someone(), channel, "!help"))
        assert len(channel.all_sent_responses) == 3
        assert channel.all_sent_files == [file]

    @pytest.mark.parametrize(
        "channel,author", [(text_channel(), GUY), (private_channel(), FRIEND)]
    )
    async def test_process_direct_embed(self, client, channel, author, monkeypatch):
        @spellbot.command()
        async def mock_help(channel, author, params):
            return spellbot.Direct(Embed()), None

        monkeypatch.setattr(client, "help", mock_help)
        await client.on_message(MockMessage(author, channel, "!help"))
        assert json.loads(author.all_sent_embeds_json) == [{"type": "rich"}]

    @pytest.mark.parametrize("channel", [text_channel(), private_channel()])
    async def test_process_weird_response(self, client, channel, monkeypatch):
        @spellbot.command()
        async def mock_help(channel, author, params):
            return 42, None  # can't send int as a response

        monkeypatch.setattr(client, "help", mock_help)
        with pytest.raises(RuntimeError):
            await client.on_message(MockMessage(someone(), channel, "!help"))

    async def test_paginate(self, client):
        def subject(text):
            return [page for page in client.paginate(text)]

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

    @pytest.mark.parametrize(
        "channel,author", [(text_channel(), GUY), (private_channel(), FRIEND)]
    )
    async def test_on_message_help(self, client, channel, author, snap):
        await client.on_message(MockMessage(author, channel, "!help"))
        for response in author.all_sent_responses:
            snap(response)
        assert len(author.all_sent_calls) == 1

    async def test_on_message_queue_dm(self, client):
        author = someone()
        await client.on_message(MockMessage(author, private_channel(), "!queue"))
        assert author.all_sent_calls == []

    async def test_on_message_queue(self, client):
        channel = text_channel()
        await client.on_message(MockMessage(GUY, channel, "!queue"))
        assert GUY.last_sent_response == "You have been entered into the play queue."

        await client.on_message(MockMessage(GUY, channel, "!queue"))
        assert GUY.last_sent_response == "You are already in the queue."

        await client.on_message(MockMessage(FRIEND, channel, "!queue"))
        assert FRIEND.last_sent_response == "You have been entered into the play queue."

        await client.on_message(MockMessage(BUDDY, channel, "!queue"))
        assert BUDDY.last_sent_response == "You have been entered into the play queue."

        await client.on_message(MockMessage(DUDE, channel, "!queue"))
        ready = "Your game is ready, go to http://example.com/game to begin playing!"
        assert GUY.last_sent_response == ready
        assert BUDDY.last_sent_response == ready
        assert FRIEND.last_sent_response == ready
        assert DUDE.last_sent_response == ready

        await client.on_message(MockMessage(GUY, channel, "!queue"))
        assert GUY.last_sent_response == "You have been entered into the play queue."


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
        print("running:", " ".join(str(part) for part in cmd))
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"flake8 issues:\n{proc.stdout.decode('utf-8')}"

    def test_black(self):
        """Checks that the Python codebase passes configured black checks."""
        chdir(REPO_ROOT)
        cmd = ["black", "-v", "--check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"black issues:\n{proc.stderr.decode('utf-8')}"

    def test_isort(self):
        """Checks that the Python codebase imports are correctly sorted."""
        chdir(REPO_ROOT)
        cmd = ["isort", "-df", "-rc", "-c", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"isort issues:\n{proc.stdout.decode('utf-8')}"

    def test_sort_strings(self):
        """Checks that the strings data is correctly sorted."""
        chdir(REPO_ROOT)
        cmd = ["python", "scripts/sort_strings.py", "--check"]
        print("running:", " ".join(str(part) for part in cmd))
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

        assert documented == implemented

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
        assert config_keys - used_keys == set()

    # Tracks the usage of snapshot files over the entire test session.
    # When it fails it means you probably need to clear out any unused snapshot files.
    def test_snapshots(self):
        """Checks that all of the snapshots files are being used."""
        snapshots_dir = REPO_ROOT / "tests" / "snapshots"
        snapshot_files = set(f.name for f in snapshots_dir.glob("*.txt"))
        assert snapshot_files == SNAPSHOTS_USED
